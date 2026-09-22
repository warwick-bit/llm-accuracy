#!/usr/bin/env python3
"""Check this package and user controls; never mistake a local probe for host activation."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from host_probe import run_probe


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
from accuracy_config import read_configuration  # noqa: E402


PROMPTS = (
    ("analysis", "Analyze customer retention.", "CC_SKIP_ANALYSIS"),
    ("fusion_evidence", "Why do database rows disagree?", "CC_SKIP_FUSION_EVIDENCE"),
    ("claim_fidelity", "Does this prove causation?", "CC_SKIP_CLAIM_FIDELITY"),
)


def safe_version(value: object) -> str:
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(r"\d{1,4}\.\d{1,4}\.\d{1,4}(?:-[a-z0-9.]{1,16})?", value)
        else "unknown"
    )


def installation_inventory() -> dict:
    """Read the host's public listing; emit only allowlisted version/status fields."""
    executable = shutil.which("claude")
    if not executable:
        return {"status": "host_unavailable"}
    try:
        result = subprocess.run(
            [executable, "plugin", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        rows = json.loads(result.stdout) if result.returncode == 0 else None
        if not isinstance(rows, list):
            return {"status": "unavailable"}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"status": "unavailable"}
    matches = [
        row
        for row in rows
        if isinstance(row, dict)
        and isinstance(row.get("id"), str)
        and row["id"].split("@", 1)[0] == "llm-accuracy"
    ]
    return {
        "status": "listed" if matches else "not_listed",
        "installations": [
            {
                "version": safe_version(row.get("version")),
                "enabled": row.get("enabled")
                if type(row.get("enabled")) is bool
                else "unknown",
            }
            for row in matches
        ],
    }


def find_shell() -> str | None:
    if os.name == "nt":
        candidate = (
            Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            / "Git/bin/bash.exe"
        )
        return str(candidate) if candidate.is_file() else shutil.which("bash")
    return shutil.which("sh")


def probe_command(command: str, prompt: str, root: Path, shell: str) -> str:
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(root)}
    try:
        result = subprocess.run(
            [shell, "-c", command],
            input=json.dumps({"prompt": prompt}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError:
        return "execution_failed"
    if result.returncode != 0:
        return "execution_failed"
    try:
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]
        valid = (
            context["hookEventName"] == "UserPromptSubmit"
            and isinstance(context["additionalContext"], str)
            and bool(context["additionalContext"])
        )
        return "emitted" if valid else "invalid_response"
    except (ValueError, KeyError, TypeError):
        return "no_context" if not result.stdout.strip() else "invalid_response"


def check_hooks(root: Path, shell: str | None) -> dict[str, str]:
    try:
        groups = json.loads((root / "hooks/hooks.json").read_text())["hooks"][
            "UserPromptSubmit"
        ]
        commands = [h["command"] for group in groups for h in group["hooks"]]
        if len(commands) != len(PROMPTS) or not all(
            isinstance(command, str) for command in commands
        ):
            raise ValueError("registration")
    except (OSError, ValueError, KeyError, TypeError):
        return {"registration": "invalid"}
    outcomes = {}
    for command, (family, prompt, skip) in zip(commands, PROMPTS):
        disabled = (
            os.environ.get(skip) == "1"
            if family == "claim_fidelity"
            else bool(os.environ.get(skip))
        )
        outcomes[family] = (
            "disabled"
            if disabled
            else probe_command(command, prompt, root, shell)
            if shell
            else "shell_unavailable"
        )
    return outcomes


def diagnose(root: Path = ROOT, shell: str | None = None) -> dict:
    phrases, config_status = read_configuration()
    try:
        manifest = json.loads((root / ".claude-plugin/plugin.json").read_text())
        version = safe_version(manifest["version"])
        if version == "unknown":
            raise ValueError("version")
    except (OSError, ValueError, KeyError, TypeError):
        version = "invalid_manifest"
    mode = os.environ.get("CC_CLAIM_FIDELITY_MODE", "general").strip().lower()
    hooks = check_hooks(root, shell or find_shell())
    healthy = (
        config_status in {"ok", "missing_default"}
        and mode in {"general", "targeted"}
        and all(v == "emitted" for v in hooks.values())
    )
    return {
        "status": "ok" if healthy and version != "invalid_manifest" else "attention",
        "package_version": version,
        "mode": "targeted" if mode == "targeted" else "general",
        "mode_recognized": mode in {"general", "targeted"},
        "config_status": config_status,
        "phrase_counts": {
            family: len(phrases.get(family, [])) for family, _, _ in PROMPTS
        },
        "hook_commands": hooks,
        "current_session_activation": "unverified",
        "scope": "local_package_commands_and_user_controls",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one isolated Claude model request using existing subscription login",
    )
    parser.add_argument("--model", default="sonnet")
    parser.add_argument(
        "--shell", help="Explicit POSIX shell executable, such as native Git Bash"
    )
    args = parser.parse_args()
    report = diagnose(shell=args.shell)
    report["host_registration"] = installation_inventory()
    if args.live:
        live = run_probe(
            ["Reply exactly OK. Do not use tools."], ROOT, model=args.model
        )
        answers = live.pop("answers", [])
        live["acknowledgement_correct"] = answers == ["OK"]
        live["scope"] = "isolated_explicit_plugin_load_with_default_controls"
        report["live"] = live
        if (
            live["status"] != "ok"
            or not live.get("fidelity_hook_responses")
            or answers != ["OK"]
        ):
            report["status"] = "attention"
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
