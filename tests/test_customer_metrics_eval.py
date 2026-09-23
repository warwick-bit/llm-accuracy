import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("customer_eval", ROOT / "scripts/eval_customer_metrics.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def answer():
    return {"decision": "needs_correction", "verified_metrics": [
        {"customer_id": 100, "number_of_orders": 2, "customer_lifetime_value": 90},
        {"customer_id": 101, "number_of_orders": 1, "customer_lifetime_value": 70},
        {"customer_id": 102, "number_of_orders": None, "customer_lifetime_value": None}],
        "Checked": "Synthetic test.", "Gap": "Fixture only.", "Next": "None."}


def scored(value):
    fixture = json.loads((module.EXAMPLE / "fixture.json").read_text())
    return module.score(json.dumps(value), module.expected_rows(fixture), "needs_correction")


def test_correct_answer_and_reordering_are_equivalent():
    value = answer()
    assert scored(value)["all_scored_fields_correct"]
    value["verified_metrics"].reverse()
    assert scored(value)["all_scored_fields_correct"]


@pytest.mark.parametrize("mutation", ["verdict", "count", "value", "omit", "duplicate", "misattribute", "null_zero"])
def test_wrong_answers_fail_actual_scorer(mutation):
    value = answer()
    rows = value["verified_metrics"]
    if mutation == "verdict":
        value["decision"] = "supported"
    elif mutation == "count":
        rows[0]["number_of_orders"] = 3
    elif mutation == "value":
        rows[0]["customer_lifetime_value"] = 91
    elif mutation == "omit":
        rows.pop()
    elif mutation == "duplicate":
        rows.append(dict(rows[0]))
    elif mutation == "misattribute":
        rows[0]["customer_id"], rows[1]["customer_id"] = rows[1]["customer_id"], rows[0]["customer_id"]
    else:
        rows[2]["number_of_orders"] = 0
    result = scored(value)
    assert result["scorable"] and not result["all_scored_fields_correct"]


def test_malformed_answer_is_not_scored_as_a_quality_failure():
    assert module.score("not JSON", [], "supported") == {"scorable": False, "failure": "answer_shape"}
    value = answer()
    value["verified_metrics"][0]["number_of_orders"] = True
    assert not scored(value)["scorable"]


def test_prompt_avoids_provenance_labels_and_adds_only_executed_report():
    fixture = json.loads((module.EXAMPLE / "fixture.json").read_text())
    sql = (module.EXAMPLE / "joined_customers.sql").read_text()
    prompts = {a: module.make_prompt(sql, fixture, a) for a in module.ARMS}
    for text in prompts.values():
        assert "Locally authored mutation" not in text
        assert "joined_customers.sql" not in text
        assert "upstream_customers.sql" not in text
    packets = {a: json.loads(p.split("\nPACKET\n")[1]) for a, p in prompts.items()}
    report = packets["executed_checks"].pop("executed_check_report")
    assert report == module.check(sql, fixture)
    assert packets["existing"] == packets["executed_checks"]


def test_runtime_drift_fails_closed():
    result = {"status": "ok", "resolved_model": "claude-sonnet-5", "result_count": 1,
              "answers": ["{}"], "fidelity_hook_responses": 1,
              "successful_fidelity_hooks": 1, "usage_model_matches": True,
              "host_inventory": {"status": "reported", "tool_count": 0, "mcp_count": 0,
                                 "plugin_count": 2, "accuracy_plugin_count": 1, "telemetry_plugin_count": 1}}
    assert module.attest(result, "claude-sonnet-5")
    result["host_inventory"]["tool_count"] = 1
    assert not module.attest(result, "claude-sonnet-5")


@pytest.mark.parametrize("mutation", ["none", "failed_hook", "stop_hook", "wrong_usage", "bad_trace"])
def test_attestation_checks_actual_hook_outcome_and_final_usage(mutation):
    events = [
        {"type": "system", "subtype": "init", "model": "claude-sonnet-5", "tools": [], "mcp_servers": [],
         "plugins": [{"name": "telemetry"}, {"name": "llm-accuracy"}]},
        {"type": "system", "subtype": "hook_response", "hook_event": "UserPromptSubmit",
         "outcome": "success", "exit_code": 0, "stdout": "CLAIM FIDELITY CHECK"},
        {"type": "result", "subtype": "success", "modelUsage": {"claude-sonnet-5": {}}, "result": "{}"}]
    if mutation == "failed_hook":
        events[1].update(exit_code=1, outcome="error")
    elif mutation == "stop_hook":
        events[1]["hook_event"] = "Stop"
    elif mutation == "wrong_usage":
        events[2]["modelUsage"] = {"claude-other": {}}
    trace = "\n".join(json.dumps(e) for e in events)
    if mutation == "bad_trace":
        trace += "\nnot-json"
    result = module.parse_attested(trace, "", 0, "claude-sonnet-5", module.host_probe.parse_events)
    assert module.attest(result, "claude-sonnet-5") is (mutation == "none")


def test_scoped_parser_is_restored_on_failure(monkeypatch):
    original = module.host_probe.parse_events

    def failure(*args, **kwargs):
        assert module.host_probe.parse_events is not original
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(module.host_probe, "run_probe", failure)
    with pytest.raises(RuntimeError):
        module.run_review("synthetic", "claude-sonnet-5")
    assert module.host_probe.parse_events is original
