"""Behaviour checks for the corpus measurement harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.measure_tool_result_corpus import (
    compare,
    load_hook,
    render_report,
    score,
    tool_results,
    transcript_paths,
)


ROOT = Path(__file__).resolve().parents[1]
SENTINEL = ROOT / "plugins" / "llm-accuracy" / "hooks" / "partial-result-sentinel.py"

# A canary placed inside record content. If any measurement path echoed payload
# values, this prose would appear in the rendered report.
PAYLOAD_MARKER = "this prose belongs to a record and must not be reported"


def write_transcript(path: Path, payloads: list[object]) -> None:
    """Write payloads in the shape a host transcript records them."""
    lines = [json.dumps({"toolUseResult": payload}) for payload in payloads]
    # Conversation lines and a truncated line, which the reader must skip.
    lines.insert(0, json.dumps({"type": "user", "message": {"content": "hello"}}))
    lines.append('{"toolUseResult": {"has_more": tr')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def wrap(body: object) -> list[dict]:
    """Deliver a body the way a host delivers an MCP tool result."""
    return [{"type": "text", "text": json.dumps(body)}]


def test_reads_tool_results_and_skips_conversation_and_bad_lines(
    tmp_path: Path,
) -> None:
    write_transcript(
        tmp_path / "session-a.jsonl",
        [
            wrap({"rows": [{"note": PAYLOAD_MARKER}], "has_more": True}),
            wrap({"rows": []}),
        ],
    )

    found = list(tool_results(transcript_paths([tmp_path])))

    assert len(found) == 2


def test_scores_a_corpus_by_signal_code(tmp_path: Path) -> None:
    write_transcript(
        tmp_path / "session-a.jsonl",
        [
            wrap({"rows": [{"id": 1}], "has_more": True}),
            wrap({"rows": [{"id": 2}], "truncated": True}),
            wrap({"rows": [{"id": 3, "has_more": True}]}),
        ],
    )
    payloads = list(tool_results(transcript_paths([tmp_path])))

    firing, codes = score(payloads, load_hook(SENTINEL))

    # The third is record content, so it must not count.
    assert firing == [0, 1]
    assert codes == {"pagination_incomplete": 1, "truncated_result": 1}


def test_excludes_named_sessions_so_a_corpus_cannot_measure_its_own_work(
    tmp_path: Path,
) -> None:
    fires = wrap({"rows": [{"id": 1}], "has_more": True})
    write_transcript(tmp_path / "other-session.jsonl", [fires])
    write_transcript(tmp_path / "mine-abc123.jsonl", [fires, fires])

    everything = list(tool_results(transcript_paths([tmp_path])))
    without_mine = list(
        tool_results(transcript_paths([tmp_path], frozenset({"abc123"})))
    )

    assert len(everything) == 3
    assert len(without_mine) == 1


def test_compare_reports_what_a_change_cost_over_one_snapshot(tmp_path: Path) -> None:
    """The control a raw count cannot give.

    The corpus grows while a session works on the hook, so comparing today's
    count against yesterday's can show a gain from an unchanged hook. Scoring
    both versions over ONE snapshot is what actually isolates the change.
    """
    write_transcript(
        tmp_path / "session-a.jsonl",
        [
            wrap({"rows": [{"id": 1}], "has_more": True}),
            wrap({"rows": [{"id": 2}], "row_cap_hit": True}),
        ],
    )
    payloads = list(tool_results(transcript_paths([tmp_path])))
    baseline = load_hook(SENTINEL, "baseline")
    candidate = load_hook(SENTINEL, "candidate")
    # A candidate that no longer reports one of the two codes.
    setattr(
        candidate,
        "TRUE_MEANS_PARTIAL",
        {
            key: value
            for key, value in candidate.TRUE_MEANS_PARTIAL.items()
            if value != "row_cap_hit"
        },
    )

    unchanged = compare(payloads, baseline, load_hook(SENTINEL, "same"))
    narrowed = compare(payloads, baseline, candidate)

    assert unchanged == {
        "results": 2,
        "baseline_firing": 2,
        "candidate_firing": 2,
        "lost": 0,
        "gained": 0,
    }
    assert narrowed["lost"] == 1
    assert narrowed["gained"] == 0


def test_report_carries_counts_and_code_names_but_never_payload_content(
    tmp_path: Path,
) -> None:
    """The safety property. A corpus of real tool output stays inside the process.

    Every rendered value is an int or a signal code from the hook's own closed
    vocabulary, so no record content, prose, identifier, or field value can be
    written out. This test drives the real path end to end with a marked payload
    and asserts the marker never surfaces.
    """
    write_transcript(
        tmp_path / "session-a.jsonl",
        [
            wrap(
                {
                    "rows": [{"note": PAYLOAD_MARKER}],
                    "has_more": True,
                    PAYLOAD_MARKER: PAYLOAD_MARKER,
                }
            )
        ],
    )
    payloads = list(tool_results(transcript_paths([tmp_path])))
    firing, codes = score(payloads, load_hook(SENTINEL))

    report = render_report({"results": len(payloads), "firing": len(firing), **codes})

    assert PAYLOAD_MARKER not in report
    assert "results: 1" in report
    assert "firing: 1" in report
    assert "pagination_incomplete" in report


def test_report_refuses_to_render_anything_that_is_not_a_count() -> None:
    """The safety property is enforced, not merely intended."""
    with pytest.raises(TypeError):
        render_report({"leaked": "a payload value"})


def test_load_hook_rejects_a_path_that_is_not_a_module(tmp_path: Path) -> None:
    not_a_module = tmp_path / "corpus.txt"
    not_a_module.write_text("not python\n", encoding="utf-8")

    with pytest.raises(ValueError):
        load_hook(not_a_module)
