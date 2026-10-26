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
from hook_shell import shell_argv


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hooks"))
from accuracy_config import claim_fidelity_mode, read_configuration  # noqa: E402


PROMPTS = (
    ("analysis", "Analyze customer retention.", "CC_SKIP_ANALYSIS"),
    ("fusion_evidence", "Why do database rows disagree?", "CC_SKIP_FUSION_EVIDENCE"),
    ("claim_fidelity", "Does this prove causation?", "CC_SKIP_CLAIM_FIDELITY"),
)

LIVE_COUNTER_DEFINITIONS = {
    "fidelity_hook_responses": "Hook-response events containing claim-fidelity guidance.",
    "hook_response_count": "All hook-response events, including silent hook responses.",
    "builtin_signal_responses": (
        "Legacy name: hook-response events containing PARTIAL RESULT SIGNAL "
        "warnings, not keyword matches. The tool-free acknowledgement probe "
        "normally reports zero; zero does not mean prompt checks are inactive."
    ),
}


def skill_frontmatter(text: str, directory_name: str) -> str:
    """Check shipped required metadata, without claiming full YAML validation."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return "invalid_delimiters"
    header = lines[1:lines.index("---", 1)]
    fields = {}
    for key in ("name", "description"):
        values = [line[len(key) + 1:].strip() for line in header if line.startswith(key + ":")]
        if len(values) != 1 or not values[0]:
            return "invalid_required_fields"
        value = values[0]
        # The shipped skills use one-line plain or quoted strings. Other YAML
        # forms need a host/YAML parser; do not call them valid or invalid here.
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                return "unsupported_required_field_format"
        elif value.startswith("'"):
            if not re.fullmatch(r"'(?:[^']|'')*'", value):
                return "unsupported_required_field_format"
            value = value[1:-1].replace("''", "'")
        elif (
            value[0] in "|>[]{}&*!#%@`"
            or ": " in value or " #" in value
            or value.lower() in {"null", "~", "true", "false", "yes", "no", "on", "off"}
            or re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value)
        ):
            return "unsupported_required_field_format"
        if not isinstance(value, str) or not value.strip():
            return "invalid_required_fields"
        fields[key] = value
    if fields["name"] != directory_name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"]):
        return "invalid_name"
    return "required_fields_valid"


def skill_inventory(root: Path) -> dict:
    """Inspect package skill files only; registration is not skill delivery."""
    inventory = {
        "status": "unavailable",
        "validation_scope": "delimiters_and_required_name_description_only_not_full_yaml",
        "host_listing": "unverified",
        "items": [],
    }
    try:
        directories = sorted(path for path in (root / "skills").iterdir() if path.is_dir())
    except OSError:
        return inventory
    for directory in directories:
        item = {"name": directory.name, "skill_md": "readable", "frontmatter": "unavailable"}
        try:
            text = (directory / "SKILL.md").read_text(encoding="utf-8")
        except FileNotFoundError:
            item["skill_md"] = "missing"
        except UnicodeError:
            item["skill_md"] = "invalid_encoding"
        except OSError:
            item["skill_md"] = "unreadable"
        else:
            item["frontmatter"] = skill_frontmatter(text, directory.name)
        inventory["items"].append(item)
    inventory["status"] = "ok" if directories and all(
        item["frontmatter"] == "required_fields_valid" for item in inventory["items"]
    ) else "attention"
    return inventory


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
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
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
        "plugin": "llm-accuracy",
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


def python_status(executable: str) -> dict:
    try:
        result = subprocess.run([executable, "-c", "import sys,json; print(json.dumps(list(sys.version_info[:3])))"],
                                capture_output=True, text=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        version = json.loads(result.stdout) if result.returncode == 0 else None
        if not isinstance(version, list) or len(version) != 3 or not all(type(v) is int for v in version):
            return {"status": "unusable"}
        return {"status": "ok" if tuple(version) >= (3, 9) else "unsupported_version",
                "version": ".".join(map(str, version))}
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {"status": "unusable"}


def command_argv(handler: dict, root: Path, executable: str) -> list[str]:
    if not isinstance(handler.get("command"), str) or 'python-launcher.cmd' not in handler['command']:
        raise ValueError("registration")
    return shell_argv(handler['command'], os.environ)



# hooks.json passes this action to the claim-fidelity SessionStart registration.
SESSION_START_ACTION = "claim-fidelity-trigger.py:session-start"
SESSION_PROBE = "claim_fidelity_session"
# Outside session mode the SessionStart command is expected to stay silent.
SESSION_NOT_USED = "not_used_in_mode"


def probe_command(
    command: dict, prompt: str, root: Path, executable: str, event: str = "UserPromptSubmit"
) -> str:
    env = {**os.environ, "CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE": executable}
    payload = {"prompt": prompt} if event == "UserPromptSubmit" else {"hook_event_name": event, "source": "startup"}
    try:
        result = subprocess.run(
            command_argv(command, root, executable),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired:
        return "timeout"
    except (OSError, ValueError):
        return "execution_failed"
    if result.returncode != 0:
        return "execution_failed"
    try:
        payload = json.loads(result.stdout)
        context = payload["hookSpecificOutput"]
        valid = (
            context["hookEventName"] == event
            and isinstance(context["additionalContext"], str)
            and bool(context["additionalContext"])
        )
        return "emitted" if valid else "invalid_response"
    except (ValueError, KeyError, TypeError):
        return "no_context" if not result.stdout.strip() else "invalid_response"


def check_hooks(root: Path, executable: str, mode: str) -> dict[str, str]:
    try:
        registered = json.loads((root / "hooks/hooks.json").read_text())["hooks"]
        commands = [h for group in registered["UserPromptSubmit"] for h in group["hooks"]]
        sessions = [
            h
            for group in registered["SessionStart"]
            for h in group["hooks"]
            if isinstance(h, dict) and SESSION_START_ACTION in h.get("command", "")
        ]
        if len(commands) != len(PROMPTS) or len(sessions) != 1 or not all(
            isinstance(command, dict) and "python-launcher.cmd" in command.get("command", "")
            for command in commands + sessions
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
            else probe_command(command, prompt, root, executable)
        )
    # Session mode sends the general reminder from SessionStart, not prompts.
    outcomes[SESSION_PROBE] = (
        "disabled"
        if os.environ.get("CC_SKIP_CLAIM_FIDELITY") == "1"
        else probe_command(sessions[0], "", root, executable, "SessionStart")
        if mode == "session"
        else SESSION_NOT_USED
    )
    return outcomes


def diagnose(root: Path = ROOT, python_executable: str | None = None) -> dict:
    phrases, config_status = read_configuration()
    try:
        manifest = json.loads((root / ".claude-plugin/plugin.json").read_text())
        version = safe_version(manifest["version"])
        if version == "unknown":
            raise ValueError("version")
    except (OSError, ValueError, KeyError, TypeError):
        version = "invalid_manifest"
    mode, mode_recognized = claim_fidelity_mode()
    executable = python_executable or os.environ.get("CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE") or sys.executable
    interpreter = python_status(executable)
    hooks = check_hooks(root, executable, mode) if interpreter["status"] == "ok" else {"interpreter": interpreter["status"]}
    skills = skill_inventory(root)
    healthy = (
        config_status in {"ok", "missing_default"}
        and mode_recognized
        and skills["status"] == "ok"
        and all(
            v == "emitted" or (k, v) == (SESSION_PROBE, SESSION_NOT_USED)
            for k, v in hooks.items()
        )
    )
    return {
        "status": "ok" if healthy and version != "invalid_manifest" else "attention",
        "package_version": version,
        "mode": mode,
        "mode_recognized": mode_recognized,
        "config_status": config_status,
        "phrase_counts": {
            family: len(phrases.get(family, [])) for family, _, _ in PROMPTS
        },
        "hook_commands": hooks,
        "skills": skills,
        "python": interpreter,
        "python_selection": "explicit" if python_executable else "hook_option" if os.environ.get("CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE") else "doctor_process",
        "installed_python_option": "unverified",
        "current_session_activation": "unverified",
        "scope": "local_package_commands_skills_and_user_controls",
    }


def live_passed(live: dict) -> bool:
    return (
        live.get("status") == "ok"
        and bool(live.get("fidelity_hook_responses"))
        and live.get("acknowledgement_correct") is True
    )


def registration_matches(report: dict) -> bool:
    registration = report.get("host_registration", {})
    rows = registration.get("installations", [])
    return (
        registration.get("status") == "listed"
        and len(rows) == 1
        and rows[0].get("enabled") is True
        and rows[0].get("version") not in (None, "unknown")
        and rows[0].get("version") == report.get("package_version")
    )


def presentation(report: dict) -> dict[str, str]:
    """Render bounded diagnostic claims from results, never infer host correctness."""
    emitted = sum(
        report.get("hook_commands", {}).get(family) == "emitted"
        for family, _, _ in PROMPTS
    )
    session = report.get("hook_commands", {}).get(SESSION_PROBE)
    session_text = (
        ""
        if session is None
        else "; the session-start probe emitted the general reminder"
        if session == "emitted"
        else "; the session-start reminder is not used in this mode"
        if session == SESSION_NOT_USED
        else "; the session-start probe did not emit the general reminder"
    )
    live = report.get("live")
    live_ok = isinstance(live, dict) and live_passed(live)
    registration_ok = registration_matches(report)
    skills = report.get("skills")
    skill_text = ""
    if isinstance(skills, dict):
        items = skills.get("items", [])
        valid = sum(item.get("frontmatter") == "required_fields_valid" for item in items)
        skill_text = (
            f"; {valid}/{len(items)} local skill files passed required-frontmatter checks"
            if items else "; local skill inventory unavailable or empty"
        )
    attention = (
        report.get("status") != "ok"
        or (isinstance(skills, dict) and skills.get("status") != "ok")
        or emitted != len(PROMPTS)
        or session not in (None, "emitted", SESSION_NOT_USED)
        or (live is not None and not live_ok)
    )
    live_text = (
        "live check not run"
        if live is None
        else "isolated live check passed"
        if live_ok
        else "isolated live check did not pass"
    )
    return {
        "status": "attention" if attention else "local_probes_passed",
        "headline": "Diagnostic checks need attention."
        if attention
        else "Local package probes passed; current-session activation is unverified.",
        "checked": f"{emitted}/{len(PROMPTS)} prompt-hook command probes emitted reminders{session_text}{skill_text}; {live_text}.",
        "gap": (
            "Current-session activation, substantive response compliance and factual accuracy remain unverified."
            " Host skill listing is unverified; plugin registration does not establish skill delivery."
            + ("" if registration_ok else " Host registration requires inspection.")
        ),
        "next": "Resolve the reported diagnostic issues, then rerun the doctor."
        if attention
        else "Inspect LLM Accuracy entries in the host's plugin interface, then test in a fresh session."
        if not registration_ok
        else "Test a substantive answer in a fresh session and inspect its claim support."
        if live_ok
        else "Use --live for an isolated delivery check, then test a substantive answer in a fresh session.",
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
        "--python-executable", help="Working Python executable name or path; no shell or arguments"
    )
    args = parser.parse_args()
    report = diagnose(python_executable=args.python_executable)
    report["host_registration"] = installation_inventory()
    if args.live:
        live = run_probe(
            ["Reply exactly OK. Do not use tools."], ROOT, model=args.model
        )
        answers = live.pop("answers", [])
        live["acknowledgement_correct"] = answers == ["OK"]
        live["scope"] = "isolated_explicit_plugin_load_with_default_controls"
        live["counter_definitions"] = LIVE_COUNTER_DEFINITIONS
        report["live"] = live
        if not live_passed(live):
            report["status"] = "attention"
    report["presentation"] = presentation(report)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
