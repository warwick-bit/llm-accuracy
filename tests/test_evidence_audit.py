"""Consumer checks for compact evidence, refused checks and final saved bytes."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/llm-accuracy/skills/verify/scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location(
    "evidence_audit", ROOT / "tools/verify-audit/audit_answer.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
CLAIM = "If gross increases by10 and deductions stay fixed, net increases by10."


def evidence():
    return {
        "checks": [
            {
                "quote": CLAIM,
                "verdict": "supported",
                "scenario_inputs": {"gross": 900, "deductions": 90},
                "equations": ["900-90=810", "(910-90)-(900-90)=10"],
                "invariant": "delta net = delta gross - delta deductions = 10 - 0 = 10",
                "explanation": "A low blend follows only if improvements are small.",
            }
        ]
    }


def final():
    return {
        "claims": [
            {"quote": CLAIM, "verdict": "supported", "reason": "Delta net=10-0=10."}
        ],
        "conclusion": "The conditional is valid.",
        "limits": ["No actual increase is observed."],
    }


def inputs(tmp_path):
    source = tmp_path / "source.md"
    source.write_text("Gross900, total deductions90.", encoding="utf8")
    candidate = tmp_path / "candidate.md"
    candidate.write_text(CLAIM, encoding="utf8")
    output = tmp_path / "audit"
    return (
        source,
        candidate,
        output,
        [
            "--source",
            str(source),
            "--candidate",
            str(candidate),
            "--output-dir",
            str(output),
        ],
    )


def test_compaction_drops_verified_historical_commentary_defect():
    value = audit.compact_evidence(evidence(), CLAIM)
    assert "small" not in json.dumps(value)
    assert value["checks"][0]["executed_equations"]["status"] == "pass"
    assert "not source authority" in value["origin"]
    assert "does not verify its origin or independence" in value["origin"]


@pytest.mark.parametrize("bad", ["(910-90)-(900-90)=11", "23/28=0.82143"])
def test_false_or_wrong_precision_equations_are_refused(bad):
    value = evidence()
    value["checks"][0]["equations"] = [bad]
    with pytest.raises(ValueError, match="did not all pass"):
        audit.compact_evidence(value, CLAIM)


def test_quotes_and_nonfinite_scenario_values_are_refused():
    with pytest.raises(ValueError, match="not bound"):
        audit.compact_evidence(evidence(), "Different original claim.")
    value = evidence()
    value["checks"][0]["scenario_inputs"]["gross"] = float("inf")
    with pytest.raises(ValueError, match="named numbers"):
        audit.compact_evidence(value, CLAIM)


def test_empty_evidence_cannot_skip_an_explicit_conditional():
    with pytest.raises(ValueError, match="omitted an explicit if-marker"):
        audit.compact_evidence({"checks": []}, CLAIM)
    assert audit.compact_evidence({"checks": []}, "Net is810.")["checks"] == []


def test_missing_input_is_unavailable_not_a_completed_audit(tmp_path):
    source, candidate, out, args = inputs(tmp_path)
    source.unlink()
    assert audit.main(args) == 2 and not (out / "completion.json").exists()
    assert json.loads((out / "STOP.json").read_text())["status"] == "unavailable"


def test_actual_consumer_saves_and_inspects_valid_final_bytes(tmp_path, monkeypatch):
    source, candidate, out, args = inputs(tmp_path)
    before = (source.read_bytes(), candidate.read_bytes())
    calls = []

    def client(*a):
        calls.append(a)
        return (evidence() if len(calls) == 1 else final()), {"exit": 0}

    monkeypatch.setattr(audit.shutil, "which", lambda x: "existing-client")
    monkeypatch.setattr(audit, "call_client", client)
    assert audit.main(args) == 0 and len(calls) == 2
    assert "small" not in json.dumps(calls[1][4]["compact_evidence"])
    inspected = json.loads((out / "inspection.json").read_text())
    assert inspected["files"][0]["text"] == (out / "audit.json").read_text()
    assert (
        inspected["files"][0]["sha256"]
        == json.loads((out / "completion.json").read_text())["saved_audit_sha256"]
    )
    assert before == (source.read_bytes(), candidate.read_bytes())
    with pytest.raises(FileExistsError):
        audit.main(args)


@pytest.mark.parametrize(
    "defect", ["arithmetic", "source_change", "client_unavailable", "malformed"]
)
def test_failure_stops_before_second_call_without_completed_audit(
    tmp_path, monkeypatch, defect
):
    source, candidate, out, args = inputs(tmp_path)
    calls = []

    def client(*a):
        calls.append(a)
        value = evidence()
        if defect == "client_unavailable":
            raise ValueError("quota unavailable")
        if defect == "source_change":
            source.write_text("changed")
        if defect == "arithmetic":
            value["checks"][0]["equations"] = ["2+2=5"]
        if defect == "malformed":
            del value["checks"][0]["quote"]
        return value, {"exit": 0}

    monkeypatch.setattr(audit.shutil, "which", lambda x: "existing-client")
    monkeypatch.setattr(audit, "call_client", client)
    assert audit.main(args) == 2 and len(calls) == 1
    assert not (out / "audit.json").exists() and not (out / "completion.json").exists()
    assert json.loads((out / "STOP.json").read_text())["retry"] is False


def test_false_final_quote_is_not_published(tmp_path, monkeypatch):
    source, candidate, out, args = inputs(tmp_path)
    calls = []

    def client(*a):
        calls.append(a)
        if len(calls) == 1:
            return evidence(), {"exit": 0}
        value = final()
        value["claims"][0]["quote"] = "Invented target."
        return value, {"exit": 0}

    monkeypatch.setattr(audit.shutil, "which", lambda x: "existing-client")
    monkeypatch.setattr(audit, "call_client", client)
    assert audit.main(args) == 2 and not (out / "audit.json").exists()


def test_native_client_launch_is_hidden_and_preserves_windows_discovery(
    tmp_path, monkeypatch
):
    seen = {}

    def run(cmd, **kwargs):
        seen.update(kwargs)
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd, 0, json.dumps({"is_error": False, "structured_output": final()}), ""
        )

    monkeypatch.setattr(audit.subprocess, "run", run)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "selected-personal-home")
    monkeypatch.setenv("PATHEXT", ".EXE;.CMD")
    monkeypatch.setenv("COMSPEC", "selected-cmd.exe")
    monkeypatch.setenv("CLAUDECODE", "nested")
    audit.call_client(
        "native-claude",
        "sonnet",
        "medium",
        "check",
        {},
        audit.AUDIT_SCHEMA,
        60,
        tmp_path,
    )
    assert seen["creationflags"] == (
        subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )
    assert (
        seen["env"]["PATHEXT"] == ".EXE;.CMD"
        and seen["env"]["COMSPEC"] == "selected-cmd.exe"
    )
    assert (
        seen["env"]["CLAUDE_CONFIG_DIR"] == "selected-personal-home"
        and "CLAUDECODE" not in seen["env"]
    )
    assert seen["cmd"][seen["cmd"].index("--tools") + 1] == ""
