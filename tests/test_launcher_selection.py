"""Interpreter selection probes must not consume input or retry a real hook."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(os.name == 'nt', reason='POSIX fallback fixtures; native vectors run separately')


def invoke(tmp_path, candidates, override=''):
    plugin = tmp_path / "plugin O'Brien é $ literal"
    hooks = plugin / 'hooks'
    hooks.mkdir(parents=True)
    origin = ROOT / 'plugins/llm-accuracy/hooks'
    for name in ('python-launcher.cmd', 'hook_runner.py'):
        shutil.copyfile(origin / name, hooks / name)
    (hooks / 'synthetic.py').write_text('import sys; print(sys.stdin.read(), end=""); sys.exit(7)\n')
    path = tmp_path / 'interpreters'
    path.mkdir()
    for name, valid in candidates.items():
        binary = path / name
        if valid:
            binary.symlink_to(sys.executable)
        else:
            binary.write_text('#!/bin/sh\nexit 49\n')
            binary.chmod(0o755)
    command = 'set -- "synthetic.py"; (. "${CLAUDE_PLUGIN_ROOT}/hooks/python-launcher.cmd" "synthetic.py"); exit 0'
    env = {'PATH': str(path), 'CLAUDE_PLUGIN_ROOT': str(plugin),
           'CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE': override}
    return subprocess.run(['/bin/sh', '-c', command], env=env, input='synthetic stdin é',
                          text=True, encoding='utf-8', capture_output=True, timeout=15)


def test_unusable_first_interpreter_falls_back_without_consuming_stdin_or_retrying_hook(tmp_path):
    result = invoke(tmp_path, {'python3': False, 'python': True})
    assert result.returncode == 0 and not result.stderr
    assert result.stdout == 'synthetic stdin é'


def test_saved_override_works_without_python_on_path(tmp_path):
    result = invoke(tmp_path, {}, sys.executable)
    assert result.returncode == 0 and not result.stderr
    assert result.stdout == 'synthetic stdin é'


@pytest.mark.parametrize('candidates,override', [({}, ''), ({'python3': True}, 'absent-explicit-python')])
def test_missing_or_invalid_override_is_advisory_without_silent_fallback(tmp_path, candidates, override):
    result = invoke(tmp_path, candidates, override)
    assert result.returncode == 0 and not result.stderr
    assert 'optional Python executable in /config' in json.loads(result.stdout)['systemMessage']
