"""Exercise the independently installable Evidence Memory hook commands."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import HOOK_SHELL

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "evidence-memory"
HOOKS = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]


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
