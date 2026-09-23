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


def answer(status="refuted", value="30", quote="Actually 30, not 40."):
    return {"claims": [{"id": "x", "status": status, "value": value, "quote": quote, "representation": "canonical"}]}


def test_extractor_does_not_receive_gold_or_sources():
    payload = extraction.extraction_payload(item(), "Actually 30, not 40.")
    assert payload == {"claims": [{"id": "x", "claim": "The net amount is 40.", "numeric_target": True, "numeric_unit": "as stated in claim"}],
                       "review": "Actually 30, not 40."}


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


@pytest.mark.parametrize("change", ["invent_quote", "missing", "duplicate", "nan", "omit_quote"])
def test_invalid_extractions_rejected(change):
    response = answer()
    if change == "invent_quote":
        response["claims"][0]["quote"] = "fabricated"
    elif change == "missing":
        response["claims"] = []
    elif change == "duplicate":
        response["claims"] *= 2
    elif change == "nan":
        response["claims"][0]["value"] = "NaN"
    elif change == "omit_quote":
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
        data.append({"type": "system", "subtype": "hook_response", "stdout": "CLAIM FIDELITY CHECK"})
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


def test_quote_matching_accepts_formatting_not_changed_claim():
    assert extraction.quote_matches("A loss of 3000", "A **loss** of\n`3000`")
    assert not extraction.quote_matches("A profit of 3000", "A **loss** of 3000")
    assert not extraction.quote_matches("Profit 3000", "Profit -3000")
