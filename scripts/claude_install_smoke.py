#!/usr/bin/env python3
"""Clean-profile Claude Code installation smoke for the llm-accuracy plugin.

Installs the committed plugin through a local-path marketplace into an
auth-only temporary profile, compares the installed bytes with the tracked
source, then runs bounded no-tool sessions through that installation and
through the release archive in a second profile. Answers stay in memory: the
receipt holds only fixed labels, counts, booleans and hashes, never a prompt,
answer, credential or hook payload.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/llm-accuracy/scripts"))
sys.path.insert(0, str(ROOT / "scripts"))

from build_plugin_zip import (  # noqa: E402
    PLUGIN,
    build_archive,
    plugin_version,
    tracked_plugin_files,
)
from eval_technical_behavior import (  # noqa: E402
    divider_precedes_footer,
    footer_present,
)

# _termination_cleanup lets SIGTERM unwind the temporary credential copy.
from host_probe import (  # noqa: E402
    CONTROL_VARS,
    _termination_cleanup,
    communicate,
)

SCOPE = "fresh_profile_local_marketplace_and_archive"
TECHNICAL_PROMPT = (
    "All local unit tests pass after a retry-handling patch. Production still runs "
    "the previous build and has not been checked. Can we call the production "
    "incident resolved? Answer briefly."
)
BYPASS_PROMPT = "Reply with the single word ready. # fidelity-ok"
SESSION_FIELDS = (
    "status",
    "result_count",
    "fidelity_hook_responses",
    "hook_response_count",
    "builtin_signal_responses",
    "host_inventory",
    "resolved_model",
)
INSTALL_CHECKS = (
    "marketplace_add",
    "plugin_install",
    "python_configured",
    "installed_enabled_version",
    "installed_files_match_source",
)
LIMITATIONS = [
    "Local-path marketplace from this checkout, not a hosted GitHub installation",
    "Auth-only temporary profiles; the current session and other machines are not verified",
    "One model run per session path: a screen, not an adherence rate",
    "Footer layout is observed, not gated; hook delivery does not establish factual accuracy",
    "Custom-phrase triggers are covered by unit tests, not by this live smoke",
]


def git_value(*arguments: str) -> str:
    """Return one Git value for the checkout under test."""
    return subprocess.run(
        ["git", "-C", str(ROOT), *arguments],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def marketplace_plugin_id() -> str:
    """Name the plugin as the local marketplace registers it."""
    manifest = json.loads(
        (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
    )
    return f"{PLUGIN.name}@{manifest['name']}"


def host_version(claude: str) -> str:
    """Report the CLI version only when it has the expected shape."""
    try:
        text = subprocess.run(
            [claude, "--version"], capture_output=True, text=True, timeout=60
        ).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unreported"
    if re.fullmatch(r"\d[0-9A-Za-z.+-]{0,40}(?: \(Claude Code\))?", text):
        return text
    return "unreported"


def platform_label() -> str:
    """Name the operating system without host or user details."""
    system = platform.system() or "unknown"
    if system == "Linux" and "microsoft" in platform.release().lower():
        return "Linux/WSL"
    return system


def auth_profile(root: Path, *, ci: bool = False, live: bool = True) -> dict[str, str]:
    """Create a profile holding only the login, with accuracy controls removed."""
    source = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        / ".credentials.json"
    )
    profile = root / "profile"
    profile.mkdir(mode=0o700)
    if not ci and source.is_file():
        shutil.copyfile(source, profile / source.name)
        (profile / source.name).chmod(0o600)
    env = {key: value for key, value in os.environ.items() if key not in CONTROL_VARS}
    if ci and live:
        names = ('ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN')
        present = [name for name in names if os.environ.get(name, '').strip()]
        if len(present) != 1:
            raise ValueError('ci_authentication_required')
        env[present[0]] = os.environ[present[0]]
    env["CLAUDE_CONFIG_DIR"] = str(profile)
    return env


def run_cli(
    command: list[str], env: dict[str, str], cwd: Path, input_text: str | None = None
) -> subprocess.CompletedProcess:
    """Run one setup command; callers read only exit codes or parsed fields."""
    try:
        return subprocess.run(
            command, env=env, cwd=cwd, input=input_text,
            capture_output=True, text=True, encoding="utf-8", timeout=180
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return subprocess.CompletedProcess(command, -1, "", "")


def installed_entry(listing: str, plugin_id: str) -> dict:
    """Find the plugin in `claude plugin list --json` output."""
    try:
        entries = json.loads(listing)
    except ValueError:
        return {}
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("id") == plugin_id:
            return entry
    return {}


def path_inside(raw: object, parent: Path) -> Path | None:
    """Accept an install path only when it resolves inside the temporary profile."""
    if not isinstance(raw, str) or not raw:
        return None
    path = Path(raw).resolve()
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return None
    return path if path.is_dir() else None


def installed_mismatches(
    tracked: list[Path], source_root: Path, installed: Path
) -> int:
    """Count tracked files that are missing or differ in the installation."""
    count = 0
    for source in tracked:
        target = installed / source.relative_to(source_root)
        if not target.is_file() or target.read_bytes() != source.read_bytes():
            count += 1
    return count


def session_command(
    claude: str, model: str, plugin_dir: Path | None = None
) -> list[str]:
    """Run one no-tool, no-MCP turn without saving the session.

    Without `plugin_dir` the profile's settings load its installed plugins. With
    it, profile settings are ignored so only that plugin directory loads.
    """
    command = [
        claude,
        "--print",
        "--input-format",
        "stream-json",
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--tools",
        "",
        "--no-session-persistence",
        "--model",
        model,
        "--max-budget-usd",
        "1.00",
    ]
    if plugin_dir is not None:
        command.extend(["--setting-sources", "", "--plugin-dir", str(plugin_dir)])
        manifest = json.loads(
            (plugin_dir / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
        )
        if "python_executable" not in manifest.get("userConfig", {}):
            raise ValueError("archive is missing the required Python option")
        command.extend(["--settings", json.dumps({"pluginConfigs": {
            manifest["name"]: {"options": {"python_executable": sys.executable}}
        }})])
    return command


def stream_input(prompt: str) -> str:
    """Encode one user turn for stream-json input."""
    message = {"type": "user", "message": {"role": "user", "content": prompt}}
    return json.dumps(message) + "\n"


def session_summary(result: dict, expected_fidelity: int) -> dict:
    """Reduce a probe result to fixed fields; the answer never leaves memory."""
    summary = {field: result.get(field) for field in SESSION_FIELDS}
    summary["expected_fidelity_hook_responses"] = expected_fidelity
    if expected_fidelity:
        answers = result.get("answers") or [""]
        summary["footer_present"] = footer_present(answers[-1])
        summary["divider_before_footer"] = divider_precedes_footer(answers[-1])
    summary["passed"] = (
        result.get("status") == "ok"
        and result.get("result_count") == 1
        and result.get("fidelity_hook_responses") == expected_fidelity
    )
    return summary


def receipt_passed(checks: dict) -> bool:
    """Gate on installation, byte match, hook delivery and cleanup only."""
    sessions = [value for value in checks.values() if isinstance(value, dict)]
    return (
        all(checks.get(key) is True for key in INSTALL_CHECKS)
        and checks.get("isolated_cleanup") is True
        and all(session.get("passed") is True for session in sessions)
    )


def run_smoke(claude: str, model: str, timeout: int, live: bool) -> dict:
    """Install, compare and probe inside one temporary directory."""
    version = plugin_version(PLUGIN)
    tracked = tracked_plugin_files(PLUGIN)
    plugin_id = marketplace_plugin_id()
    checks: dict = {}
    with (
        _termination_cleanup(),
        tempfile.TemporaryDirectory(prefix="llm-accuracy-install-smoke-") as directory,
    ):
        root = Path(directory)
        work = root / "work"
        work.mkdir()
        env = auth_profile(root)
        profile = Path(env["CLAUDE_CONFIG_DIR"])
        add = run_cli([claude, "plugin", "marketplace", "add", str(ROOT)], env, work)
        checks["marketplace_add"] = add.returncode == 0
        install = run_cli([claude, "plugin", "install", plugin_id], env, work)
        checks["plugin_install"] = install.returncode == 0
        configure = run_cli(
            [claude, "plugin", "configure", plugin_id, "--values-stdin"],
            env, work, json.dumps({"python_executable": sys.executable}),
        )
        checks["python_configured"] = configure.returncode == 0
        listing = run_cli([claude, "plugin", "list", "--json"], env, work)
        entry = installed_entry(listing.stdout, plugin_id)
        checks["installed_enabled_version"] = (
            listing.returncode == 0
            and entry.get("enabled") is True
            and entry.get("version") == version
        )
        installed = path_inside(entry.get("installPath"), profile)
        checks["tracked_files"] = len(tracked)
        checks["installed_byte_mismatches"] = (
            installed_mismatches(tracked, PLUGIN, installed)
            if installed
            else len(tracked)
        )
        checks["installed_files_match_source"] = (
            installed is not None and checks["installed_byte_mismatches"] == 0
        )
        if live:
            for name, prompt, expected in (
                ("installed_default_session", TECHNICAL_PROMPT, 1),
                ("installed_bypass", BYPASS_PROMPT, 0),
            ):
                result = communicate(
                    session_command(claude, model),
                    work,
                    env,
                    stream_input(prompt),
                    timeout,
                )
                checks[name] = session_summary(result, expected)
        archive = build_archive(
            root / "archive" / f"{PLUGIN.name}-{version}.zip", PLUGIN
        )
        archive_sha256 = hashlib.sha256(archive.read_bytes()).hexdigest()
        if live:
            extracted = root / "archive" / PLUGIN.name
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extracted)
            result = communicate(
                session_command(claude, model, extracted),
                work,
                auth_profile(root / "archive"),
                stream_input(TECHNICAL_PROMPT),
                timeout,
            )
            checks["archive_session"] = session_summary(result, 1)
    checks["isolated_cleanup"] = not root.exists()
    if not live:
        checks["live_sessions"] = "skipped"
    return {
        "schema_version": 1,
        "scope": SCOPE,
        "source_commit": git_value("rev-parse", "HEAD"),
        "plugin_tree": git_value(
            "rev-parse", f"HEAD:{PLUGIN.relative_to(ROOT).as_posix()}"
        ),
        "plugin_version": version,
        "host_version": host_version(claude),
        "model_requested": model,
        "checks": checks,
        "archive_sha256": archive_sha256,
        "passed": receipt_passed(checks),
        "tested_on": datetime.date.today().isoformat(),
        "platform": platform_label(),
        "limitations": LIMITATIONS
        + ([] if live else ["Live sessions skipped: installation evidence only"]),
    }


def parse_arguments(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse a small, explicit smoke interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude", default="claude", help="Claude Code executable.")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--timeout", type=int, default=240, help="Seconds per session.")
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help="Install and compare only; no model calls.",
    )
    parser.add_argument(
        "--receipt", type=Path, help="Also write the JSON receipt here."
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Print one raw-free JSON receipt; exit nonzero when the smoke fails."""
    options = parse_arguments(arguments)
    if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]{1,100}", options.model):
        print("claude_install_smoke: invalid model name", file=sys.stderr)
        return 2
    claude = shutil.which(options.claude)
    if not claude:
        print("claude_install_smoke: Claude Code executable not found", file=sys.stderr)
        return 2
    try:
        receipt = run_smoke(
            claude, options.model, options.timeout, not options.skip_live
        )
    except ValueError as error:
        # Raised for uncommitted plugin changes or a failed boundary check.
        print(f"claude_install_smoke: {error}", file=sys.stderr)
        return 2
    except (OSError, KeyError, subprocess.SubprocessError) as error:
        # Name the failure class only: messages can carry local paths.
        print(f"claude_install_smoke: {type(error).__name__}", file=sys.stderr)
        return 2
    text = json.dumps(receipt, indent=2) + "\n"
    print(text, end="")
    if options.receipt:
        try:
            options.receipt.parent.mkdir(parents=True, exist_ok=True)
            options.receipt.write_text(text, encoding="utf-8")
        except OSError as error:
            print(
                f"claude_install_smoke: receipt not written ({type(error).__name__})",
                file=sys.stderr,
            )
            return 2
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
