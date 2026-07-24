"""Subprocess-level wiring tests that invoke the hook exactly as hooks.json does.

The behaviour tests in test_session_ledger.py import the module and call
functions directly, which leaves CLI parsing, stdin handling, interpreter
invocation, and the hooks.json contract uncovered. These tests execute the
exact command strings shipped in hooks.json through a POSIX shell, the same
way Claude Code runs them.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "session-ledger"
HOOK_CONFIG = PLUGIN_ROOT / "hooks" / "hooks.json"

EVENT_ACTIONS = {
    "UserPromptSubmit": "capture",
    "Stop": "capture",
    "PreCompact": "pre-compact",
    "PostCompact": "post-compact",
    "SessionStart": "session-start",
}

posix_only = pytest.mark.skipif(
    os.name != "posix", reason="hook commands run through a POSIX shell"
)


def hook_command(event: str) -> str:
    config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))["hooks"]
    matchers = config[event]
    assert len(matchers) == 1
    hooks = matchers[0]["hooks"]
    assert len(hooks) == 1
    return hooks[0]["command"]


def run_hook(
    event: str,
    stdin_text: str,
    *,
    data_root: Path | None,
) -> subprocess.CompletedProcess[str]:
    """Run one shipped hook command exactly as the host would."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA"}
    }
    environment["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    if data_root is not None:
        environment["CLAUDE_PLUGIN_DATA"] = str(data_root)
    return subprocess.run(
        ["/bin/sh", "-c", hook_command(event)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )


def record_file(data_root: Path) -> Path | None:
    matches = sorted(data_root.glob("session-ledger/sessions/*/record.json"))
    return matches[0] if matches else None


def read_entries(data_root: Path) -> list[dict[str, str]]:
    path = record_file(data_root)
    assert path is not None, "expected a ledger record to be written"
    return json.loads(path.read_text(encoding="utf-8"))["entries"]


def test_hooks_json_shape_matches_the_documented_contract() -> None:
    config = json.loads(HOOK_CONFIG.read_text(encoding="utf-8"))
    assert set(config) == {"hooks"}
    assert set(config["hooks"]) == set(EVENT_ACTIONS)
    for event, action in EVENT_ACTIONS.items():
        hook = config["hooks"][event][0]["hooks"][0]
        assert set(hook) == {"type", "command", "timeout"}
        assert hook["type"] == "command"
        assert hook["timeout"] == 5
        assert hook["command"] == (
            'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py" '
            f'{action} --plugin-data "${{CLAUDE_PLUGIN_DATA}}"'
        )


@posix_only
def test_user_prompt_submit_command_captures_the_prompt(tmp_path: Path) -> None:
    data_root = tmp_path / "plugin-data"
    payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
        "prompt": "Synthetic wiring prompt.",
    }

    result = run_hook("UserPromptSubmit", json.dumps(payload), data_root=data_root)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""
    entries = read_entries(data_root)
    assert entries == [
        {
            "role": "user",
            "text": "Synthetic wiring prompt.",
            "fingerprint": entries[0]["fingerprint"],
        }
    ]
    assert entries[0]["fingerprint"].startswith("hook:")


@posix_only
def test_stop_command_captures_the_last_assistant_message(tmp_path: Path) -> None:
    data_root = tmp_path / "plugin-data"
    payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
        "last_assistant_message": "Synthetic wiring reply.",
    }

    result = run_hook("Stop", json.dumps(payload), data_root=data_root)

    assert result.returncode == 0
    assert result.stderr == ""
    roles = [(entry["role"], entry["text"]) for entry in read_entries(data_root)]
    assert roles == [("assistant", "Synthetic wiring reply.")]


@posix_only
def test_pre_compact_command_flushes_the_transcript_tail(tmp_path: Path) -> None:
    data_root = tmp_path / "plugin-data"
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Synthetic transcript text."}],
                }
            }
        ),
        encoding="utf-8",
    )
    payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "transcript_path": str(transcript),
        "trigger": "manual",
    }

    result = run_hook("PreCompact", json.dumps(payload), data_root=data_root)

    assert result.returncode == 0
    assert result.stderr == ""
    roles = [(entry["role"], entry["text"]) for entry in read_entries(data_root)]
    assert roles == [("assistant", "Synthetic transcript text.")]


@posix_only
def test_post_compact_then_session_start_restores_the_summary(tmp_path: Path) -> None:
    data_root = tmp_path / "plugin-data"
    compact_payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "compact_summary": "Synthetic compact summary evidence.",
    }
    result = run_hook("PostCompact", json.dumps(compact_payload), data_root=data_root)
    assert result.returncode == 0
    assert result.stderr == ""
    record_path = record_file(data_root)
    assert record_path is not None
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["compact_summary"] == "Synthetic compact summary evidence."

    start_payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "source": "compact",
    }
    result = run_hook("SessionStart", json.dumps(start_payload), data_root=data_root)

    assert result.returncode == 0
    assert result.stderr == ""
    response = json.loads(result.stdout)
    output = response["hookSpecificOutput"]
    assert output["hookEventName"] == "SessionStart"
    assert "UNTRUSTED HISTORICAL REFERENCE" in output["additionalContext"]
    assert "Synthetic compact summary evidence." in output["additionalContext"]


@posix_only
@pytest.mark.parametrize("event", sorted(EVENT_ACTIONS))
@pytest.mark.parametrize("stdin_text", ["", "{not json", '["not", "an", "object"]'])
def test_malformed_stdin_fails_open_without_output(
    tmp_path: Path, event: str, stdin_text: str
) -> None:
    data_root = tmp_path / "plugin-data"

    result = run_hook(event, stdin_text, data_root=data_root)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""
    assert record_file(data_root) is None


@posix_only
def test_missing_plugin_data_environment_fails_open(tmp_path: Path) -> None:
    payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
        "prompt": "Synthetic wiring prompt.",
    }

    result = run_hook("UserPromptSubmit", json.dumps(payload), data_root=None)

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == ""
    assert not list(tmp_path.rglob("record.json"))
