"""Exercise the independently installable Evidence Memory hook commands."""
from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from conftest import HOOK_SHELL

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "evidence-memory"
HOOKS = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]


def test_enabled_plugin_hooks_allow_cold_start_time() -> None:
    assert all(handler["timeout"] == 10 for group in HOOKS.values()
               for entry in group for handler in entry["hooks"])


def invoke(event: str, payload: object, data: Path) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT), CLAUDE_PLUGIN_DATA=str(data))
    command = HOOKS[event][0]["hooks"][0]["command"]
    return subprocess.run([HOOK_SHELL, "-c", command], input=json.dumps(payload),
                          capture_output=True, text=True, env=environment, timeout=10)


def cli(data: Path, action: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ROOT / "hooks" / "memory.py"),
                           "--plugin-data", str(data), "--session-id", "synthetic-session", action],
                          capture_output=True, text=True, timeout=10)


@pytest.mark.skipif(not HOOK_SHELL, reason="POSIX hook shell unavailable")
@pytest.mark.parametrize("action", ["disable", "clear", "begin-plan"])
def test_plugin_autostarts_without_backfill_and_stop_stays_off(tmp_path: Path, action: str) -> None:
    data = tmp_path / "data"
    transcript = tmp_path / "synthetic.jsonl"
    old = {"sessionId": "synthetic-session", "timestamp": "2020-01-01T00:00:00Z",
           "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "old",
                       "name": "query_dataset", "input": {"metric": "old"}}]}}
    transcript.write_text(json.dumps(old) + "\n")
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript)}

    assert invoke("UserPromptSubmit", {**payload, "hook_event_name": "UserPromptSubmit"}, data).returncode == 0
    assert json.loads(cli(data, "status").stdout)["events"] == 0

    stamp = datetime.now(timezone.utc).isoformat()
    fresh = [
        {"sessionId": "synthetic-session", "timestamp": stamp,
         "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "new",
                     "name": "query_dataset", "input": {"metric": "new"}}]}},
        {"sessionId": "synthetic-session", "timestamp": stamp,
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "new",
                     "content": "new metric collected"}]}},
    ]
    with transcript.open("a") as stream:
        stream.writelines(json.dumps(row) + "\n" for row in fresh)
    assert invoke("PostToolUse", payload, data).returncode == 0
    assert json.loads(cli(data, "status").stdout)["events"] == 2

    assert cli(data, action).returncode == 0
    assert invoke("SessionStart", {**payload, "source": "compact"}, data).returncode == 0
    assert invoke("UserPromptSubmit", {**payload, "hook_event_name": "UserPromptSubmit"}, data).returncode == 0
    assert not list(data.rglob("memory.sqlite3"))

    stopped_scope = json.loads(next(data.rglob("scope.json")).read_text())
    stopped_at = datetime.fromisoformat(stopped_scope["started_at"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(stamp) < stopped_at
    assert cli(data, "enable").returncode == 0
    assert invoke("PostToolUse", payload, data).returncode == 0
    assert json.loads(cli(data, "status").stdout)["events"] == 0

    resumed_stamp = (stopped_at + timedelta(seconds=1)).isoformat()
    resumed = [
        {"sessionId": "synthetic-session", "timestamp": resumed_stamp,
         "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "resumed",
                     "name": "query_dataset", "input": {"metric": "resumed"}}]}},
        {"sessionId": "synthetic-session", "timestamp": resumed_stamp,
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "resumed",
                     "content": "resumed metric collected"}]}},
    ]
    with transcript.open("a") as stream:
        stream.writelines(json.dumps(row) + "\n" for row in resumed)
    assert invoke("PostToolUse", payload, data).returncode == 0
    assert json.loads(cli(data, "status").stdout)["events"] == 2

    other = {"session_id": "another-session", "cwd": str(tmp_path), "source": "startup"}
    assert invoke("SessionStart", other, data).returncode == 0
    assert len(list(data.rglob("memory.sqlite3"))) == 2


@pytest.mark.skipif(not HOOK_SHELL, reason="POSIX hook shell unavailable")
def test_legacy_stop_marker_does_not_autostart_on_upgrade(tmp_path: Path) -> None:
    data = tmp_path / "data"
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "hook_event_name": "UserPromptSubmit"}
    assert cli(data, "disable").returncode == 0
    scope = next(data.rglob("scope.json"))
    legacy = json.loads(scope.read_text())
    legacy.pop("capture_paused")
    scope.write_text(json.dumps(legacy))

    assert invoke("UserPromptSubmit", payload, data).returncode == 0
    assert invoke("SessionStart", {**payload, "source": "resume"}, data).returncode == 0
    assert not list(data.rglob("memory.sqlite3"))
    assert cli(data, "enable").returncode == 0
    assert len(list(data.rglob("memory.sqlite3"))) == 1


@pytest.mark.skipif(not HOOK_SHELL, reason="POSIX hook shell unavailable")
def test_independent_hook_capture_restore_and_clear(tmp_path: Path) -> None:
    data = tmp_path / "data"
    transcript = tmp_path / "synthetic.jsonl"
    rows = [
        {"sessionId": "synthetic-session", "timestamp": "2026-09-01T00:00:00Z",
         "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "one",
                     "name": "query_dataset", "input": {"metric": "metric007"}}]}},
        {"sessionId": "synthetic-session", "timestamp": "2026-09-01T00:00:01Z",
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "one",
                     "content": "metric007 collected 123 AUD"}]}},
    ]
    transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript)}
    assert invoke("PostToolUse", payload, data).returncode == 0
    assert not list(data.rglob("memory.sqlite3"))
    assert cli(data, "enable").returncode == 0
    assert invoke("PostToolUse", payload, data).returncode == 0
    status = json.loads(cli(data, "status").stdout)
    assert status["events"] == 2
    restored = invoke("SessionStart", {**payload, "source": "compact"}, data)
    assert restored.returncode == 0
    assert "evidence-memory:memory" in json.loads(restored.stdout)["hookSpecificOutput"]["additionalContext"]
    assert cli(data, "clear").returncode == 0
    assert not list(data.rglob("memory.sqlite3"))
    assert invoke("PostToolUse", payload, data).returncode == 0
    assert not list(data.rglob("memory.sqlite3"))


@pytest.mark.skipif(not HOOK_SHELL, reason="POSIX hook shell unavailable")
def test_malformed_hook_input_fails_open(tmp_path: Path) -> None:
    environment = dict(os.environ, CLAUDE_PLUGIN_ROOT=str(ROOT),
                       CLAUDE_PLUGIN_DATA=str(tmp_path / "data"))
    command = HOOKS["PostToolUse"][0]["hooks"][0]["command"]
    result = subprocess.run([HOOK_SHELL, "-c", command], input="{invalid",
                            capture_output=True, text=True, env=environment, timeout=10)
    assert result.returncode == 0
    assert result.stdout == ""


@pytest.mark.skipif(not HOOK_SHELL, reason="POSIX hook shell unavailable")
@pytest.mark.parametrize("initial", ["missing", "empty"])
def test_prompt_before_transcript_is_quiet_and_later_capture_catches_up(
        tmp_path: Path, initial: str) -> None:
    data = tmp_path / "data"
    transcript = tmp_path / "synthetic.jsonl"
    if initial == "empty":
        transcript.touch()
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript), "hook_event_name": "UserPromptSubmit"}

    first = invoke("UserPromptSubmit", payload, data)
    assert first.returncode == 0
    assert first.stdout == ""
    assert json.loads(cli(data, "status").stdout)["events"] == 0

    second = invoke("UserPromptSubmit", payload, data)
    assert second.returncode == 0
    assert second.stdout == ""
    third = invoke("UserPromptSubmit", payload, data)
    assert third.returncode == 0
    assert "transcript still unavailable after three hooks" in json.loads(third.stdout)["systemMessage"]
    fourth = invoke("UserPromptSubmit", payload, data)
    assert fourth.returncode == 0
    assert fourth.stdout == ""

    stamp = datetime.now(timezone.utc).isoformat()
    rows = [
        {"sessionId": "synthetic-session", "timestamp": stamp,
         "message": {"role": "assistant", "content": [{"type": "tool_use", "id": "fresh",
                     "name": "synthetic_query", "input": {"key": "fresh"}}]}},
        {"sessionId": "synthetic-session", "timestamp": stamp,
         "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "fresh",
                     "content": "fresh result"}]}},
    ]
    transcript.write_text("".join(json.dumps(row) + "\n" for row in rows))
    later = invoke("PostToolUse", payload, data)
    assert later.returncode == 0
    assert later.stdout == ""
    assert json.loads(cli(data, "status").stdout)["events"] == 2
    transcript.unlink()
    assert invoke("PostToolUse", payload, data).stdout == ""


@pytest.mark.skipif(os.name != "posix" or not HOOK_SHELL, reason="POSIX lock probe unavailable")
def test_busy_session_lock_reports_safe_code_and_later_capture_catches_up(tmp_path: Path) -> None:
    import fcntl

    data = tmp_path / "data"
    transcript = tmp_path / "synthetic.jsonl"
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript), "hook_event_name": "UserPromptSubmit"}
    assert invoke("UserPromptSubmit", payload, data).stdout == ""

    stamp = datetime.now(timezone.utc).isoformat()
    transcript.write_text(json.dumps({"sessionId": "synthetic-session", "timestamp": stamp,
                                      "message": {"role": "assistant", "content": [
                                          {"type": "tool_use", "id": "fresh", "name": "synthetic_query",
                                           "input": {"key": "fresh"}}]}}) + "\n")
    lock = data / "evidence-memory" / "locks" / hashlib.sha256(b"synthetic-session").hexdigest()
    with lock.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        blocked = invoke("PostToolUse", payload, data)
        assert blocked.returncode == 0
        assert "BlockingIOError" in json.loads(blocked.stdout)["systemMessage"]
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    later = invoke("PostToolUse", payload, data)
    assert later.returncode == 0
    assert later.stdout == ""
    assert json.loads(cli(data, "status").stdout)["events"] == 1


@pytest.mark.skipif(not HOOK_SHELL, reason="POSIX hook shell unavailable")
def test_persistent_scope_error_reports_safe_code(tmp_path: Path) -> None:
    data = tmp_path / "data"
    transcript = tmp_path / "wrong-session.jsonl"
    transcript.write_text(json.dumps({"sessionId": "other-session", "timestamp": "2026-09-25T00:00:00Z",
                                      "message": {"role": "user", "content": "synthetic"}}) + "\n")
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript), "hook_event_name": "UserPromptSubmit"}
    result = invoke("UserPromptSubmit", payload, data)
    assert result.returncode == 0
    message = json.loads(result.stdout)["systemMessage"]
    assert "transcript_session_mismatch" in message
    assert str(transcript) not in message
    assert "other-session" not in message


@pytest.mark.skipif(not HOOK_SHELL or os.name != "posix", reason="symlink probe unavailable")
def test_symlinked_transcript_is_not_treated_as_host_delay(tmp_path: Path) -> None:
    data = tmp_path / "data"
    transcript = tmp_path / "synthetic.jsonl"
    transcript.symlink_to(tmp_path / "missing-target.jsonl")
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript), "hook_event_name": "UserPromptSubmit"}
    result = invoke("UserPromptSubmit", payload, data)
    assert result.returncode == 0
    assert "transcript_unavailable" in json.loads(result.stdout)["systemMessage"]


@pytest.mark.skipif(not HOOK_SHELL or not hasattr(os, "mkfifo"), reason="FIFO probe unavailable")
def test_special_file_is_not_treated_as_host_delay(tmp_path: Path) -> None:
    data = tmp_path / "data"
    transcript = tmp_path / "synthetic.pipe"
    os.mkfifo(transcript)
    payload = {"session_id": "synthetic-session", "cwd": str(tmp_path),
               "transcript_path": str(transcript), "hook_event_name": "UserPromptSubmit"}
    result = invoke("UserPromptSubmit", payload, data)
    assert result.returncode == 0
    assert "transcript_unavailable" in json.loads(result.stdout)["systemMessage"]
