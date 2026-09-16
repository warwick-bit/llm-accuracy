"""Evidence-receipt contract tests shared by both public plugins."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "plugins" / "llm-accuracy"
DATA = ROOT / "plugins" / "deterministic-data"


def load_validator(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.parent.parent.name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def valid_receipt(status: str = "supported") -> dict[str, object]:
    caveats = [] if status == "supported" else ["Synthetic qualification."]
    return {
        "schema_version": "1.0",
        "prompt_epoch": "epoch-001",
        "claim_id": "claim-001",
        "route_id": "route-001",
        "definition_id": "active-service-units",
        "source_refs": [
            {
                "source_id": "synthetic-source",
                "status": "success",
                "observed_at": "2026-01-01T00:00:00Z",
                "scope_match": "match",
            }
        ],
        "scope": {
            "population": "fictional active accounts",
            "measure": "active service units",
            "time_window": "latest complete month",
            "grain": "account_month",
        },
        "freshness": {"status": "current", "basis": "Synthetic fixture."},
        "completeness": {"status": "complete", "basis": "Synthetic fixture."},
        "conflict": {"status": "none", "basis": "Synthetic fixture."},
        "caveats": caveats,
        "claim_status": status,
    }


def validators() -> list[ModuleType]:
    return [
        load_validator(CORE / "scripts" / "validate_evidence_receipt.py"),
        load_validator(DATA / "scripts" / "validate_evidence_receipt.py"),
    ]


@pytest.mark.parametrize("status", ["supported", "qualified", "withheld", "unchecked"])
def test_receipt_statuses_validate(status: str) -> None:
    for validator in validators():
        assert validator.validate_receipt(valid_receipt(status)) == []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (lambda value: value["source_refs"][0].update(status="failed"), "supported_without_successful_source"),
        (lambda value: value["source_refs"][0].update(scope_match="mismatch"), "supported_without_scope_match"),
        (lambda value: value["freshness"].update(status="stale"), "supported_without_current_source"),
        (lambda value: value["completeness"].update(status="partial"), "supported_without_complete_coverage"),
        (lambda value: value["conflict"].update(status="present"), "supported_with_unresolved_conflict"),
    ],
)
def test_supported_claims_require_each_fidelity_dimension(mutation, expected: str) -> None:
    receipt = valid_receipt()
    mutation(receipt)

    for validator in validators():
        assert expected in validator.validate_receipt(receipt)


def test_prompt_epoch_is_answer_bound() -> None:
    for validator in validators():
        assert validator.validate_receipt(
            valid_receipt(), expected_epoch="epoch-002"
        ) == ["prompt_epoch_mismatch"]


def test_receipt_contracts_are_identical_between_plugins() -> None:
    assert (CORE / "references" / "evidence-receipt.schema.json").read_bytes() == (
        DATA / "references" / "evidence-receipt.schema.json"
    ).read_bytes()
    assert (CORE / "scripts" / "validate_evidence_receipt.py").read_bytes() == (
        DATA / "scripts" / "validate_evidence_receipt.py"
    ).read_bytes()


def test_cli_reports_structure_only_without_echoing_input(tmp_path: Path) -> None:
    receipt = valid_receipt()
    secret = "CANARY-RAW-DATA-MUST-NOT-ECHO"
    receipt["caveats"] = [secret]
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            str(CORE / "scripts" / "validate_evidence_receipt.py"),
            str(path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    output = json.loads(result.stdout)
    assert result.returncode == 0
    assert output["authority"] == "structural_only"
    assert "were not verified" in output["statement"]
    assert secret not in result.stdout
