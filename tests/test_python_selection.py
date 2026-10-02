"""Codex's separate POSIX launcher probes usability before executing once."""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import HOOK_SHELL

ROOT = Path(__file__).resolve().parents[1]


def shell_path(path):
    value = path.as_posix()
    return "/" + value[0].lower() + value[2:] if os.name == "nt" else value


def write_launcher(path, *, broken=False):
    text = "#!/bin/sh\n"
    text += "exit 49\n" if broken else "exec " + shlex.quote(Path(sys.executable).as_posix()) + ' "$@"\n'
    path.write_text(text)
    path.chmod(0o755)


@pytest.mark.skipif(not HOOK_SHELL, reason="Codex POSIX launcher needs a POSIX shell")
@pytest.mark.parametrize("broken", [False, True])
def test_codex_selection_probes_without_consuming_stdin_and_does_not_retry_hook(tmp_path, broken):
    root = tmp_path / "plugin O'Brien é"
    (root / "hooks").mkdir(parents=True)
    (root / "hooks/memory.py").write_text('import json,sys\nprint(json.dumps({"args":sys.argv[1:],"stdin":sys.stdin.read()}))\nsys.exit(7)\n')
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_launcher(bin_dir / "python3", broken=broken)
    write_launcher(bin_dir / "python")
    config = json.loads((ROOT / "plugins/evidence-memory/hooks/codex-hooks.json").read_text())["hooks"]
    for groups in config.values():
        handler = groups[0]["hooks"][0]
        environment = dict(os.environ, CLAUDE_PLUGIN_ROOT=root.as_posix(), CLAUDE_PLUGIN_DATA="synthetic data")
        result = subprocess.run([HOOK_SHELL, "-c", "PATH=" + shlex.quote(shell_path(bin_dir)) + "; " + handler["command"]],
                                input="synthetic stdin", capture_output=True, text=True, env=environment, timeout=5)
        assert result.returncode == 7 and result.stderr == ""
        observed = json.loads(result.stdout)
        assert observed["stdin"] == "synthetic stdin"
        assert observed["args"][1:] == ["--plugin-data", "synthetic data"]


def test_codex_skill_validates_interpreter_before_status():
    skill = (ROOT / "plugins/evidence-memory/skills/memory/SKILL.md").read_text()
    assert 'sys.version_info < (3, 9)' in skill
    assert 'test -n "$MEMORY_PYTHON" || exit 1' in skill
