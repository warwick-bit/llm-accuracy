"""Receipt metadata controls, not adapter or model accuracy tests."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = json.loads((ROOT / "tests/fixtures/tool_failure_receipts.json").read_text())


@pytest.fixture(params=["llm-accuracy", "deterministic-data"])
def validator(request):
    path = ROOT / "plugins" / request.param / "scripts/validate_evidence_receipt.py"
    spec = importlib.util.spec_from_file_location("receipt_validator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("case", FIXTURES["failure_cases"], ids=lambda case: case["case"])
def test_failure_receipt_validates_without_becoming_supported(validator, case):
    receipt = copy.deepcopy(case["receipt"])
    assert validator.validate_receipt(receipt, expected_epoch="fictional-turn-a") == []
    assert receipt["claim_status"] == "withheld"
    receipt["claim_status"] = "supported"
    assert sorted(validator.validate_receipt(receipt)) == case["supported_errors"]


def test_healthy_metadata_control(validator):
    assert validator.validate_receipt(
        FIXTURES["healthy_receipt"], expected_epoch="fictional-turn-a"
    ) == []


def test_old_receipt_cannot_satisfy_new_host_epoch(validator):
    assert validator.validate_receipt(
        FIXTURES["healthy_receipt"], expected_epoch="fictional-turn-b"
    ) == ["prompt_epoch_mismatch"]


def test_failed_refresh_receipt_can_describe_the_current_failed_attempt(validator):
    receipt = copy.deepcopy(next(
        case["receipt"] for case in FIXTURES["failure_cases"]
        if case["case"] == "failed_refresh"
    ))
    receipt["prompt_epoch"] = "fictional-turn-b"
    assert validator.validate_receipt(receipt, expected_epoch="fictional-turn-b") == []
    assert receipt["claim_status"] == "withheld"


def test_invented_source_can_pass_structure_limitation_control(validator):
    receipt = copy.deepcopy(FIXTURES["healthy_receipt"])
    receipt["source_refs"][0]["source_id"] = "fictional-invented-source-not-contacted"
    errors = validator.validate_receipt(receipt)
    assert errors == []
    assert validator.result(errors)["authority"] == "structural_only"


def test_relabelling_epoch_does_not_prove_a_new_read_limitation_control(validator):
    receipt = copy.deepcopy(FIXTURES["healthy_receipt"])
    receipt["prompt_epoch"] = "fictional-turn-b"
    assert validator.validate_receipt(receipt, expected_epoch="fictional-turn-b") == []
    # Only an external trusted host can establish that a new read really occurred.
