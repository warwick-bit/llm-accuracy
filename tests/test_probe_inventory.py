"""Missing inventory cannot serve as isolation evidence; no raw names escape."""

import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "inventory_probe",
    Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/scripts/host_probe.py",
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


def initial(**fields):
    return {
        "type": "system",
        "subtype": "init",
        "tools": [],
        "mcp_servers": [],
        "plugins": [{"name": "llm-accuracy", "path": "PRIVATE_SENTINEL"}],
        **fields,
    }


def test_inventory_counts_without_raw_host_details():
    result = probe.host_inventory([initial()])
    assert result == {
        "status": "reported",
        "tool_count": 0,
        "mcp_count": 0,
        "plugin_count": 1,
        "accuracy_plugin_count": 1,
        "telemetry_plugin_count": 0,
    }
    assert "PRIVATE_SENTINEL" not in json.dumps(result)


@pytest.mark.parametrize(
    "events",
    [
        [],
        [initial(), initial()],
        [initial(tools=None)],
        [initial(plugins={})],
        [initial(mcp_servers="PRIVATE_SENTINEL")],
    ],
)
def test_absent_or_ambiguous_inventory_is_unreported(events):
    assert probe.host_inventory(events) == {"status": "unreported"}


def test_other_plugins_and_live_integrations_are_counted():
    result = probe.host_inventory(
        [
            initial(
                tools=["PRIVATE_SENTINEL"],
                mcp_servers=[{"name": "PRIVATE_SENTINEL"}],
                plugins=[{"name": "session-ledger"}, {"name": "llm-accuracy"}, None],
            )
        ]
    )
    assert result["tool_count"] == 1
    assert result["mcp_count"] == 1
    assert result["plugin_count"] == 3
    assert result["accuracy_plugin_count"] == 1
    assert "PRIVATE_SENTINEL" not in json.dumps(result)


def test_event_parser_exposes_attestation():
    payload = "\n".join(
        json.dumps(e) for e in [initial(), {"type": "result", "result": "OK"}]
    )
    assert probe.parse_events(payload, "", 0)["host_inventory"]["plugin_count"] == 1


def test_shared_host_component_is_distinguished_from_accuracy():
    result = probe.host_inventory([initial(plugins=[{"name": "telemetry"}])])
    assert result["plugin_count"] == result["telemetry_plugin_count"] == 1
    assert result["accuracy_plugin_count"] == 0


def test_explicit_effort_is_passed_to_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(probe.shutil, "which", lambda _: "claude")
    captured = []

    def communicate(command, *args):
        captured.extend(command)
        return {"status": "ok", "answers": ["OK"]}

    monkeypatch.setattr(probe, "communicate", communicate)
    assert probe.run_probe(["synthetic"], None, effort="medium")["status"] == "ok"
    assert captured[captured.index("--effort") + 1] == "medium"


def test_invalid_effort_never_starts_a_process(monkeypatch):
    monkeypatch.setattr(
        probe.shutil, "which", lambda _: pytest.fail("must not discover CLI")
    )
    assert probe.run_probe(["synthetic"], None, effort="arbitrary") == {
        "status": "invalid_effort",
        "answers": [],
    }
