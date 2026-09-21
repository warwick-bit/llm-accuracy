"""Exercise shipped entrypoints with isolated interpreter availability."""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def entrypoints():
    cases = []
    for plugin in ("llm-accuracy", "session-ledger"):
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


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX hook shell")
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
        launcher = bin_dir / name
        launcher.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"print(json.dumps({{'interpreter': {name!r}, 'args': sys.argv[1:], 'stdin': sys.stdin.read()}}))\n"
            f"sys.exit({exit_code})\n"
        )
        launcher.chmod(0o755)
    env = {
        "PATH": str(bin_dir),
        "CLAUDE_PLUGIN_ROOT": str(root),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "ledger data's directory"),
        "CLAUDE_SESSION_ID": "synthetic-session",
    }
    result = subprocess.run(
        ["/bin/sh", "-c", command],
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
    args = [str(hooks / target)]
    if plugin == "session-ledger":
        tail = command.split(f'/hooks/{target}" ', 1)[1]
        for key, value in env.items():
            tail = tail.replace("${" + key + "}", value)
        args += shlex.split(tail)
    assert observed["args"] == args


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX hook shell")
@pytest.mark.parametrize("plugin,command", entrypoints())
def test_real_entrypoints_run_with_only_python(tmp_path, plugin, command):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "python").symlink_to(sys.executable)
    env = {
        "PATH": str(bin_dir),
        "CLAUDE_PLUGIN_ROOT": str(ROOT / "plugins" / plugin),
        "CLAUDE_PLUGIN_DATA": str(tmp_path / "synthetic ledger"),
        "CLAUDE_SESSION_ID": "synthetic-session",
    }
    result = subprocess.run(
        ["/bin/sh", "-c", command],
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
