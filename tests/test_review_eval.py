"""Executable oracle, malicious-operation and negative-scoring controls."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


TOOLS = module("review_eval_tools")
CASES = module("review_eval_cases")
RUNNER = module("run_review_eval")
SMOKE = module("smoke_analytical_review")


@pytest.mark.parametrize("expression", ["__import__('os')", "2**100000", "[1]*9", "True", "1/0"])
def test_calculator_rejects_execution_and_unbounded_operations(expression):
    result = TOOLS.tool_result({}, "calculate", {"expression": expression})
    assert result["isError"]
    assert expression not in json.dumps(result)


def test_decimal_calculator_avoids_binary_float_rounding():
    assert TOOLS.calculate("0.1 + 0.2") == "0.3"
    assert TOOLS.calculate("100 + 60 * 1.20") == "172.00"


@pytest.mark.parametrize("sql", ["DELETE FROM t", "DROP TABLE t", "ATTACH DATABASE '/tmp/x' AS x",
                                 "PRAGMA writable_schema=ON", "SELECT load_extension('x')",
                                 "SELECT randomblob(1000000000)", "SELECT printf('%1000000000s','x')"])
def test_query_rejects_mutations_and_file_access(sql):
    result = TOOLS.tool_result({"setup_sql": "CREATE TABLE t(x); INSERT INTO t VALUES (1);"},
                              "query", {"sql": sql})
    assert result["isError"]
    assert sql not in json.dumps(result)


def test_oracles_and_known_bad_outputs():
    inventory = CASES.cases()
    assert len({item["id"] for item in inventory}) == len(inventory)
    for item in inventory:
        good = {**item["gold"], "reason": "Synthetic scorer control", "checks": []}
        assert CASES.score(item, good)["objective_pass"]
        assert not CASES.score(item, {})["objective_pass"]
        assert not CASES.score(item, {"verdict": item["gold"]["verdict"]})["objective_pass"]
        wrong = {**good, "value": "999999"}
        assert not CASES.score(item, wrong)["objective_pass"]
        false_alarm = {**good, "verdict": "invented"}
        assert not CASES.score(item, false_alarm)["objective_pass"]
    by_id = {item["id"]: item for item in inventory}
    assert by_id["join-total"]["gold"]["value"] == "320"
    assert by_id["null-trap"]["gold"]["value"] == "3"
    assert by_id["retry-gap"]["gold"]["value"] == "40"


def test_decoder_rejects_process_error_even_with_correct_looking_body():
    with pytest.raises(ValueError):
        RUNNER.decode_answer(json.dumps({"type": "result", "is_error": True,
                                       "structured_output": {"verdict": "supported"}}))


def test_failed_runs_do_not_enter_quality_denominator():
    result = RUNNER.summarize([
        {"arm": "default", "status": "completed", "objective_pass": True, "seconds": 1},
        {"arm": "default", "status": "process_failure", "seconds": 2},
    ])
    assert result["default"] == {"completed": 1, "process_failures": 1,
                                 "objective_passes": 1, "seconds": 3}


@pytest.mark.parametrize("extra_tool,plugins", [("Bash", []), (None, [{"name": "unexpected"}])])
def test_effective_runtime_attestation_rejects_extra_capabilities(extra_tool, plugins):
    inventory = ["mcp__review__evidence", "mcp__review__query", "mcp__review__calculate"]
    if extra_tool:
        inventory.append(extra_tool)
    stream = "\n".join(json.dumps(event) for event in [
        {"type": "system", "subtype": "init", "tools": inventory, "plugins": plugins},
        {"type": "result", "structured_output": {
            "verdict": "supported", "value": "1", "reason": "test", "checks": []}},
    ])
    with pytest.raises(ValueError):
        RUNNER.decode_stream(stream, set())


def test_correct_number_with_false_prose_is_explicitly_unmeasured():
    item = CASES.cases()[0]
    answer = {**item["gold"], "reason": "An unrelated untrue explanation.", "checks": []}
    result = CASES.score(item, answer)
    assert result["objective_pass"]
    assert result["explanation_review"] == "not_measured"


def test_missing_skill_control_cannot_pass_on_runtime_failure():
    assert not SMOKE.control_passed({"status": "process_failure", "passed": False}, True)
    assert SMOKE.control_passed({"status": "completed", "target_skill_invoked": True,
                                 "target_skill_succeeded": False, "passed": False}, True)
