"""Exercise shipped Claude argument vectors with no shell."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import HOOK_SHELL, hook_argv

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ('llm-accuracy', 'session-ledger', 'evidence-memory')


def test_native_windows_gate_has_no_shell_dependency():
    if os.environ.get('REQUIRE_NATIVE_WINDOWS') == '1':
        assert os.name == 'nt'
        assert HOOK_SHELL == ''


def handlers():
    for name in PLUGINS:
        config = json.loads((ROOT / 'plugins' / name / 'hooks/hooks.json').read_text())['hooks']
        for event, groups in config.items():
            for i, group in enumerate(groups):
                for handler in group['hooks']:
                    yield pytest.param(name, handler, id=f'{name}-{event}-{i}')


@pytest.mark.parametrize('name,handler', list(handlers()))
@pytest.mark.parametrize('code', [0, 2, 7])
def test_exec_paths_argv_stdin_and_no_duplicate_execution(tmp_path, name, handler, code):
    root = tmp_path / "plugin O'Brien é $ literal"
    hooks = root / 'hooks'
    hooks.mkdir(parents=True)
    shutil.copyfile(ROOT / 'plugins' / name / 'hooks/hook_runner.py', hooks / 'hook_runner.py')
    target = handler['args'][3]
    (hooks / target).write_text('import json,sys\nprint(json.dumps({"args":sys.argv[1:],"stdin":sys.stdin.read()}))\n'
                               f'sys.exit({code})\n')
    data = tmp_path / "data O'Brien é $ literal"
    argv = hook_argv(handler, root, data)
    result = subprocess.run(argv, input='synthetic stdin é', capture_output=True, text=True,
                            encoding='utf-8', timeout=5, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    assert result.returncode == (1 if code == 2 else code)
    assert result.stderr == ''
    observed = json.loads(result.stdout)
    assert observed['stdin'] == 'synthetic stdin é'
    assert observed['args'] == argv[5:]


def doctor_module():
    directory = ROOT / 'plugins/llm-accuracy/scripts'
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location('exec_doctor', directory / 'accuracy_doctor.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_doctor_rejects_missing_and_unusable_executables(tmp_path):
    doctor = doctor_module()
    assert doctor.python_status(str(tmp_path / 'missing python')) == {'status': 'unusable'}
    assert doctor.python_status(sys.executable)['status'] == 'ok'
    assert doctor.python_status(sys.executable + ' --version') == {'status': 'unusable'}


@pytest.mark.parametrize('output,code,status', [('store alias', 1, 'unusable'), ('[3, 8, 20]', 0, 'unsupported_version')])
def test_doctor_diagnoses_store_alias_and_old_version(monkeypatch, output, code, status):
    doctor = doctor_module()
    monkeypatch.setattr(doctor.subprocess, 'run', lambda *a, **kw: subprocess.CompletedProcess([], code, output, ''))
    assert doctor.python_status('synthetic python')['status'] == status


def test_windows_memory_prefix_quotes_literals():
    spec = importlib.util.spec_from_file_location('prefix_memory', ROOT / 'plugins/evidence-memory/hooks/memory.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.shell_prefix(("C:/Python O'Brien/python.exe", '$literal'), windows=True) == "& 'C:/Python O''Brien/python.exe' '$literal'"


@pytest.mark.parametrize('quote', ["'", '\u2018', '\u2019', '\u201a', '\u201b'])
def test_memory_prefix_round_trips_through_its_named_shell(tmp_path, quote):
    shell = shutil.which('pwsh') if os.name == 'nt' else HOOK_SHELL
    if not shell:
        pytest.skip('named shell unavailable; direct argv remains the execution contract')
    spec = importlib.util.spec_from_file_location('roundtrip_memory', ROOT / 'plugins/evidence-memory/hooks/memory.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "script O'Brien é $ literal.py"
    target.write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    arguments = [sys.executable, str(target), f"value O{quote}Brien é $ literal"]
    command = module.shell_prefix(arguments, windows=os.name == 'nt')
    shell_args = [shell, '-NoProfile', '-NonInteractive', '-Command', command] if os.name == 'nt' else [shell, '-c', command]
    result = subprocess.run(shell_args, capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0 and result.stderr == ''
    assert json.loads(result.stdout) == arguments[2:]
