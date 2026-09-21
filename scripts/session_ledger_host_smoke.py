#!/usr/bin/env python3
"""Run a content-free Claude Code host smoke for the Session Ledger plugin.

The observer plugin produced here records only hook event names, payload key
names, and boolean presence flags. Claude's stdout and stderr are captured and
discarded, so this script never prints, writes, or returns a prompt, transcript,
model response, credential, or hook payload value.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PLUGIN = ROOT / "plugins" / "session-ledger"
OBSERVED_EVENTS = frozenset(
    {
        "SessionStart",
        "UserPromptSubmit",
        "Stop",
        "PreCompact",
        "PostCompact",
        "SubagentStart",
        "SubagentStop",
    }
)
OBSERVED_SOURCES = frozenset({"startup", "resume", "clear", "compact", "fork"})
DIRECT_REQUIRED_EVENTS = frozenset({"SessionStart", "UserPromptSubmit", "Stop"})
SUBAGENT_REQUIRED_EVENTS = DIRECT_REQUIRED_EVENTS | frozenset(
    {"SubagentStart", "SubagentStop"}
)
SUBAGENT_LIFECYCLE_EVENTS = frozenset({"SubagentStart", "SubagentStop"})
DIRECT_PROMPT = "Reply exactly: SESSION_LEDGER_SMOKE_OK. Do not use any tools."
SMOKE_AGENT_NAME = "ledger-smoke-child"
SMOKE_AGENT = {
    SMOKE_AGENT_NAME: {
        "description": "Reply with the fixed Session Ledger smoke acknowledgement.",
        "prompt": "Reply exactly: SESSION_LEDGER_SMOKE_OK. Do not use any tools.",
        "tools": [],
    }
}
SUBAGENT_PROMPT = (
    f"Use exactly one {SMOKE_AGENT_NAME} subagent by invoking the Agent tool. "
    "After it replies, reply exactly: SESSION_LEDGER_SMOKE_OK."
)


def observer_payload(
    payload: object, *, expected_session_id: str | None = None
) -> dict[str, object]:
    """Return a safe structural receipt without retaining payload values."""
    if not isinstance(payload, dict):
        return {
            "event": "unknown",
            "keys": [],
            "session_id_matches_requested": False,
        }
    event = payload.get("hook_event_name")
    session_id = payload.get("session_id")
    source = payload.get("source")
    return {
        "agent_id_present": isinstance(payload.get("agent_id"), str),
        "agent_type_present": isinstance(payload.get("agent_type"), str),
        "event": event if event in OBSERVED_EVENTS else "unknown",
        "keys": sorted(key for key in payload if isinstance(key, str)),
        "session_id_matches_requested": (
            isinstance(session_id, str) and session_id == expected_session_id
        ),
        "session_id_present": isinstance(payload.get("session_id"), str),
        "source": source if source in OBSERVED_SOURCES else None,
    }


def observer_source() -> str:
    """Return the temporary observer hook source with no payload-value logging."""
    events = json.dumps(sorted(OBSERVED_EVENTS))
    sources = json.dumps(sorted(OBSERVED_SOURCES))
    return """#!/usr/bin/env python3
import json
import os
import sys

EVENTS = __SESSION_LEDGER_SMOKE_EVENTS__
SOURCES = __SESSION_LEDGER_SMOKE_SOURCES__

try:
    payload = json.load(sys.stdin)
except (json.JSONDecodeError, OSError):
    payload = {}

if not isinstance(payload, dict):
    payload = {}
event = payload.get(\"hook_event_name\")
session_id = payload.get(\"session_id\")
source = payload.get(\"source\")
expected_session_id = os.environ.get(\"SESSION_LEDGER_SMOKE_SESSION_ID\")
receipt = {
    \"agent_id_present\": isinstance(payload.get(\"agent_id\"), str),
    \"agent_type_present\": isinstance(payload.get(\"agent_type\"), str),
    \"event\": event if event in EVENTS else \"unknown\",
    \"keys\": sorted(key for key in payload if isinstance(key, str)),
    \"session_id_matches_requested\": isinstance(session_id, str) and session_id == expected_session_id,
    \"session_id_present\": isinstance(payload.get(\"session_id\"), str),
    \"source\": source if source in SOURCES else None,
}
target = os.environ.get(\"SESSION_LEDGER_SMOKE_RECEIPTS\")
if target:
    descriptor = os.open(target, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, (json.dumps(receipt, sort_keys=True) + \"\\n\").encode(\"utf-8\"))
    finally:
        os.close(descriptor)
""".replace("__SESSION_LEDGER_SMOKE_EVENTS__", events).replace(
        "__SESSION_LEDGER_SMOKE_SOURCES__", sources
    )


def write_observer_plugin(root: Path) -> Path:
    """Create the disposable structural observer plugin."""
    plugin = root / "session-ledger-host-observer"
    manifest = plugin / ".claude-plugin" / "plugin.json"
    hooks = plugin / "hooks" / "hooks.json"
    observer = plugin / "hooks" / "observe.py"
    manifest.parent.mkdir(parents=True)
    observer.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "name": "session-ledger-host-observer",
                "version": "0.0.0",
                "description": "Disposable structural host observer.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    command = (
        'if command -v python3 >/dev/null 2>&1; then PLUGIN_PYTHON=python3; '
        'else PLUGIN_PYTHON=python; fi; '
        '"$PLUGIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/hooks/observe.py"'
    )
    hooks.write_text(
        json.dumps(
            {
                "hooks": {
                    event: [{"hooks": [{"type": "command", "command": command}]}]
                    for event in sorted(OBSERVED_EVENTS)
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    observer.write_text(observer_source(), encoding="utf-8")
    observer.chmod(0o700)
    return plugin


def read_receipts(path: Path) -> list[dict[str, object]]:
    """Read valid structural observer receipts, ignoring interrupted writes."""
    if not path.exists():
        return []
    receipts: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            receipt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(receipt, dict):
            receipts.append(receipt)
    return receipts


def report_for(
    receipts: list[dict[str, object]],
    *,
    scenario: str,
    command_exit: int | None,
    execution: str = "completed",
) -> dict[str, object]:
    """Summarize structural receipts without returning any host output."""
    event_counts = Counter(
        receipt["event"]
        for receipt in receipts
        if isinstance(receipt.get("event"), str)
    )
    seen_events = frozenset(event_counts)
    required = (
        SUBAGENT_REQUIRED_EVENTS
        if scenario == "subagent"
        else DIRECT_REQUIRED_EVENTS
    )
    lifecycle_receipts = [
        receipt
        for receipt in receipts
        if receipt.get("event") in SUBAGENT_LIFECYCLE_EVENTS
    ]
    agent_receipts = [
        receipt
        for receipt in lifecycle_receipts
        if receipt.get("agent_id_present") or receipt.get("agent_type_present")
    ]
    subagent_payload_seen = bool(agent_receipts)
    matching_agent_sessions = [
        receipt.get("session_id_matches_requested")
        for receipt in lifecycle_receipts
        if receipt.get("session_id_present") is True
    ]
    if not agent_receipts:
        subagent_session_mapping = "not_observed"
    elif len(matching_agent_sessions) != len(lifecycle_receipts):
        subagent_session_mapping = "missing-session-id"
    elif all(matching_agent_sessions):
        subagent_session_mapping = "shared-session"
    elif not any(matching_agent_sessions):
        subagent_session_mapping = "separate-session"
    else:
        subagent_session_mapping = "mixed-session"
    passed = command_exit == 0 and required.issubset(seen_events)
    if scenario == "subagent":
        passed = passed and subagent_session_mapping in {
            "shared-session",
            "separate-session",
        }
    return {
        "claude_exit_code": command_exit,
        "event_counts": dict(sorted(event_counts.items())),
        "execution": execution,
        "host_output": "discarded",
        "outcome": "PASS" if passed else "FAIL",
        "required_events_seen": sorted(required & seen_events),
        "scenario": scenario,
        "subagent_payload_seen": subagent_payload_seen,
        "subagent_session_mapping": subagent_session_mapping,
    }


def smoke_command(
    *, claude: str, observer: Path, scenario: str, budget_usd: str, session_id: str
) -> list[str]:
    """Build the isolated non-interactive command without ambient settings."""
    prompt = SUBAGENT_PROMPT if scenario == "subagent" else DIRECT_PROMPT
    command = [
        claude,
        "--print",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--no-chrome",
        "--permission-prompts",
        "none",
        "--max-budget-usd",
        budget_usd,
        "--session-id",
        session_id,
        "--tools",
        "Agent" if scenario == "subagent" else "",
        "--plugin-dir",
        str(LEDGER_PLUGIN),
        "--plugin-dir",
        str(observer),
    ]
    if scenario == "subagent":
        command.extend(
            [
                "--allowedTools",
                "Agent",
                "--agents",
                json.dumps(SMOKE_AGENT, sort_keys=True),
            ]
        )
    return [*command, prompt]


def run_smoke(
    *, claude: str, config_dir: Path, scenario: str, budget_usd: str, timeout: int
) -> dict[str, object]:
    """Run the host smoke, retaining only structural observer receipts."""
    config_dir = config_dir.expanduser().resolve()
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="session-ledger-host-smoke-") as temp:
        temporary_root = Path(temp)
        receipts_path = temporary_root / "receipts.jsonl"
        observer = write_observer_plugin(temporary_root)
        session_id = str(uuid.uuid4())
        environment = {
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "CLAUDE_CONFIG_DIR": str(config_dir),
            "HOME": str(config_dir),
            "PATH": os.environ.get("PATH", os.defpath),
            "SESSION_LEDGER_SMOKE_RECEIPTS": str(receipts_path),
            "SESSION_LEDGER_SMOKE_SESSION_ID": session_id,
        }
        try:
            completed = subprocess.run(
                smoke_command(
                    claude=claude,
                    observer=observer,
                    scenario=scenario,
                    budget_usd=budget_usd,
                    session_id=session_id,
                ),
                cwd=temporary_root,
                env=environment,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
            exit_code: int | None = completed.returncode
            execution = "completed"
        except FileNotFoundError:
            exit_code = None
            execution = "not_found"
        except subprocess.TimeoutExpired:
            exit_code = None
            execution = "timed_out"
        return report_for(
            read_receipts(receipts_path),
            scenario=scenario,
            command_exit=exit_code,
            execution=execution,
        )


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse a deliberately small, explicit host-smoke interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", default="claude", help="Claude Code executable.")
    parser.add_argument(
        "--config-dir",
        type=Path,
        required=True,
        help="Clean persistent Claude config directory; authenticate it with /login first.",
    )
    parser.add_argument(
        "--scenario", choices=("direct", "subagent"), default="direct"
    )
    parser.add_argument(
        "--budget-usd", default="0.25", help="Maximum Claude Code print budget."
    )
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Print one content-free JSON receipt and return nonzero on a failed smoke."""
    options = parse_arguments(arguments)
    result = run_smoke(
        claude=options.claude,
        config_dir=options.config_dir,
        scenario=options.scenario,
        budget_usd=options.budget_usd,
        timeout=options.timeout,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["outcome"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
