"""Measurement and isolation controls for the free-form comparison."""

import argparse
import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import review_everyday_extract as extraction
import run_review_everyday as runner


def item():
    return {"gold": [{"id": "x", "claim": "The net amount is 40.", "status": "refuted", "value": "30"}],
            "fixture": {"sources": {"private_gold_context": "never sent to extractor"}}}


def answer(status="refuted", value="30", evidence_lines=None):
    return {"claims": [{"id": "x", "status": status, "value": value,
                        "evidence_lines": [1] if evidence_lines is None else evidence_lines, "representation": "canonical"}]}


def test_extractor_does_not_receive_gold_or_sources():
    payload = extraction.extraction_payload(item(), "Actually 30, not 40.")
    assert payload == {"claims": [{"id": "x", "claim": "The net amount is 40.", "numeric_target": True, "numeric_unit": "as stated in claim"}],
                       "review_lines": [{"id": 1, "text": "Actually 30, not 40."}]}


@pytest.mark.parametrize("status,value", [("supported", "40"), ("refuted", "35"), ("omitted", None), ("ambiguous", None)])
def test_known_wrong_outputs_fail_score(status, value):
    assert not extraction.score_extraction(answer(status, value), item())["all_claims_match"]


def test_valid_paraphrase_and_number():
    review = "Actually 30, not 40."
    extraction.validate_extraction(answer(), item(), review)
    assert extraction.score_extraction(answer(), item())["all_claims_match"]


def test_scoped_approval_need_not_restate_correct_number():
    correct = item()
    correct["gold"][0].update(status="supported", value="40")
    assert extraction.score_extraction(answer("supported", None), correct)["all_claims_match"]
    assert not extraction.score_extraction(answer("supported", "35"), correct)["all_claims_match"]
    assert not extraction.score_extraction(answer("refuted", None), item())["all_claims_match"]


@pytest.mark.parametrize("unit,kind,raw,expected", [
    ("percentage", "fraction", "0.5", "50"),
    ("signed profit", "loss_magnitude", "3000", "-3000"),
    ("total charges", "additional_count", "2", "3"),
])
def test_unit_normalization_preserves_meaning(unit, kind, raw, expected):
    row = dict(value=raw, representation=kind)
    assert extraction.equal_value(extraction.normalize(row, {"numeric_unit": unit}), expected)
    with pytest.raises(ValueError):
        extraction.normalize(row, {"numeric_unit": "as stated in claim"})


def test_wrong_profit_sign_still_fails():
    assert not extraction.equal_value(extraction.normalize(
        {"value": "3000", "representation": "canonical"}, {"numeric_unit": "signed profit"}), "-3000")
    assert extraction.equal_value("30.00", "30")


@pytest.mark.parametrize("change", ["invent_lines", "missing", "duplicate", "nan", "huge", "omit_lines"])
def test_invalid_extractions_rejected(change):
    response = answer()
    if change == "invent_lines":
        response["claims"][0]["evidence_lines"] = [2]
    elif change == "missing":
        response["claims"] = []
    elif change == "duplicate":
        response["claims"] *= 2
    elif change == "nan":
        response["claims"][0]["value"] = "NaN"
    elif change == "huge":
        response["claims"][0]["value"] = "1e9999999"
    elif change == "omit_lines":
        response["claims"][0]["status"] = "omitted"
    with pytest.raises(ValueError):
        extraction.validate_extraction(response, item(), "Actually 30, not 40.")


def args():
    return argparse.Namespace(claude_binary="claude", model="claude-sonnet-5", extractor_model="claude-sonnet-5",
                              effort="high", host_plugins=["telemetry", "agents-md"])


def events(plugin=False):
    names = ["telemetry", "agents-md"] + (["llm-accuracy"] if plugin else [])
    data = [{"type": "system", "subtype": "init", "model": "claude-sonnet-5",
             "plugins": [{"name": n} for n in names], "tools": sorted(runner.TOOLS)},
            {"type": "result", "result": "Actually 30, not 40.", "modelUsage": {"claude-sonnet-5": {}}}]
    if plugin:
        data.append({"type": "system", "subtype": "hook_response", "stdout": "CLAIM FIDELITY CHECK",
                     "hook_event": "UserPromptSubmit", "hook_name": "UserPromptSubmit:2", "exit_code": 0, "outcome": "success"})
    return data


def encoded(data):
    return "\n".join(json.dumps(e) for e in data)


def test_review_has_no_claim_schema_or_gold():
    cmd = runner.command(args())
    assert "--json-schema" not in cmd
    assert "--json-schema" in runner.command(args(), True)
    assert runner.prompts()["default"] == runner.TASK


@pytest.mark.parametrize("plugin", [True, False])
def test_inventory_positive_control(plugin):
    result, metadata = runner.parse(encoded(events(plugin)), 0, args(), plugin=plugin)
    assert result == "Actually 30, not 40."
    assert metadata["fidelity_hook_responses"] == int(plugin)


@pytest.mark.parametrize("change", ["plugin", "tools", "model", "missing_init", "missing_result", "error"])
def test_inventory_negative_controls(change):
    data = copy.deepcopy(events())
    if change == "plugin":
        data[0]["plugins"].append({"name": "surprise"})
    elif change == "tools":
        data[0]["tools"].append("Bash")
    elif change == "model":
        data[1]["modelUsage"] = {"different": {}}
    elif change == "missing_init":
        data = data[1:]
    elif change == "missing_result":
        data = data[:1]
    else:
        data[1]["is_error"] = True
    with pytest.raises(ValueError):
        runner.parse(encoded(data), 0, args())


def test_plugin_missing_hook_is_not_quality_failure():
    with pytest.raises(ValueError, match="hook_activation_failure"):
        runner.parse(encoded(events(True)[:2]), 0, args(), plugin=True)


def test_receipt_never_retains_raw_quote_or_value():
    scored = extraction.score_extraction(answer(), item())
    assert "quote" not in scored["claims"][0]
    assert "value" not in scored["claims"][0]
    assert "Actually" not in json.dumps(scored)


@pytest.mark.parametrize("selected", [[0], [3], [True], [1, 1], [2], []])
def test_invalid_line_references_fail(selected):
    with pytest.raises(ValueError):
        extraction.validate_extraction(answer(evidence_lines=selected), item(), "Actual evidence.\n \n")


def test_multiline_evidence_requires_no_quote_reconstruction():
    response = answer(evidence_lines=[1, 3])
    extraction.validate_extraction(response, item(), "**Net:** 30.\n\nNot the reported `40`.")


@pytest.mark.parametrize("key,value", [("exit_code", 1), ("outcome", "error"), ("hook_event", "Stop")])
def test_failed_or_wrong_hook_does_not_attest_activation(key, value):
    data = events(True)
    data[-1][key] = value
    with pytest.raises(ValueError, match="hook_activation_failure"):
        runner.parse(encoded(data), 0, args(), plugin=True)


def test_truncated_tool_trace_preserves_failure_row(monkeypatch):
    def fake_call(args, work, cmd, prompt, **kwargs):
        (work / "trace.jsonl").write_text('{"tool":')
        return None, {"status": "process_failure", "failure": "timeout"}
    monkeypatch.setattr(runner, "call", fake_call)
    case = {"id": "synthetic", "domain": "data", "fixture": {"sources": {}, "setup_sql": ""}}
    result = runner.review(case, "default", args())
    assert result["review"]["status"] == "process_failure"
    assert result["review"]["failure"] == "timeout"
    assert result["review"]["trace_failure"] == "invalid_tool_trace"


def test_extraction_retries_bad_lines_once_with_same_prompt(monkeypatch):
    prompts = []
    def fake_call(args, work, cmd, prompt, **kwargs):
        prompts.append(prompt)
        return answer(evidence_lines=[2] if len(prompts) == 1 else [1]), {"status": "completed"}
    monkeypatch.setattr(runner, "call", fake_call)
    result, receipt = runner.extract(item(), "Actually 30, not 40.", args())
    assert result is not None and len(prompts) == 2 and prompts[0] == prompts[1]
    assert receipt["attempts"][0]["failure"] == "extract_lines"
    assert receipt["status"] == "completed"


def test_valid_wrong_extraction_is_never_retried(monkeypatch):
    calls = []
    def fake_call(*args, **kwargs):
        calls.append(1)
        return answer("supported", "40"), {"status": "completed"}
    monkeypatch.setattr(runner, "call", fake_call)
    result, receipt = runner.extract(item(), "Actually 30, not 40.", args())
    assert len(calls) == 1 and receipt["status"] == "completed"
    assert not extraction.score_extraction(result, item())["all_claims_match"]


def test_scoped_control_accepts_endorsed_value_not_arbitrary_number():
    control = next(c for c in extraction.calibration_cases() if c["id"] == "scoped_all_clear")
    gold = control["gold"][0]
    assert runner.calibration_value_matches(answer("supported", "40")["claims"][0], gold, None, control)
    assert not runner.calibration_value_matches(answer("supported", "35")["claims"][0], gold, None, control)


def test_hook_display_name_does_not_replace_event_success_and_marker():
    data = events(True)
    data[-1]["hook_name"] = "Checking llm-accuracy claim fidelity"
    _, receipt = runner.parse(encoded(data), 0, args(), plugin=True)
    assert receipt["fidelity_hook_responses"] == 1


def test_python39_temp_directory_compatibility(monkeypatch):
    seen = []
    monkeypatch.setattr(runner.sys, "version_info", (3, 9))
    monkeypatch.setattr(runner.tempfile, "TemporaryDirectory", lambda **kwargs: seen.append(kwargs))
    runner.temporary_directory("offline-test-")
    assert seen == [{"prefix": "offline-test-"}]
