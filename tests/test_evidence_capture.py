"""Negative controls for the experimental observation path and its receipts."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.fixture
def packet(tmp_path):
    smoke = module("evidence_capture_smoke")
    config, source, _, _ = smoke.prepare(tmp_path, True)
    payload = {
        "hook_event_name": "PostToolUse", "tool_name": "Read",
        "tool_input": {"file_path": config["fixture"]},
        "tool_response": {"file": {"content": config["content"]}},
    }
    return config, source, payload


def test_observation_does_not_modify_or_echo_payload(packet):
    config, _, payload = packet
    original = copy.deepcopy(payload)
    output, observation = module("capture_observation").handle(payload, config)
    assert payload == original
    assert module("evidence_capture_smoke").observation_valid(observation)
    assert config["marker"] in output["hookSpecificOutput"]["additionalContext"]
    assert "updatedToolOutput" not in json.dumps(output)
    assert config["content"] not in json.dumps(observation)
    assert config["fixture"] not in json.dumps(observation)


@pytest.mark.parametrize("response", [None, {}, "text", {"file": {}},
                                     {"file": {"content": "wrong"}},
                                     {"file": {"content": True}}])
def test_unknown_truncated_or_wrong_content_never_emits(packet, response):
    config, _, payload = packet
    payload["tool_response"] = response
    output, observation = module("capture_observation").handle(payload, config)
    assert output == {}
    assert not module("evidence_capture_smoke").observation_valid(observation)


@pytest.mark.parametrize("tool,path", [("Bash", "sample.txt"), ("Read", "../profile/observer.json"),
                                      ("Read", "/unrelated/file"), ("Read", None)])
def test_isolation_rejects_unexpected_tools_and_paths(packet, tool, path):
    config, _, payload = packet
    payload.update(hook_event_name="PreToolUse", tool_name=tool, tool_input={"file_path": path})
    output, observation = module("capture_observation").handle(payload, config)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert observation is None


def test_control_observes_without_delivering(packet):
    config, _, payload = packet
    config["emit"] = False
    output, observation = module("capture_observation").handle(payload, config)
    assert output == {}
    assert module("evidence_capture_smoke").observation_valid(observation)


def completed_result(answer):
    return {
        "status": "ok", "answers": [answer], "result_count": 1,
        "fidelity_hook_responses": 1, "resolved_model": "claude-synthetic",
        "host_inventory": {"status": "reported", "accuracy_plugin_count": 1, "mcp_count": 0},
    }


@pytest.mark.parametrize("emit", [False, True])
def test_delivery_scorer_positive_and_wrong_answer_controls(packet, emit):
    config, source, payload = packet
    smoke = module("evidence_capture_smoke")
    observation = module("capture_observation").observe(payload, config)
    answer = "Source: " + source + "\nObservation: " + (config["marker"] if emit else "none")
    result = completed_result(answer)
    assert smoke.assess(result, observation, source, config["marker"], emit)["passed"]
    wrong_arm = "Source: " + source + "\nObservation: " + ("none" if emit else config["marker"])
    for wrong in ("", "Source: invented\nObservation: invented", answer + "\nObservation: none", wrong_arm):
        assert not smoke.assess(completed_result(wrong), observation, source, config["marker"], emit)["passed"]
    result["status"] = "timeout"
    assert not smoke.assess(result, observation, source, config["marker"], emit)["passed"]
    assert not smoke.assess(completed_result(answer), None, source, config["marker"], emit)["passed"]


def test_summary_requires_two_completed_matching_models():
    smoke = module("evidence_capture_smoke")
    good = {"passed": True, "resolved_model": "claude-synthetic"}
    assert not smoke.summarize({"silent_control": good})["passed"]
    assert smoke.summarize({"silent_control": good, "observation_context": good})["passed"]
    assert not smoke.summarize({"silent_control": good, "observation_context": {
        "passed": True, "resolved_model": "unreported",
    }})["passed"]


def test_hook_cli_malformed_input_fails_without_echoing(tmp_path):
    config = tmp_path / "config.json"
    config.write_text("{}")
    result = subprocess.run([sys.executable, str(ROOT / "scripts/capture_observation.py"), str(config)],
                            input="not-json-private-sentinel", text=True, capture_output=True)
    assert result.returncode == 2
    assert result.stdout == result.stderr == ""


def test_baseline_executable_oracle_and_case_integrity():
    baseline = module("accuracy_baseline_cases")
    assert baseline.retry_trace("before") == {"responses": [503], "passed": False}
    assert baseline.retry_trace("after") == {"responses": [503, 200], "passed": True}
    assert not baseline.retry_trace("after", (503, 503))["passed"]
    suite = baseline.cases()
    baseline.validate_cases(suite)
    assert len(suite) == 10
    for case in suite:
        assert "oracle" not in case["model_input"]
    positive = next(case for case in suite if case["id"] == "reproduction_pass")
    files = positive["model_input"]["files"]
    assert not json.loads(files["before.json"])["trace"]["passed"]
    assert json.loads(files["after.json"])["trace"]["passed"]
    with pytest.raises(ValueError):
        baseline.validate_cases([suite[0], suite[0]])
