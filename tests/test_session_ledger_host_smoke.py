"""Tests for the content-free Session Ledger Claude Code host smoke."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "session_ledger_host_smoke.py"


def load_smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("session_ledger_host_smoke", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_observer_payload_retains_structure_not_prompt_values() -> None:
    smoke = load_smoke()
    payload = {
        "agent_id": "synthetic-child-id",
        "agent_type": "synthetic-child-type",
        "hook_event_name": "UserPromptSubmit",
        "prompt": "Synthetic secret-shaped prompt must never be retained here.",
        "session_id": "synthetic-session-id",
        "source": "startup",
    }

    receipt = smoke.observer_payload(
        payload, expected_session_id="synthetic-session-id"
    )

    assert receipt == {
        "agent_id_present": True,
        "agent_type_present": True,
        "event": "UserPromptSubmit",
        "keys": sorted(payload),
        "session_id_matches_requested": True,
        "session_id_present": True,
        "source": "startup",
    }
    rendered = json.dumps(receipt)
    assert payload["prompt"] not in rendered
    assert payload["session_id"] not in rendered
    assert payload["agent_id"] not in rendered
    assert payload["agent_type"] not in rendered


def test_observer_payload_bounds_unknown_event_and_source_values() -> None:
    smoke = load_smoke()

    receipt = smoke.observer_payload(
        {"hook_event_name": "UnexpectedEvent", "source": "untrusted-value"},
        expected_session_id="synthetic-session-id",
    )

    assert receipt == {
        "agent_id_present": False,
        "agent_type_present": False,
        "event": "unknown",
        "keys": ["hook_event_name", "source"],
        "session_id_matches_requested": False,
        "session_id_present": False,
        "source": None,
    }


def test_observer_plugin_covers_only_session_ledger_events(tmp_path: Path) -> None:
    smoke = load_smoke()

    plugin = smoke.write_observer_plugin(tmp_path)

    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())
    hooks = json.loads((plugin / "hooks" / "hooks.json").read_text())["hooks"]
    assert manifest["name"] == "session-ledger-host-observer"
    assert set(hooks) == smoke.OBSERVED_EVENTS
    assert all(
        entry[0]["hooks"][0]["command"]
        == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/observe.py"'
        for entry in hooks.values()
    )


def test_generated_observer_discards_payload_values(tmp_path: Path) -> None:
    smoke = load_smoke()
    plugin = smoke.write_observer_plugin(tmp_path)
    receipts = tmp_path / "receipts.jsonl"
    payload = {
        "agent_id": "synthetic-agent-id",
        "hook_event_name": "Stop",
        "last_assistant_message": "Synthetic assistant text must not persist.",
        "session_id": "synthetic-session-id",
    }
    environment = {
        **os.environ,
        "SESSION_LEDGER_SMOKE_RECEIPTS": str(receipts),
        "SESSION_LEDGER_SMOKE_SESSION_ID": "synthetic-session-id",
    }

    result = subprocess.run(
        ["python3", str(plugin / "hooks" / "observe.py")],
        input=json.dumps(payload),
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""
    rendered = receipts.read_text(encoding="utf-8")
    assert payload["last_assistant_message"] not in rendered
    assert payload["session_id"] not in rendered
    assert payload["agent_id"] not in rendered
    assert json.loads(rendered)["session_id_matches_requested"] is True


def test_direct_report_requires_the_three_noninteractive_events() -> None:
    smoke = load_smoke()
    receipts = [
        {"event": "SessionStart", "agent_id_present": False},
        {"event": "UserPromptSubmit", "agent_id_present": False},
        {"event": "Stop", "agent_id_present": False},
    ]

    result = smoke.report_for(receipts, scenario="direct", command_exit=0)

    assert result["outcome"] == "PASS"
    assert result["event_counts"] == {
        "SessionStart": 1,
        "Stop": 1,
        "UserPromptSubmit": 1,
    }
    assert result["host_output"] == "discarded"
    assert result["execution"] == "completed"
    assert result["subagent_payload_seen"] is False
    assert result["subagent_session_mapping"] == "not_observed"


def test_subagent_report_requires_an_observed_agent_field() -> None:
    smoke = load_smoke()
    receipts = [
        {"event": "SessionStart", "agent_id_present": False},
        {
            "event": "UserPromptSubmit",
            "agent_id_present": True,
            "session_id_matches_requested": True,
            "session_id_present": True,
        },
        {"event": "Stop", "agent_id_present": False},
    ]

    result = smoke.report_for(receipts, scenario="subagent", command_exit=0)
    assert result["outcome"] == "PASS"
    assert result["subagent_session_mapping"] == "shared-session"
    assert smoke.report_for(receipts[:1], scenario="subagent", command_exit=0)[
        "outcome"
    ] == "FAIL"


def test_smoke_command_uses_a_new_session_and_direct_plugin_paths(tmp_path: Path) -> None:
    smoke = load_smoke()
    command = smoke.smoke_command(
        claude="claude-test",
        observer=tmp_path / "observer",
        scenario="direct",
        budget_usd="0.25",
        session_id="123e4567-e89b-12d3-a456-426614174000",
    )

    assert command[:7] == [
        "claude-test",
        "--print",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--setting-sources",
        "",
    ]
    assert "--strict-mcp-config" in command
    assert "--plugin-dir" in command
    assert str(smoke.LEDGER_PLUGIN) in command
    assert str(tmp_path / "observer") in command
    session_id = command[command.index("--session-id") + 1]
    assert session_id == "123e4567-e89b-12d3-a456-426614174000"
    assert command[-1] == smoke.DIRECT_PROMPT


def test_run_smoke_uses_only_the_clean_config_and_structural_receipt(
    tmp_path: Path, monkeypatch
) -> None:
    smoke = load_smoke()
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        receipts = Path(str(kwargs["env"]["SESSION_LEDGER_SMOKE_RECEIPTS"]))
        receipts.write_text(
            "\n".join(
                json.dumps(
                    {
                        "event": event,
                        "agent_id_present": False,
                        "session_id_matches_requested": True,
                    }
                )
                for event in ("SessionStart", "UserPromptSubmit", "Stop")
            )
            + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, b"ignored", b"ignored")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    result = smoke.run_smoke(
        claude="claude-test",
        config_dir=tmp_path / "clean-config",
        scenario="direct",
        budget_usd="0.25",
        timeout=30,
    )

    environment = captured["environment"]
    assert result["outcome"] == "PASS"
    assert (tmp_path / "clean-config").is_dir()
    assert set(environment) == {
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
        "CLAUDE_CONFIG_DIR",
        "HOME",
        "PATH",
        "SESSION_LEDGER_SMOKE_RECEIPTS",
        "SESSION_LEDGER_SMOKE_SESSION_ID",
    }
    assert environment["CLAUDE_CONFIG_DIR"] == str(tmp_path / "clean-config")
    assert environment["HOME"] == str(tmp_path / "clean-config")
    assert captured["command"][0] == "claude-test"


def test_run_smoke_reports_timeout_without_host_output(tmp_path: Path, monkeypatch) -> None:
    smoke = load_smoke()

    def fake_run(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("claude-test", 30, output=b"ignored")

    monkeypatch.setattr(smoke.subprocess, "run", fake_run)

    result = smoke.run_smoke(
        claude="claude-test",
        config_dir=tmp_path / "clean-config",
        scenario="direct",
        budget_usd="0.25",
        timeout=30,
    )

    assert result == {
        "claude_exit_code": None,
        "event_counts": {},
        "execution": "timed_out",
        "host_output": "discarded",
        "outcome": "FAIL",
        "required_events_seen": [],
        "scenario": "direct",
        "subagent_payload_seen": False,
        "subagent_session_mapping": "not_observed",
    }
