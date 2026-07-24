"""Subprocess-level wiring tests that invoke the hook exactly as hooks.json does.

The behaviour tests in test_session_ledger.py import the module and call
functions directly, which leaves CLI parsing, stdin handling, interpreter
invocation, and the hooks.json contract uncovered. These tests execute the
exact command strings shipped in hooks.json — and the inline commands embedded
in the begin-plan and clear SKILL.md files — through a POSIX shell, the same
way Claude Code runs them.
"""

from __future__ import annotations

import json
import os
import re
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


def clean_environment() -> dict[str, str]:
    """Return the ambient environment minus every plugin-contract variable."""
    return {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "CLAUDE_PLUGIN_ROOT",
            "CLAUDE_PLUGIN_DATA",
            "CLAUDE_SESSION_ID",
            "SESSION_LEDGER_REDACT",
        }
    }


def run_hook(
    event: str,
    stdin_text: str,
    *,
    data_root: Path | None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one shipped hook command exactly as the host would."""
    environment = clean_environment()
    environment["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    if data_root is not None:
        environment["CLAUDE_PLUGIN_DATA"] = str(data_root)
    environment.update(extra_env or {})
    return subprocess.run(
        ["/bin/sh", "-c", hook_command(event)],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )


def skill_command(name: str) -> str:
    """Return the one inline command embedded in a skill's SKILL.md."""
    source = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    commands = re.findall(r"!`([^`]+)`", source)
    assert len(commands) == 1, f"{name} skill must embed exactly one inline command"
    return commands[0]


def run_skill(
    name: str,
    *,
    data_root: Path | None,
    session_id: str | None,
) -> subprocess.CompletedProcess[str]:
    """Run one skill's embedded command exactly as skill preprocessing would."""
    environment = clean_environment()
    environment["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    if data_root is not None:
        environment["CLAUDE_PLUGIN_DATA"] = str(data_root)
    if session_id is not None:
        environment["CLAUDE_SESSION_ID"] = session_id
    return subprocess.run(
        ["/bin/sh", "-c", skill_command(name)],
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
    assert result.stdout == ""
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
    assert result.stdout == ""
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
    assert result.stdout == ""
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


@posix_only
def test_capture_command_applies_opt_in_redaction_from_the_environment(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "plugin-data"
    payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
        "prompt": "Key AKIAIOSFODNN7EXAMPLE was pasted here.",
    }

    result = run_hook(
        "UserPromptSubmit",
        json.dumps(payload),
        data_root=data_root,
        extra_env={"SESSION_LEDGER_REDACT": "1"},
    )

    assert result.returncode == 0
    assert result.stderr == ""
    entries = read_entries(data_root)
    assert entries[0]["text"] == "Key [REDACTED:aws-access-key-id] was pasted here."


@posix_only
def test_begin_plan_skill_command_starts_a_boundary(tmp_path: Path) -> None:
    data_root = tmp_path / "plugin-data"

    result = run_skill("begin-plan", data_root=data_root, session_id="wiring-session")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "Started a fresh Session Ledger plan boundary" in result.stdout
    assert len(list(data_root.glob("session-ledger/sessions/*/scope.json"))) == 1


@posix_only
@pytest.mark.parametrize("missing", ["plugin-data", "session-id"])
def test_begin_plan_skill_command_reports_failure_when_env_is_missing(
    tmp_path: Path, missing: str
) -> None:
    data_root = None if missing == "plugin-data" else tmp_path / "plugin-data"
    session_id = None if missing == "session-id" else "wiring-session"

    result = run_skill("begin-plan", data_root=data_root, session_id=session_id)

    assert result.returncode == 0
    assert result.stderr == ""
    assert (
        result.stdout
        == "Could not confirm a Session Ledger plan boundary was started.\n"
    )
    assert not list(tmp_path.rglob("scope.json"))


@posix_only
def test_clear_skill_command_deletes_state_and_reports_it(tmp_path: Path) -> None:
    data_root = tmp_path / "plugin-data"
    payload = {
        "session_id": "wiring-session",
        "cwd": str(tmp_path),
        "transcript_path": str(tmp_path / "missing-transcript.jsonl"),
        "prompt": "Synthetic wiring prompt.",
    }
    run_hook("UserPromptSubmit", json.dumps(payload), data_root=data_root)
    assert record_file(data_root) is not None

    result = run_skill("clear", data_root=data_root, session_id="wiring-session")

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout == "Cleared local Session Ledger state.\n"
    assert not (data_root / "session-ledger").exists()
