"""Exercise installed hook vectors with synthetic data, without a model call."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from hook_command import shell_argv

SESSION = "synthetic-installed-qa"
SUMMARY = "Synthetic installed ledger summary."
MARKER = "Synthetic installed memory marker 4831."


def invoke(
    plugin: Path,
    event: str,
    payload: dict,
    data: Path,
    python: str,
    env: dict,
    *,
    index: int = 0,
) -> bytes:
    hook = json.loads((plugin / "hooks/hooks.json").read_text())["hooks"][event][index][
        "hooks"
    ][0]
    child = {**env, "CLAUDE_PLUGIN_ROOT": str(plugin), "CLAUDE_PLUGIN_DATA": str(data),
             "CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE": python}
    arguments = shell_argv(hook["command"], child)
    result = subprocess.run(
        arguments,
        input=json.dumps(payload).encode(),
        env=child,
        capture_output=True,
        timeout=15,
    )
    if result.returncode or result.stderr:
        raise ValueError("installed_hook_probe_failed")
    return result.stdout


def memory_cli(plugin: Path, data: Path, python: str, env: dict, *arguments) -> dict:
    result = subprocess.run(
        [
            python or sys.executable,
            str(plugin / "hooks/memory.py"),
            "--plugin-data",
            str(data),
            "--session-id",
            SESSION,
            *arguments,
        ],
        env=env,
        capture_output=True,
        timeout=15,
    )
    if result.returncode or result.stderr:
        raise ValueError("installed_hook_probe_failed")
    return json.loads(result.stdout)


def memory_probe(plugin: Path, root: Path, python: str, env: dict) -> bool:
    data, log = root / "memory-data", root / "synthetic-transcript.jsonl"
    log.write_text("", encoding="utf-8")
    payload = {
        "session_id": SESSION,
        "cwd": str(root),
        "transcript_path": str(log),
        "hook_event_name": "UserPromptSubmit",
    }
    invoke(plugin, "UserPromptSubmit", payload, data, python, env)
    timestamp = datetime.now(timezone.utc).isoformat()
    entries = [
        {
            "sessionId": SESSION,
            "timestamp": timestamp,
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "qa-call",
                        "name": "mcp__synthetic__query_dataset",
                        "input": {},
                    }
                ],
            },
        },
        {
            "sessionId": SESSION,
            "timestamp": timestamp,
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "qa-call", "content": MARKER}
                ],
            },
        },
    ]
    log.write_text(
        "".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8"
    )
    payload["hook_event_name"] = "PostToolUse"
    invoke(plugin, "PostToolUse", payload, data, python, env)
    before = memory_cli(plugin, data, python, env, "status")["events"]
    matched = len(memory_cli(plugin, data, python, env, "search", "4831")["matches"]) == 1
    invoke(plugin, "PostToolUse", payload, data, python, env)
    after = memory_cli(plugin, data, python, env, "status")["events"]
    memory_cli(plugin, data, python, env, "disable")
    # The transcript contains exactly one call and one result event.
    return matched and before == after == 2


def run(
    installed: dict[str, Path], root: Path, options: dict[str, str], env: dict
) -> bool:
    payload = {
        "session_id": SESSION,
        "cwd": str(root),
        "prompt": "Does this evidence prove the source is current and complete?",
    }
    accuracy = invoke(
        installed["llm-accuracy"],
        "UserPromptSubmit",
        payload,
        root / "accuracy-data",
        options["llm-accuracy"],
        env,
        index=2,
    )
    if b"CLAIM FIDELITY CHECK" not in accuracy:
        return False
    ledger, data = installed["session-ledger"], root / "ledger-data"
    compact = {"session_id": SESSION, "cwd": str(root), "compact_summary": SUMMARY}
    invoke(ledger, "PostCompact", compact, data, options["session-ledger"], env)
    restored = invoke(
        ledger,
        "SessionStart",
        {**payload, "source": "compact"},
        data,
        options["session-ledger"],
        env,
    )
    if SUMMARY.encode() not in restored:
        return False
    return memory_probe(
        installed["evidence-memory"], root, options["evidence-memory"], env
    )
