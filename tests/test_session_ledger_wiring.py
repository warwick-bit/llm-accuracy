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
import sys
from pathlib import Path

import pytest

from conftest import HOOK_SHELL


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "session-ledger"
HOOK_CONFIG = PLUGIN_ROOT / "hooks" / "hooks.json"

EVENT_ACTIONS = {
    "UserPromptSubmit": "capture",
    "Stop": "capture",
    "PostToolUse": "memory-capture",
    "PostToolUseFailure": "memory-capture",
    "PreCompact": "pre-compact",
    "PostCompact": "post-compact",
    "SessionStart": "session-start",
}

posix_only = pytest.mark.skipif(
    not HOOK_SHELL, reason="requires a configured POSIX hook shell"
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
        [HOOK_SHELL, "-c", hook_command(event)],
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
        [HOOK_SHELL, "-c", skill_command(name)],
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
            'if command -v python3 >/dev/null 2>&1; then PLUGIN_PYTHON=python3; '
            'else PLUGIN_PYTHON=python; fi; '
            '"$PLUGIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py" '
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
    assert json.loads(result.stdout) == {
        "systemMessage": "Session Ledger: Capture skipped: plugin data directory is unavailable."
    }
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


@posix_only
def test_clear_skill_command_reports_failure_without_plugin_data(
    tmp_path: Path,
) -> None:
    result = run_skill("clear", data_root=None, session_id=None)

    assert result.returncode == 0
    assert result.stderr == ""
    assert (
        result.stdout == "Could not confirm local Session Ledger state was cleared.\n"
    )


@posix_only
def test_navigation_and_compaction_use_same_session_record(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    payload = {"session_id": "synthetic-navigation", "cwd": str(tmp_path / "first")}
    events = [
        ("SessionStart", {**payload, "source": "startup"}),
        ("UserPromptSubmit", {**payload, "prompt": "Synthetic earlier decision."}),
        ("Stop", {**payload, "cwd": str(tmp_path / "second"),
                  "last_assistant_message": "Synthetic later answer."}),
        ("PreCompact", {**payload, "cwd": str(tmp_path / "second")}),
        # The observed host order restores before PostCompact writes the summary.
        ("SessionStart", {**payload, "cwd": str(tmp_path / "second"), "source": "compact"}),
        ("PostCompact", {**payload, "cwd": str(tmp_path / "second"),
                         "compact_summary": "Synthetic compact summary."}),
    ]
    for event, body in events:
        result = run_hook(event, json.dumps(body), data_root=data_root)
        assert result.returncode == 0 and result.stderr == ""
        if event == "SessionStart" and body["source"] == "compact":
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            assert "Synthetic earlier decision." in context
            assert "Synthetic later answer." in context
    assert len(list(data_root.glob("session-ledger/sessions/*/record.json"))) == 1
    for cwd in (payload["cwd"], str(tmp_path / "third")):
        result = run_hook("SessionStart", json.dumps({**payload, "cwd": cwd, "source": "resume"}),
                          data_root=data_root)
        assert "Synthetic compact summary." in result.stdout
    result = run_hook("SessionStart", json.dumps({**payload, "source": "compact",
                      "session_id": "synthetic-other-session"}), data_root=data_root)
    response = json.loads(result.stdout)
    assert "hookSpecificOutput" not in response
    assert "Restore skipped" in response["systemMessage"]


@pytest.mark.parametrize("stdio", ["cp1252:surrogateescape", "utf-8"])
@pytest.mark.parametrize("sample", ["Synthetic ASCII", "Synthetic café — →", "Synthetic ❯ ●", "Synthetic café — → 日本語 😀"])
@pytest.mark.parametrize("event,field", [
    ("UserPromptSubmit", "prompt"),
    ("Stop", "last_assistant_message"),
    ("PostCompact", "compact_summary"),
])
def test_utf8_payload_round_trips_independently_of_stdio_encoding(
    tmp_path: Path, stdio: str, sample: str, event: str, field: str
) -> None:
    # Send real UTF-8 bytes, not json.dumps' default ASCII escapes. Force the
    # Windows piped-stdin codec on every platform, including Linux CI.
    environment = clean_environment()
    environment.update(PYTHONUTF8="0", PYTHONIOENCODING=stdio)
    payload = {"session_id": "synthetic-encoding", "cwd": str(tmp_path), field: sample}
    command = [sys.executable, str(PLUGIN_ROOT / "hooks" / "session-ledger.py")]
    result = subprocess.run(
        [*command, EVENT_ACTIONS[event], "--plugin-data", str(tmp_path)],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True, env=environment, timeout=30,
    )
    assert result.returncode == 0
    assert result.stderr == b""
    assert result.stdout == b""
    path = record_file(tmp_path)
    assert path is not None
    record = json.loads(path.read_text(encoding="utf-8"))
    stored = record["compact_summary"] if field == "compact_summary" else record["entries"][0]["text"]
    assert stored == sample
    restored = subprocess.run(
        [*command, "session-start", "--plugin-data", str(tmp_path)],
        input=json.dumps({**payload, "source": "resume"}).encode("utf-8"),
        capture_output=True, env=environment, timeout=30,
    )
    assert restored.returncode == 0 and restored.stderr == b""
    context = json.loads(restored.stdout)["hookSpecificOutput"]["additionalContext"]
    marker = "COMPACT SUMMARY" if field == "compact_summary" else "SESSION RECORD"
    encoded = context.split(f"BEGIN JSON-ESCAPED {marker}\n", 1)[1].split(
        f"\nEND JSON-ESCAPED {marker}", 1
    )[0]
    restored_value = json.loads(encoded)
    assert (restored_value if field == "compact_summary" else restored_value[0]["text"]) == sample


@pytest.mark.parametrize("raw", [
    b"{\xff}", b'{"prompt":"\xff"}', b"{not json", b"[]",
    b"[" * 10000 + b"0" + b"]" * 10000,
])
def test_invalid_byte_payload_fails_open(tmp_path: Path, raw: bytes) -> None:
    result = subprocess.run(
        [sys.executable, str(PLUGIN_ROOT / "hooks" / "session-ledger.py"),
         "capture", "--plugin-data", str(tmp_path)],
        input=raw, capture_output=True, timeout=30,
    )
    assert result.returncode == 0
    assert result.stdout == result.stderr == b""
    assert record_file(tmp_path) is None
