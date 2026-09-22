"""Counterexample, coverage, abstention and explanation-control tests."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from calibrate_review_judge import control_matches, controls, reference_answer  # noqa: E402
from review_challenge_cases import challenge_cases  # noqa: E402
from review_eval_tools import query  # noqa: E402
from review_explanation_judge import observations, validate_grade  # noqa: E402
from run_review_challenge import score_challenge, summarize_challenge, validate_answer  # noqa: E402


def test_reference_values_and_offsetting_join_counterexample():
    cases = {item["id"]: item for item in challenge_cases()}
    item = cases["packet-a"]
    wrong = query(item["fixture"], "SELECT o.id, SUM(l.amount)-SUM(r.amount) net FROM orders o "
                  "JOIN lines l ON l.order_id=o.id JOIN refunds r ON r.order_id=o.id GROUP BY o.id")["rows"]
    assert wrong == [("o1", -100), ("o2", 190)]
    assert sum(row[1] for row in wrong) == int(item["gold"]["a1"]["value"]) == 90
    assert item["gold"]["a3"]["value"] == "0"
    assert cases["packet-b"]["gold"]["b2"]["value"] == "270.00"
    assert cases["packet-c"]["gold"]["c1"]["value"] == "100"
    assert cases["packet-d"]["gold"]["d1"]["value"] == "50.0"
    assert cases["packet-e"]["gold"]["e2"]["value"] == "85.00"
    assert cases["packet-f"]["gold"]["f1"]["value"] == "50"


def test_missing_duplicate_wrong_and_invented_claims_cannot_pass():
    for item in challenge_cases():
        answer = reference_answer(item)
        validate_answer(answer)
        assert score_challenge(item, answer)["objective_pass"]
        answer["claims"].pop()
        assert not score_challenge(item, answer)["objective_pass"]
        answer = reference_answer(item)
        answer["claims"].append(answer["claims"][0])
        assert not score_challenge(item, answer)["objective_pass"]
        answer = reference_answer(item)
        answer["claims"][0]["value"] = "999999"
        assert not score_challenge(item, answer)["objective_pass"]
        answer = reference_answer(item)
        answer["claims"][0]["id"] = "invented"
        assert not score_challenge(item, answer)["objective_pass"]


def test_wrong_explanation_controls_preserve_correct_values():
    for control in controls():
        assert score_challenge(control["item"], control["answer"])["objective_pass"]
        assert not control_matches(control, {"judge_status": "process_failure"})


def test_unjudgeable_is_not_a_calibration_pass():
    control = controls()[1]
    assert not control_matches(control, {"judge_status": "completed", "explanation_grades": {
        "claims": [{"id": control["target"], "explanation": "unjudgeable"}]}})


def test_tool_observations_exclude_model_prose_and_instructions():
    events = [
        {"message": {"content": [{"type": "text", "text": "private model prose"},
            {"type": "tool_use", "id": "synthetic-call", "name": "mcp__review__calculate", "input": {"expression": "1+2"}}]}},
        {"message": {"content": [{"type": "tool_result", "tool_use_id": "synthetic-call", "content": "3"}]}},
    ]
    result = observations("\n".join(json.dumps(e) for e in events))
    assert result == [{"tool": "mcp__review__calculate", "input": {"expression": "1+2"}, "result": "3", "is_error": False}]
    assert "private" not in json.dumps(result)


def test_malformed_judge_result_rejected():
    with pytest.raises(ValueError):
        validate_grade({"claims": []})


def test_failure_denominators_and_partial_coverage_are_separate():
    item = challenge_cases()[0]
    answer = reference_answer(item)
    answer["claims"].pop()
    row = {"arm": "default", "status": "completed", "seconds": 1, **score_challenge(item, answer)}
    summary = summarize_challenge([row, {"arm": "default", "status": "process_failure", "seconds": 1}])["default"]
    assert summary["completed_cases"] == 1
    assert summary["process_failures"] == 1
    assert summary["verdict_value_matches"] == 3
    assert summary["coverage_failures"] == 1
    assert summary["judge_failures"] == 1
