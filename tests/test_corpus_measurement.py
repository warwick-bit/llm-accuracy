"""Behaviour checks for the corpus measurement harness."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.measure_tool_result_corpus import (
    CorpusError,
    compare,
    load_hook,
    main,
    render_report,
    safe_summary,
    score,
    tool_results,
    transcript_paths,
)


ROOT = Path(__file__).resolve().parents[1]
SENTINEL = ROOT / "plugins" / "llm-accuracy" / "hooks" / "partial-result-sentinel.py"

# A canary placed inside record content. If any measurement path echoed payload
# values, this prose would appear in the rendered output.
PAYLOAD_MARKER = "this prose belongs to a record and must not be reported"


def wrap(body: object) -> list[dict]:
    """Deliver a body the way a host delivers an MCP tool result."""
    return [{"type": "text", "text": json.dumps(body)}]


def transcript_lines(
    payloads: list[object],
    *,
    tool: str = "mcp__example__list_things",
    session: str = "session-one",
) -> list[str]:
    """Build the record pair a host writes: the tool_use, then its result."""
    lines = [json.dumps({"type": "user", "message": {"content": "hello"}})]
    for index, payload in enumerate(payloads):
        call_id = f"toolu_{index}"
        lines.append(
            json.dumps(
                {
                    "type": "assistant",
                    "sessionId": session,
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": call_id, "name": tool},
                        ]
                    },
                }
            )
        )
        lines.append(
            json.dumps(
                {
                    "type": "user",
                    "sessionId": session,
                    "toolUseResult": payload,
                    "message": {
                        "content": [
                            {"type": "tool_result", "tool_use_id": call_id},
                        ]
                    },
                }
            )
        )
    return lines


def write_transcript(path: Path, payloads: list[object], **kwargs: str) -> None:
    lines = transcript_lines(payloads, **kwargs)
    lines.append('{"toolUseResult": {"has_more": tr')  # a truncated mid-write line
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect(root: Path, **kwargs: object) -> list[object]:
    return list(tool_results(transcript_paths([root]), **kwargs))  # type: ignore[arg-type]


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

    assert len(collect(tmp_path)) == 2


def test_scopes_to_the_tools_the_hook_is_actually_wired_to(tmp_path: Path) -> None:
    """Production runs the sentinel on `mcp__.*` only.

    Scoring every tool result reports a denominator that is mostly out of scope --
    built-in results outnumber MCP ones heavily -- which overstates how much
    relevant evidence a measurement rests on.
    """
    fires = wrap({"rows": [{"id": 1}], "has_more": True})
    write_transcript(tmp_path / "mcp.jsonl", [fires], tool="mcp__example__list")
    write_transcript(tmp_path / "builtin.jsonl", [fires, fires], tool="Read")

    assert len(collect(tmp_path)) == 1
    assert len(collect(tmp_path, mcp_only=False)) == 3


def test_a_result_whose_tool_cannot_be_resolved_is_out_of_mcp_scope(
    tmp_path: Path,
) -> None:
    orphan = {
        "type": "user",
        "toolUseResult": wrap({"rows": [], "has_more": True}),
        "message": {"content": [{"type": "tool_result", "tool_use_id": "missing"}]},
    }
    (tmp_path / "orphan.jsonl").write_text(json.dumps(orphan) + "\n", encoding="utf-8")

    assert collect(tmp_path) == []
    assert len(collect(tmp_path, mcp_only=False)) == 1


def test_scores_a_corpus_per_signal_code(tmp_path: Path) -> None:
    write_transcript(
        tmp_path / "session-a.jsonl",
        [
            wrap({"rows": [{"id": 1}], "has_more": True, "truncated": True}),
            wrap({"rows": [{"id": 2}], "truncated": True}),
            wrap({"rows": [{"id": 3, "has_more": True}]}),
        ],
    )

    observations, codes = score(collect(tmp_path), load_hook(SENTINEL))

    # The third is record content, so it must not count. The first carries two
    # signals, which count once each rather than as one combined bucket.
    assert {index for index, _ in observations} == {0, 1}
    assert codes == {"pagination_incomplete": 1, "truncated_result": 2}


def test_excludes_a_session_by_its_recorded_id_not_its_filename(
    tmp_path: Path,
) -> None:
    """A subagent transcript is named for the agent, not its parent session.

    Filtering on the filename alone leaves a session's own subagent payloads in
    the corpus, so the self-contamination control has to read the record.
    """
    fires = wrap({"rows": [{"id": 1}], "has_more": True})
    write_transcript(tmp_path / "other.jsonl", [fires], session="keep-me")
    write_transcript(tmp_path / "agent-42.jsonl", [fires, fires], session="mine-abc123")

    everything = list(tool_results(transcript_paths([tmp_path])))
    without_mine = list(
        tool_results(
            transcript_paths([tmp_path], frozenset({"abc123"})),
            exclude_sessions=frozenset({"abc123"}),
        )
    )

    assert len(everything) == 3
    assert len(without_mine) == 1


def test_overlapping_transcript_roots_do_not_double_count(tmp_path: Path) -> None:
    write_transcript(tmp_path / "session-a.jsonl", [wrap({"rows": []})])

    assert len(list(transcript_paths([tmp_path, tmp_path]))) == 1


def test_a_deeply_nested_line_does_not_abort_the_measurement(tmp_path: Path) -> None:
    """The JSON decoder raises RecursionError, not ValueError, on deep nesting."""
    good = transcript_lines([wrap({"rows": [], "has_more": True})])
    deep = '{"toolUseResult":' + "[" * 20000 + "0" + "]" * 20000 + "}"
    (tmp_path / "session-a.jsonl").write_text(
        "\n".join([deep, *good]) + "\n", encoding="utf-8"
    )

    assert len(collect(tmp_path)) == 1


def test_compare_counts_observations_so_a_code_swap_cannot_read_as_unchanged(
    tmp_path: Path,
) -> None:
    """`lost: 0` must not be reachable by exchanging one signal for another.

    Comparing only whether each result fired would call a rule that swapped
    `pagination_incomplete` for `truncated_result` a no-op, which is exactly the
    kind of change a control is supposed to surface.
    """
    write_transcript(
        tmp_path / "session-a.jsonl", [wrap({"rows": [], "has_more": True})]
    )
    payloads = collect(tmp_path)
    baseline = SimpleNamespace(collect_codes=lambda _: {"pagination_incomplete"})
    swapped = SimpleNamespace(collect_codes=lambda _: {"truncated_result"})
    same = SimpleNamespace(collect_codes=lambda _: {"pagination_incomplete"})

    unchanged = compare(payloads, baseline, same)
    swap = compare(payloads, baseline, swapped)

    assert unchanged["lost"] == 0 and unchanged["gained"] == 0
    assert swap["baseline_firing"] == swap["candidate_firing"] == 1
    assert swap["lost"] == 1
    assert swap["gained"] == 1


def test_compare_detects_a_narrowed_rule(tmp_path: Path) -> None:
    write_transcript(
        tmp_path / "session-a.jsonl",
        [
            wrap({"rows": [{"id": 1}], "has_more": True}),
            wrap({"rows": [{"id": 2}], "row_cap_hit": True}),
        ],
    )
    payloads = collect(tmp_path)
    baseline = load_hook(SENTINEL, "baseline")
    candidate = load_hook(SENTINEL, "candidate")
    setattr(
        candidate,
        "TRUE_MEANS_PARTIAL",
        {
            key: value
            for key, value in candidate.TRUE_MEANS_PARTIAL.items()
            if value != "row_cap_hit"
        },
    )

    narrowed = compare(payloads, baseline, candidate)

    assert narrowed["lost"] == 1
    assert narrowed["gained"] == 0


def test_a_hook_returning_payload_derived_codes_cannot_reach_the_report(
    tmp_path: Path,
) -> None:
    """The safety property, attacked the way it would actually fail.

    A hook is arbitrary imported code. If it returns a string built from the
    payload, the count must still be printable, so the code is checked against a
    vocabulary this script owns and anything else becomes a fixed placeholder.
    """
    write_transcript(tmp_path / "session-a.jsonl", [wrap({"note": PAYLOAD_MARKER})])
    payloads = collect(tmp_path)
    leaky = SimpleNamespace(
        collect_codes=lambda payload: {json.loads(payload[0]["text"])["note"]}
    )

    observations, codes = score(payloads, leaky)
    report = render_report({"results": len(payloads), "codes": codes})

    assert codes == {"<unrecognised-code>": 1}
    assert observations == {(0, "<unrecognised-code>")}
    assert PAYLOAD_MARKER not in report


def test_a_hook_that_raises_or_prints_the_payload_cannot_reach_the_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An exception message and a stray print are both payload-carrying paths."""
    write_transcript(tmp_path / "session-a.jsonl", [wrap({"note": PAYLOAD_MARKER})])
    payloads = collect(tmp_path)

    def explode(payload: object) -> set[str]:
        raise RuntimeError(json.loads(payload[0]["text"])["note"])  # type: ignore[index]

    def chatty(payload: object) -> set[str]:
        print(json.loads(payload[0]["text"])["note"])  # type: ignore[index]
        return set()

    _, raised = score(payloads, SimpleNamespace(collect_codes=explode))
    _, printed = score(payloads, SimpleNamespace(collect_codes=chatty))

    assert raised == {"<hook-error>": 1}
    assert printed == {}
    assert PAYLOAD_MARKER not in capsys.readouterr().out


def test_an_exception_raised_while_iterating_the_result_cannot_escape() -> None:
    """The guard has to cover iteration, not just the call.

    Round two: the try/except wrapped `collect_codes(payload)` only, so a
    returned object that raised from `__iter__` carried its message -- and any
    payload the hook had put in it -- straight out to the traceback.
    """

    class Bomb(list):
        def __iter__(self):
            raise RuntimeError(PAYLOAD_MARKER)

    _, counts = score(["a payload"], SimpleNamespace(collect_codes=lambda _: Bomb()))

    assert counts == {"<hook-error>": 1}


def test_a_code_that_only_compares_equal_is_replaced_by_the_canonical_one() -> None:
    """Equality is not identity, and only identity is safe to print.

    Round two: a `str` subclass comparing equal to a known code passed the
    vocabulary check, was kept, and rendered its payload through `__str__`.
    """

    class Sneaky(str):
        def __str__(self) -> str:
            return PAYLOAD_MARKER

    _, counts = score(
        ["a payload"],
        SimpleNamespace(collect_codes=lambda _: {Sneaky("pagination_incomplete")}),
    )
    report = render_report({"results": 1, "codes": counts})

    assert counts == {"pagination_incomplete": 1}
    assert PAYLOAD_MARKER not in report
    assert type(next(iter(counts))) is str


def test_a_swap_between_two_unknown_codes_is_flagged_rather_than_missed() -> None:
    """Unknown codes collapse to one placeholder, so a swap between them hides.

    Round two: the observation-level control caught a known-to-known swap but
    not an unknown-to-unknown one. It cannot distinguish them without printing
    them, so it reports how many observations are in that state instead: a
    non-zero `unrecognised` means the vocabulary is stale and `lost`/`gained`
    cannot be read at face value.
    """
    known = compare(
        ["a payload"],
        SimpleNamespace(collect_codes=lambda _: {"pagination_incomplete"}),
        SimpleNamespace(collect_codes=lambda _: {"truncated_result"}),
    )
    unknown = compare(
        ["a payload"],
        SimpleNamespace(collect_codes=lambda _: {"legacy_partial_a"}),
        SimpleNamespace(collect_codes=lambda _: {"legacy_partial_b"}),
    )

    assert (known["lost"], known["gained"], known["unrecognised"]) == (1, 1, 0)
    assert unknown["unrecognised"] == 1


def test_an_ordinary_finalizer_runs_inside_the_capture() -> None:
    """Round three: a `__del__` printed after the capture closed.

    The hook's object is released while the redirect is still open, so under
    refcounting its finalizer runs inside the quarantine. This closes the
    careless case. It does not make the process safe against a hook that
    deliberately defers finalization, which the docstring now says outright
    rather than claiming a containment that no in-process check can provide.
    """

    class Finalizer(list):
        def __init__(self) -> None:
            super().__init__(["pagination_incomplete"])

        def __del__(self) -> None:
            print(PAYLOAD_MARKER)

    captured_out, captured_err = io.StringIO(), io.StringIO()
    with (
        contextlib.redirect_stdout(captured_out),
        contextlib.redirect_stderr(captured_err),
    ):
        _, counts = score(
            ["a payload"], SimpleNamespace(collect_codes=lambda _: Finalizer())
        )

    assert counts == {"pagination_incomplete": 1}
    assert PAYLOAD_MARKER not in captured_out.getvalue()
    assert PAYLOAD_MARKER not in captured_err.getvalue()


def test_a_null_tool_result_is_a_result_not_an_absent_key(tmp_path: Path) -> None:
    """`toolUseResult: null` is a recorded result with a null payload.

    Treating it as an absent key made `--scope all` quietly narrower than its
    own description. It changes no current figure -- the corpus contains none --
    but a denominator should mean what it says.
    """
    lines = [
        json.dumps(
            {
                "message": {
                    "content": [{"type": "tool_use", "id": "t1", "name": "mcp__p__get"}]
                }
            }
        ),
        json.dumps(
            {
                "toolUseResult": None,
                "message": {"content": [{"type": "tool_result", "tool_use_id": "t1"}]},
            }
        ),
    ]
    (tmp_path / "session-a.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert collect(tmp_path) == [None]


def test_the_report_refuses_unknown_fields_codes_and_free_text() -> None:
    """The safety property is enforced at one chokepoint, not merely intended."""
    with pytest.raises(CorpusError):
        safe_summary({"leaked": 1})
    with pytest.raises(CorpusError):
        safe_summary({"codes": {PAYLOAD_MARKER: 1}})
    with pytest.raises(CorpusError):
        safe_summary({"scope": PAYLOAD_MARKER})
    with pytest.raises(CorpusError):
        safe_summary({"results": PAYLOAD_MARKER})


def test_json_output_goes_through_the_same_chokepoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--json` must not become the path that bypasses the safety check."""
    write_transcript(
        tmp_path / "session-a.jsonl",
        [wrap({"rows": [{"note": PAYLOAD_MARKER}], "has_more": True})],
    )

    exit_code = main(
        ["--transcript-root", str(tmp_path), "--hook", str(SENTINEL), "--json"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "scope": "mcp",
        "results": 1,
        "firing": 1,
        "observations": 1,
        "codes": {"pagination_incomplete": 1},
    }
    assert PAYLOAD_MARKER not in json.dumps(payload)


def test_argument_errors_do_not_echo_the_value_they_rejected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Round four: argparse quoted the offending value back.

    Someone can paste anything into an argument, so the parser reports that the
    arguments were invalid without repeating them.
    """
    with pytest.raises(SystemExit) as exit_info:
        main(["--scope", PAYLOAD_MARKER])

    captured = capsys.readouterr()
    assert exit_info.value.code == 2
    assert PAYLOAD_MARKER not in captured.out + captured.err
    assert "invalid arguments" in captured.out + captured.err


def test_a_rejected_return_type_still_releases_inside_the_capture() -> None:
    """The early return for an unrecognised type skipped the release.

    Round four, non-blocking: only the accepted-container branch dropped the
    hook's object before the capture closed, so a finalizer on a rejected type
    still printed outside it.
    """

    class Odd:
        def __del__(self) -> None:
            print(PAYLOAD_MARKER)

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
        _, counts = score(["a payload"], SimpleNamespace(collect_codes=lambda _: Odd()))

    assert counts == {"<unrecognised-code>": 1}
    assert PAYLOAD_MARKER not in captured.getvalue()


def test_the_chokepoint_replaces_rather_than_checks_every_printable_thing() -> None:
    """Rounds five and six: `in` and `isinstance` are not enough, anywhere.

    A subclass of `str` or `int` satisfies every membership and instance test and
    can still render anything through `__format__`, `__str__` or `__repr__`, and
    a non-string object can forge a label through `__eq__`/`__hash__`. So labels,
    scope values and code names are looked up and replaced by this script's own
    instances, and counts must be exactly `int`. Round five fixed only the code
    names, which left the other three open.
    """

    class Str(str):
        def __format__(self, spec: str) -> str:
            return PAYLOAD_MARKER

        def __str__(self) -> str:
            return PAYLOAD_MARKER

        def __repr__(self) -> str:
            return PAYLOAD_MARKER

    class Int(int):
        def __format__(self, spec: str) -> str:
            return PAYLOAD_MARKER

    class ForgedLabel:
        def __hash__(self) -> int:
            return hash("results")

        def __eq__(self, other: object) -> bool:
            return other == "results"

        def __str__(self) -> str:
            return PAYLOAD_MARKER

    attacks: list[dict] = [
        {"scope": Str("mcp")},
        {Str("results"): 1},
        {ForgedLabel(): 1},
        {"results": Int(7)},
        {"codes": {"row_cap_hit": Int(1)}},
        {"codes": {Str("row_cap_hit"): 1}},
    ]
    for attack in attacks:
        with pytest.raises(CorpusError) as error:
            render_report(attack)
        assert PAYLOAD_MARKER not in str(error.value), attack

    # And an ordinary summary still renders, so the check is not simply refusing
    # everything.
    assert render_report(
        {"scope": "mcp", "results": 2, "codes": {"row_cap_hit": 1}}
    ) == ("scope: mcp\nresults: 2\ncodes:\n         1  row_cap_hit")


def test_the_chokepoint_refuses_without_repeating_what_it_refused() -> None:
    """A fail-closed check that prints the rejected value is not fail-closed."""
    with pytest.raises(CorpusError) as error:
        safe_summary({"codes": {PAYLOAD_MARKER: 1}})

    assert PAYLOAD_MARKER not in str(error.value)


def test_main_reports_a_bad_hook_path_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    not_a_module = tmp_path / "corpus.txt"
    not_a_module.write_text("not python\n", encoding="utf-8")

    exit_code = main(["--transcript-root", str(tmp_path), "--hook", str(not_a_module)])

    assert exit_code == 2
    assert capsys.readouterr().out.startswith("error:")


def test_load_hook_rejects_a_path_that_is_not_a_module(tmp_path: Path) -> None:
    not_a_module = tmp_path / "corpus.txt"
    not_a_module.write_text("not python\n", encoding="utf-8")

    with pytest.raises(CorpusError):
        load_hook(not_a_module)
