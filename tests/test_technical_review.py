"""Boundary tests for explicit evidence-packet review; no model calls."""

import importlib.util
import io
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/llm-accuracy/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "technical_review", SCRIPTS / "technical_review.py"
)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

PACKET = {
    "question": "What is the incident status?",
    "draft": "Status: Open. Local tests reportedly pass.",
    "evidence": [
        {
            "id": "e1",
            "source": "User report",
            "text": "Local tests pass; production unchecked. No tracker status supplied.",
        }
    ],
}
FINDING = {
    "category": "unsupported",
    "draft_quote": "Status: Open.",
    "question_quote": "",
    "evidence_ids": ["e1"],
}


def host(answer=None, **changes):
    return {
        "status": "ok",
        "answers": [json.dumps({"findings": [FINDING]}) if answer is None else answer],
        "result_count": 1,
        "hook_response_count": 0,
        "resolved_model": "claude-reviewer-1",
        "host_inventory": {
            "status": "reported",
            "tool_count": 0,
            "mcp_count": 0,
            "plugin_count": 0,
            "telemetry_plugin_count": 0,
            "accuracy_plugin_count": 0,
        },
        **changes,
    }


def parse(finding):
    return review.parse_review(json.dumps({"findings": [finding]}), PACKET)


def test_literal_anchor_and_safe_output():
    assert parse(FINDING) == {
        "status": "reviewed",
        "findings": [
            {
                "category": "unsupported",
                "anchor": "draft",
                "start": 0,
                "length": 13,
                "evidence_ids": ["e1"],
            }
        ],
    }


@pytest.mark.parametrize(
    "change",
    [
        {"category": []},
        {"category": "invented"},
        {"draft_quote": "missing"},
        {"draft_quote": ""},
        {"question_quote": "not empty"},
        {"evidence_ids": ["missing"]},
        {"evidence_ids": ["e1", "e1"]},
        {"evidence_ids": []},
        {"explanation": "extra assertion"},
    ],
)
def test_invalid_finding(change):
    assert parse(FINDING | change)["status"] != "reviewed"


@pytest.mark.parametrize(
    "answer",
    [
        '{"findings":[],"findings":[]}',
        "null",
        "[]",
        '{"findings":null}',
        '{"findings":[],"verdict":"approved"}',
        "not json",
        json.dumps({"findings": [FINDING] * 21}),
    ],
)
def test_bad_review_never_becomes_empty_success(answer):
    result = review.parse_review(answer, PACKET)
    assert result["status"] != "reviewed"
    assert "findings" not in result


def test_duplicate_or_ambiguous_quotes_rejected():
    answer = json.dumps({"findings": [FINDING]})
    assert (
        review.parse_review(answer, PACKET | {"draft": PACKET["draft"] * 2})["status"]
        == "invalid_quote"
    )
    assert (
        review.parse_review(json.dumps({"findings": [FINDING] * 2}), PACKET)["status"]
        == "duplicate_finding"
    )


def test_omission_anchors_question_and_overhedging_anchors_draft():
    omission = FINDING | {
        "category": "omission",
        "draft_quote": "",
        "question_quote": PACKET["question"],
    }
    assert parse(omission)["findings"][0]["anchor"] == "question"
    assert (
        parse(FINDING | {"category": "overhedging"})["findings"][0]["anchor"] == "draft"
    )


@pytest.mark.parametrize(
    "packet",
    [
        None,
        {},
        PACKET | {"extra": "x"},
        PACKET | {"question": ""},
        PACKET | {"draft": "x" * 24001},
        PACKET | {"evidence": []},
        PACKET | {"evidence": PACKET["evidence"] * 2},
        PACKET | {"evidence": [{"id": "../x", "source": "s", "text": "t"}]},
        PACKET | {"evidence": [{"id": "e1", "text": "t"}]},
    ],
)
def test_bad_input_never_calls_model(monkeypatch, packet):
    monkeypatch.setattr(
        review, "run_probe", lambda *a, **kw: pytest.fail("model called")
    )
    result = review.review_packet(packet, model="fable")
    assert result["status"] == "invalid_input"
    assert (
        result["presentation"]["headline"] == "Review unavailable; no review verdict."
    )


@pytest.mark.parametrize(
    "options",
    [
        {"model": "-option"},
        {"model": None},
        {"model": "fable", "timeout": True},
        {"model": "fable", "timeout": 181},
        {"model": "fable", "author_model": []},
        {"model": "fable", "author_model": "opus"},
    ],
)
def test_bad_options_never_call_model(monkeypatch, options):
    monkeypatch.setattr(
        review, "run_probe", lambda *a, **kw: pytest.fail("model called")
    )
    assert review.review_packet(PACKET, **options)["status"] != "reviewed"


def test_single_explicit_call_has_no_plugin_or_tools(monkeypatch):
    calls = []

    def probe(prompts, plugin, **options):
        calls.append((prompts, plugin, options))
        return host()

    monkeypatch.setattr(review, "run_probe", probe)
    result = review.review_packet(PACKET, model="fable", author_model="claude-author-1")
    assert len(calls) == 1
    assert calls[0] == (
        [review.PROMPT + json.dumps(PACKET)],
        None,
        {"model": "fable", "effort": "medium", "timeout": 180},
    )
    assert result["reviewer"]["model_comparison"] == "different_from_reported_author"
    assert result["reviewer"]["author_identity_source"] == "caller_reported"
    assert PACKET["draft"] not in json.dumps(result)
    assert "draft_quote" not in json.dumps(result)


@pytest.mark.parametrize(
    "author,expected",
    [
        (None, "unverified"),
        ("claude-reviewer-1", "same_as_reported_author"),
        ("claude-author-1", "different_from_reported_author"),
    ],
)
def test_identity_is_not_inferred(monkeypatch, author, expected):
    monkeypatch.setattr(review, "run_probe", lambda *a, **kw: host())
    assert (
        review.review_packet(PACKET, model="fable", author_model=author)["reviewer"][
            "model_comparison"
        ]
        == expected
    )


@pytest.mark.parametrize(
    "status",
    [
        "authentication",
        "rate_limit",
        "timeout",
        "host_error",
        "host_unavailable",
        "auth_copy_failed",
        "missing_result",
        "oversized_output",
    ],
)
def test_failed_review_is_explicit_no_retry_no_raw_output(monkeypatch, status):
    calls = []

    def probe(*a, **kw):
        calls.append(1)
        return host("PRIVATE SENTINEL", status=status)

    monkeypatch.setattr(review, "run_probe", probe)
    result = review.review_packet(PACKET, model="fable")
    assert len(calls) == 1
    assert result["status"] == "review_unavailable"
    assert "PRIVATE" not in json.dumps(result)
    assert "findings" not in result


@pytest.mark.parametrize(
    "change",
    [
        {"tool_count": 1},
        {"mcp_count": 1},
        {"accuracy_plugin_count": 1},
        {"plugin_count": 1},
        {"status": "unreported"},
        {"status": "changed"},
    ],
)
def test_unattested_isolation_rejected(monkeypatch, change):
    response = host()
    response["host_inventory"].update(change)
    monkeypatch.setattr(review, "run_probe", lambda *a, **kw: response)
    assert (
        review.review_packet(PACKET, model="fable")["status"] == "identity_unverified"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"resolved_model": "unreported"},
        {"hook_response_count": 1},
        {"result_count": 2},
        {"answers": []},
    ],
)
def test_incomplete_host_metadata_rejected(monkeypatch, change):
    monkeypatch.setattr(review, "run_probe", lambda *a, **kw: host(**change))
    assert review.review_packet(PACKET, model="fable")["status"] != "reviewed"


def test_empty_review_is_not_certification(monkeypatch):
    monkeypatch.setattr(review, "run_probe", lambda *a, **kw: host('{"findings":[]}'))
    result = review.review_packet(PACKET, model="fable")
    assert result["status"] == "reviewed" and result["findings"] == []
    assert (
        result["presentation"]["headline"]
        == "Reviewer found no material issue in the supplied packet."
    )
    assert "not independently verified" in result["presentation"]["gap"]


@pytest.mark.parametrize(
    "raw", ['{"question":"a","question":"b"}', "x" * 24001, "invalid PRIVATE SENTINEL"]
)
def test_cli_rejects_input_without_echo(monkeypatch, capsys, raw):
    monkeypatch.setattr(sys, "argv", ["technical_review", "--model", "fable"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    monkeypatch.setattr(
        review, "run_probe", lambda *a, **kw: pytest.fail("model called")
    )
    assert review.main() == 2
    output = capsys.readouterr().out
    assert json.loads(output)["status"] == "invalid_input"
    assert "PRIVATE" not in output


def test_cli_success(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["technical_review", "--model", "fable"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(PACKET)))
    monkeypatch.setattr(review, "run_probe", lambda *a, **kw: host())
    assert review.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "reviewed"


def test_command_is_explicit_only_and_not_wired_to_hooks():
    skill = (ROOT / "plugins/llm-accuracy/skills/technical-review/SKILL.md").read_text()
    hooks = (ROOT / "plugins/llm-accuracy/hooks/hooks.json").read_text()
    assert "disable-model-invocation: true" in skill
    assert "technical_review" not in hooks and "technical-review" not in hooks


def test_frozen_pilot_receipt_matches_current_prompt_and_seeded_spans():
    import hashlib

    receipt = json.loads(
        (ROOT / "docs/validation/technical-review-pilot-2026-09-23.json").read_text()
    )
    cases = {
        c["id"]: c
        for c in json.loads(
            (ROOT / "tests/fixtures/technical-review-cases.json").read_text()
        )
    }
    assert (
        hashlib.sha256(review.PROMPT.encode()).hexdigest()
        == receipt["reviewer_prompt_sha256"]
    )
    seen = []
    for stage in receipt["stages"].values():
        assert stage["passed"]
        for row in stage["rows"]:
            case = cases[row["case"]]
            seen.append(row["case"])
            assert row["matched"] and row["result"]["status"] == "reviewed"
            covered = set()
            for finding in row["result"]["findings"]:
                text = case["packet"][finding["anchor"]]
                quote = text[finding["start"] : finding["start"] + finding["length"]]
                matches = set()
                for index, defect in enumerate(case["defects"]):
                    start = text.find(defect["allowed_span"])
                    if (
                        finding["category"] == defect["category"]
                        and finding["anchor"] == defect["anchor"]
                        and start >= 0
                        and start <= finding["start"]
                        and finding["start"] + finding["length"]
                        <= start + len(defect["allowed_span"])
                        and defect["contains"] in quote
                        and set(defect["required_evidence"])
                        <= set(finding["evidence_ids"])
                        <= set(defect["allowed_evidence"])
                    ):
                        matches.add(index)
                assert matches
                covered.update(matches)
            assert covered == set(range(len(case["defects"])))
    assert len(seen) == 20 and all(seen.count(key) == 2 for key in cases)


@pytest.mark.parametrize("error", [OSError, RuntimeError, ValueError])
def test_host_exception_has_safe_failure_receipt(monkeypatch, error):
    def probe(*a, **kw):
        raise error("PRIVATE SENTINEL")

    monkeypatch.setattr(review, "run_probe", probe)
    result = review.review_packet(PACKET, model="fable")
    assert result["status"] == "review_unavailable"
    assert result["reason"] == "host_exception"
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize("error", [KeyboardInterrupt, SystemExit])
def test_cancellation_propagates_after_host_cleanup(monkeypatch, error):
    def probe(*a, **kw):
        raise error()

    monkeypatch.setattr(review, "run_probe", probe)
    with pytest.raises(error):
        review.review_packet(PACKET, model="fable")


@pytest.mark.parametrize("change", [{"answers": []}, {"result_count": 2}])
def test_incomplete_result_diagnostic_never_says_ok(monkeypatch, change):
    monkeypatch.setattr(review, "run_probe", lambda *a, **kw: host(**change))
    assert (
        review.review_packet(PACKET, model="fable")["reason"]
        == "incomplete_host_result"
    )
