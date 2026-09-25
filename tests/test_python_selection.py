"""Exercise shipped entrypoints with isolated interpreter availability."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import HOOK_SHELL

ROOT = Path(__file__).resolve().parents[1]


def shell_path(path: Path) -> str:
    """PATH inside Git Bash needs /c/... rather than a drive-letter colon."""
    value = path.as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


def write_launcher(path: Path, probe: Path | None = None) -> None:
    """Git Bash can execute scripts even when native Python has no shebang support."""
    args = [Path(sys.executable).as_posix()]
    if probe is not None:
        args.append(probe.as_posix())
    path.write_text("#!/bin/sh\nexec " + shlex.join(args) + ' "$@"\n', encoding="utf-8")
    path.chmod(0o755)


def entrypoints():
    cases = []
    for plugin in ("llm-accuracy", "session-ledger", "evidence-memory"):
        root = ROOT / "plugins" / plugin
        hooks = json.loads((root / "hooks/hooks.json").read_text())["hooks"]
        for event, matchers in hooks.items():
            for index, matcher in enumerate(matchers):
                for hook in matcher["hooks"]:
                    cases.append(
                        pytest.param(
                            plugin, hook["command"], id=f"{plugin}-{event}-{index}"
                        )
                    )
        for skill in sorted(root.glob("skills/*/SKILL.md")):
            for command in re.findall(r"!`([^`]+)`", skill.read_text()):
                cases.append(pytest.param(plugin, command, id=skill.parent.name))
    return cases


@pytest.mark.skipif(not HOOK_SHELL, reason="requires a configured POSIX hook shell")
@pytest.mark.parametrize("plugin,command", entrypoints())
@pytest.mark.parametrize(
    "available", [("python3",), ("python",), ("python3", "python")]
)
@pytest.mark.parametrize("exit_code", [0, 7])
def test_interpreter_selection_preserves_io_arguments_and_exit_status(
    tmp_path, plugin, command, available, exit_code
):
    root = tmp_path / "plugin root's copy"
    hooks = root / "hooks"
    hooks.mkdir(parents=True)
    target = re.search(r'/hooks/([^" ]+\.py)', command).group(1)
    (hooks / target).write_text("# synthetic hook target\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in available:
        probe = tmp_path / (name + "_probe.py")
        probe.write_text(
            "import json, sys\n"
            f"print(json.dumps({{'interpreter': {name!r}, 'args': sys.argv[1:], 'stdin': sys.stdin.read()}}))\n"
            f"sys.exit({exit_code})\n"
        )
        write_launcher(bin_dir / name, probe)
    env = {
        **os.environ,
        "PATH": str(bin_dir),
        "CLAUDE_PLUGIN_ROOT": root.as_posix(),
        "CLAUDE_PLUGIN_DATA": (tmp_path / "ledger data's directory").as_posix(),
        "CLAUDE_SESSION_ID": "synthetic-session",
    }
    result = subprocess.run(
        [HOOK_SHELL, "-c", "PATH=" + shlex.quote(shell_path(bin_dir)) + "; " + command],
        input="synthetic input",
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )
    assert result.returncode == exit_code, result.stderr
    assert result.stderr == ""
    # One JSON object also proves a failed hook was not retried with python.
    observed = json.loads(result.stdout)
    assert observed["interpreter"] == available[0]
    assert observed["stdin"] == "synthetic input"
    args = [(hooks / target).as_posix()]
    if plugin in ("session-ledger", "evidence-memory"):
        tail = command.split(f'/hooks/{target}" ', 1)[1]
        for key, value in env.items():
            tail = tail.replace("${" + key + "}", value)
        args += shlex.split(tail)
    assert observed["args"] == args


@pytest.mark.skipif(not HOOK_SHELL, reason="requires a configured POSIX hook shell")
@pytest.mark.parametrize("plugin,command", entrypoints())
def test_real_entrypoints_run_with_only_python(tmp_path, plugin, command):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_launcher(bin_dir / "python")
    env = {
        **os.environ,
        "PATH": str(bin_dir),
        "CLAUDE_PLUGIN_ROOT": (ROOT / "plugins" / plugin).as_posix(),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "synthetic ledger"),
        "CLAUDE_SESSION_ID": "synthetic-session",
    }
    result = subprocess.run(
        [HOOK_SHELL, "-c", "PATH=" + shlex.quote(shell_path(bin_dir)) + "; " + command],
        input='{"prompt":"Analyze retention by cohort."}',
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    if "analysis-contract-injector.py" in command:
        assert "analysis contract" in result.stdout
    if " clear " in command:
        assert "Cleared local Session Ledger state." in result.stdout
    if " begin-plan " in command:
        assert "Started a fresh Session Ledger plan boundary" in result.stdout


@pytest.mark.skipif(not HOOK_SHELL, reason="requires a configured POSIX hook shell")
def test_generated_host_observer_runs_with_only_python(tmp_path):
    from test_session_ledger_host_smoke import load_smoke

    smoke = load_smoke()
    plugin = smoke.write_observer_plugin(tmp_path)
    config = json.loads((plugin / "hooks/hooks.json").read_text())["hooks"]
    command = config["Stop"][0]["hooks"][0]["command"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_launcher(bin_dir / "python")
    receipts = tmp_path / "synthetic-receipts.jsonl"
    env = {
        **os.environ,
        "CLAUDE_PLUGIN_ROOT": plugin.as_posix(),
        "SESSION_LEDGER_SMOKE_RECEIPTS": str(receipts),
        "SESSION_LEDGER_SMOKE_SESSION_ID": "synthetic-session",
    }
    result = subprocess.run(
        [HOOK_SHELL, "-c", "PATH=" + shlex.quote(shell_path(bin_dir)) + "; " + command],
        input=json.dumps(
            {"hook_event_name": "Stop", "session_id": "synthetic-session"}
        ),
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    assert len(receipts.read_text().splitlines()) == 1
    assert json.loads(receipts.read_text())["event"] == "Stop"
