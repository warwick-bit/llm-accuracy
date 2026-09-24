"""Experimental synthetic Read observer; not included in a distributed plugin.

The pre-tool branch isolates the smoke. The post-tool branch only observes the
host payload. It neither reads a model-selected path nor executes a command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


def allowed_read(payload: dict, fixture: str) -> bool:
    tool_input = payload.get("tool_input")
    return (
        payload.get("tool_name") == "Read"
        and isinstance(tool_input, dict)
        and tool_input.get("file_path") == fixture
    )


def observe(payload: dict, config: dict) -> dict:
    """Return fixed typed facts only; unknown tool shapes cannot pass."""
    response = payload.get("tool_response")
    file = response.get("file") if isinstance(response, dict) else None
    content = file.get("content") if isinstance(file, dict) else None
    return {
        "schema_version": 1,
        "tool": "Read",
        "expected_path": allowed_read(payload, config["fixture"]),
        "text_response": isinstance(content, str),
        "content_matches_fixture": content == config["content"],
        "authority": "tool_observation_only",
    }


def handle(payload: dict, config: dict) -> tuple[dict, dict | None]:
    event = payload.get("hook_event_name")
    if event == "PreToolUse":
        permitted = allowed_read(payload, config["fixture"])
        return {"hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": "allow" if permitted else "deny",
            "permissionDecisionReason": "Synthetic smoke fixture boundary",
        }}, None
    if event != "PostToolUse" or not allowed_read(payload, config["fixture"]):
        return {}, None
    observation = observe(payload, config)
    if not observation["content_matches_fixture"] or not config["emit"]:
        return {}, observation
    context = (
        "Read observation marker: " + config["marker"] + ". "
        "The host returned the expected synthetic file content. "
        "This records a file read only; it verifies neither the truth of its "
        "contents nor execution of any test described in it."
    )
    return {"hookSpecificOutput": {
        "hookEventName": event, "additionalContext": context,
    }}, observation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        raw = sys.stdin.read(1_000_001)
        if len(raw) > 1_000_000:
            return 2
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return 2
        output, observation = handle(payload, config)
        if observation is not None:
            Path(config["receipt"]).write_text(json.dumps(observation), encoding="utf-8")
        print(json.dumps(output))
    except (OSError, ValueError, KeyError, TypeError):
        # A failed isolation hook must invalidate the smoke, not reveal payloads.
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
