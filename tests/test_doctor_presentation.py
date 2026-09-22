"""Synthetic diagnostic states must not become broader runtime claims."""

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def doctor(monkeypatch):
    scripts = ROOT / "plugins/llm-accuracy/scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "doctor_presentation_test", scripts / "accuracy_doctor.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(**updates):
    return {
        "status": "ok",
        "package_version": "0.6.1",
        "hook_commands": {
            "analysis": "emitted",
            "fusion_evidence": "emitted",
            "claim_fidelity": "emitted",
        },
        "host_registration": {
            "status": "listed",
            "installations": [{"version": "0.6.1", "enabled": True}],
        },
        **updates,
    }


@pytest.mark.parametrize("status", ["ok", "attention"])
def test_offline_presentation_keeps_current_activation_unverified(doctor, status):
    value = doctor.presentation(report(status=status))
    assert set(value) == {"status", "headline", "checked", "gap", "next"}
    assert all(isinstance(v, str) and v.strip() for v in value.values())
    assert "current-session activation" in value["gap"].lower()
    assert "unverified" in value["gap"]
    assert "accuracy" in value["gap"]
    assert "not run" in value["checked"]
    assert ("need attention" in value["headline"]) == (status == "attention")


@pytest.mark.parametrize(
    "live,passed",
    [
        (
            {
                "status": "ok",
                "fidelity_hook_responses": 1,
                "acknowledgement_correct": True,
            },
            True,
        ),
        (
            {
                "status": "ok",
                "fidelity_hook_responses": 0,
                "acknowledgement_correct": True,
            },
            False,
        ),
        (
            {
                "status": "ok",
                "fidelity_hook_responses": 1,
                "acknowledgement_correct": False,
            },
            False,
        ),
        (
            {
                "status": "authentication",
                "fidelity_hook_responses": 0,
                "acknowledgement_correct": False,
            },
            False,
        ),
    ],
)
def test_live_success_requires_delivery_and_acknowledgement(doctor, live, passed):
    value = doctor.presentation(
        report(live=live, status="ok" if passed else "attention")
    )
    assert ("isolated live check passed" in value["checked"]) == passed
    assert "current-session activation" in value["gap"].lower()
    assert "factual accuracy" in value["gap"].lower()


@pytest.mark.parametrize(
    "outcome", ["disabled", "shell_unavailable", "timeout", "invalid_response"]
)
def test_failed_or_disabled_commands_are_not_counted_as_emitted(doctor, outcome):
    value = doctor.presentation(
        report(
            status="attention",
            hook_commands={
                "analysis": outcome,
                "fusion_evidence": "emitted",
                "claim_fidelity": "emitted",
            },
        )
    )
    assert "2/3" in value["checked"]
    assert "need attention" in value["headline"]


def test_presentation_does_not_echo_untrusted_report_strings(doctor):
    value = doctor.presentation(
        report(
            status="attention",
            package_version="PRIVATE_SENTINEL",
            host_registration={"status": "PRIVATE_SENTINEL"},
            hook_commands={"PRIVATE_SENTINEL": "PRIVATE_SENTINEL"},
        )
    )
    assert "PRIVATE_SENTINEL" not in json.dumps(value)


def test_cli_includes_presentation_for_attention_result(doctor, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["doctor"])
    monkeypatch.setattr(doctor, "diagnose", lambda **kw: report(status="attention"))
    monkeypatch.setattr(
        doctor, "installation_inventory", lambda: {"status": "not_listed"}
    )
    assert doctor.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert "need attention" in result["presentation"]["headline"]


@pytest.mark.parametrize(
    "registration",
    [
        {"status": "unavailable"},
        {"status": "not_listed", "installations": []},
        {"status": "listed", "installations": [{"version": "0.6.1", "enabled": False}]},
        {
            "status": "listed",
            "installations": [{"version": "unknown", "enabled": True}],
        },
        {"status": "listed", "installations": [{"version": "0.1.0", "enabled": True}]},
        {
            "status": "listed",
            "installations": [{"version": "0.6.1", "enabled": True}] * 2,
        },
    ],
)
def test_registration_ambiguity_keeps_local_scope_and_names_next_check(
    doctor, registration
):
    value = doctor.presentation(report(host_registration=registration))
    assert value["status"] == "local_probes_passed"
    assert "registration requires inspection" in value["gap"]
    assert "plugin interface" in value["next"]
    assert "current-session activation is unverified" in value["headline"]


def test_missing_command_results_cannot_render_success(doctor):
    value = doctor.presentation(report(hook_commands={}))
    assert value["status"] == "attention"
