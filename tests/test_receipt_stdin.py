"""CLI coverage for file-free evidence-receipt validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = {
    "schema_version": "1.0",
    "prompt_epoch": "epoch-001",
    "claim_id": "claim-001",
    "route_id": "route-001",
    "definition_id": "active-service-units",
    "source_refs": [
        {
            "source_id": "synthetic-source",
            "status": "unavailable",
            "observed_at": None,
            "scope_match": "unknown",
        }
    ],
    "scope": {
        "population": "fictional service units",
        "measure": "active service units",
        "time_window": "latest complete month",
        "grain": "account_month",
    },
    "freshness": {"status": "unknown", "basis": "No source was read."},
    "completeness": {"status": "unknown", "basis": "No source was read."},
    "conflict": {"status": "unknown", "basis": "No source was read."},
    "caveats": ["Synthetic fixture."],
    "claim_status": "withheld",
}


def test_receipt_validator_accepts_json_on_standard_input() -> None:
    script = (
        ROOT
        / "plugins"
        / "deterministic-data"
        / "scripts"
        / "validate_evidence_receipt.py"
    )

    result = subprocess.run(
        [sys.executable, str(script), "--expected-epoch", "epoch-001"],
        input=json.dumps(RECEIPT),
        capture_output=True,
        check=False,
        text=True,
    )

    output = json.loads(result.stdout)
    assert result.returncode == 0
    assert output["status"] == "pass"
    assert output["errors"] == []
    assert output["authority"] == "structural_only"


def test_receipt_validator_rejects_stdin_from_another_prompt_epoch() -> None:
    script = (
        ROOT
        / "plugins"
        / "deterministic-data"
        / "scripts"
        / "validate_evidence_receipt.py"
    )

    result = subprocess.run(
        [sys.executable, str(script), "--expected-epoch", "epoch-002"],
        input=json.dumps(RECEIPT),
        capture_output=True,
        check=False,
        text=True,
    )

    output = json.loads(result.stdout)
    assert result.returncode == 1
    assert output["status"] == "fail"
    assert output["errors"] == ["prompt_epoch_mismatch"]
    assert output["authority"] == "structural_only"
