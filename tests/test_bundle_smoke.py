"""Bundle QA must reject false proof and keep host content out of reports."""
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('bundle_smoke', ROOT / 'scripts/claude_bundle_smoke.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


def test_windows_run_records_the_git_bash_state_it_proved(monkeypatch):
    monkeypatch.setattr(bundle.smoke, 'platform_label', lambda: 'Linux/WSL')
    assert bundle.windows_bash_state() == 'not_tested'
    monkeypatch.setattr(bundle.smoke, 'platform_label', lambda: 'Windows')
    monkeypatch.delenv('CLAUDE_CODE_GIT_BASH_PATH', raising=False)
    monkeypatch.setattr(bundle, 'usable_bash', lambda path: bool(path))
    assert bundle.windows_bash_state() == 'present'
    monkeypatch.setattr(bundle, 'usable_bash', lambda path: False)
    assert bundle.windows_bash_state() == 'absent'
    monkeypatch.setenv('CLAUDE_CODE_GIT_BASH_PATH', 'C:/synthetic/missing/bash.exe')
    assert bundle.windows_bash_state() == 'unclear'


def test_windows_probe_checks_path_override_and_git_install_folders(monkeypatch):
    monkeypatch.setattr(bundle.smoke, 'platform_label', lambda: 'Windows')
    monkeypatch.setenv('CLAUDE_CODE_GIT_BASH_PATH', 'C:/override/bash.exe')
    found = {'git': 'D:/Tools/Git/cmd/git.exe', 'bash': 'E:/bin/bash.exe'}
    monkeypatch.setattr(bundle.shutil, 'which', found.get)
    probed = []
    monkeypatch.setattr(bundle, 'usable_bash', lambda path: probed.append(str(path)) or False)
    assert bundle.windows_bash_state() == 'unclear'
    roots = ('C:/Program Files/Git', 'C:/Program Files (x86)/Git', 'D:/Tools/Git')
    expected = {'E:/bin/bash.exe', 'C:/override/bash.exe'} | {
        str(Path(root) / suffix) for root in roots for suffix in ('bin/bash.exe', 'usr/bin/bash.exe')}
    assert set(probed) == expected
    for source in expected:  # Each source alone proves Bash present.
        monkeypatch.setattr(bundle, 'usable_bash', lambda path, source=source: str(path) == source)
        assert bundle.windows_bash_state() == 'present', source


@pytest.mark.parametrize(('stdout', 'code', 'usable'), [
    (b'GNU bash, version 5.2.37(1)-release', 0, True),
    (b'zsh 5.9 (x86_64-pc-msys)', 0, False),
    (b'GNU bash, version 5.2.37(1)-release', 1, False),
])
def test_usable_bash_needs_a_gnu_bash_version(monkeypatch, stdout, code, usable):
    def version(command, **kwargs):
        return subprocess.CompletedProcess(command, code, stdout=stdout, stderr=b'')
    monkeypatch.setattr(bundle.subprocess, 'run', version)
    assert bundle.usable_bash('D:/Tools/Git/bin/bash.exe') is usable


@pytest.mark.parametrize('state', ['present', 'absent', 'unclear'])
def test_smoke_report_carries_the_probed_windows_bash_state(monkeypatch, state):
    def git(command, **kwargs):
        return subprocess.CompletedProcess(command, 1 if 'diff' in command else 0, stdout=b'', stderr=b'')
    monkeypatch.setattr(bundle, 'require_committed_source', lambda: 'a' * 40)
    monkeypatch.setattr(bundle, 'changed_paths', lambda root, baseline: [])
    monkeypatch.setattr(bundle.subprocess, 'run', git)
    monkeypatch.setattr(bundle.smoke, 'platform_label', lambda: 'Windows')
    monkeypatch.setattr(bundle, 'windows_bash_state', lambda: state)
    monkeypatch.setattr(bundle.smoke, 'host_version', lambda claude: '9.9.9 (Claude Code)')
    monkeypatch.setattr(bundle, 'package_binding', lambda root, name: {'version': '0.0.0', 'sha256': '0' * 64})
    monkeypatch.setattr(bundle.smoke, 'auth_profile', lambda root, **k: {'CLAUDE_CONFIG_DIR': str(root / 'p')})
    monkeypatch.setattr(bundle, 'lifecycle', lambda *a, **k: {'lifecycle': True})
    monkeypatch.setattr(bundle, 'installed_listing', lambda claude, env, root: [])
    monkeypatch.setattr(bundle.smoke, 'installed_entry', lambda listing, name: {})
    monkeypatch.setattr(bundle.smoke, 'path_inside', lambda path, root: True)
    monkeypatch.setattr(bundle.installed_hook_probe, 'run', lambda *a: True)
    monkeypatch.setattr(bundle, 'python_options', lambda profile: {})
    monkeypatch.setattr(bundle, 'action', lambda *a, **k: None)
    monkeypatch.setattr(bundle, 'bundle_removed', lambda listing: True)
    report = bundle.run_smoke('synthetic-host', 'synthetic-baseline', live=False)
    assert report['windows_bash'] == state
    assert report['status'] == 'partial'


def test_installed_byte_missing_and_extra_files_are_failures(tmp_path):
    source, profile = tmp_path / 'source', tmp_path / 'profile'
    entries = []
    for name in bundle.PACKAGES:
        origin, installed = source / 'plugins' / name, profile / name
        for directory in (origin, installed):
            (directory / '.claude-plugin').mkdir(parents=True)
            (directory / '.claude-plugin/plugin.json').write_text('{"version":"1.0.0"}')
            (directory / 'source.py').write_text('synthetic original')
        entries.append({'id': name + '@llm-accuracy', 'version': '1.0.0', 'installPath': str(installed)})
    listing = json.dumps(entries)
    assert bundle.installation_matches(listing, source, profile)
    changed = profile / bundle.PACKAGES[0] / 'source.py'
    changed.write_text('synthetic wrong byte')
    assert not bundle.installation_matches(listing, source, profile)
    changed.unlink()
    assert not bundle.installation_matches(listing, source, profile)
    changed.write_text('synthetic original')
    (changed.parent / 'extra.py').write_text('synthetic extra')
    assert not bundle.installation_matches(listing, source, profile)


def test_installation_path_must_be_inside_temporary_profile(tmp_path):
    listing = json.dumps([{'id': 'llm-accuracy@llm-accuracy', 'version': '1.0.0',
                           'installPath': str(ROOT / 'plugins/llm-accuracy')}])
    assert not bundle.installation_matches(listing, ROOT, tmp_path)


def test_missing_python_configuration_fails_without_reporting_contents(tmp_path):
    (tmp_path / 'settings.json').write_text('{"private":"SYNTHETIC_SENTINEL"}')
    options = bundle.python_options(tmp_path)
    assert all(value is None for value in options.values())
    assert 'SYNTHETIC_SENTINEL' not in json.dumps(options)


def test_one_remaining_bundle_registration_is_not_uninstalled():
    assert bundle.bundle_removed('[]')
    assert not bundle.bundle_removed('[{"id":"evidence-memory@llm-accuracy"}]')


@pytest.mark.parametrize('count', [0, 2])
def test_missing_or_duplicate_prompt_delivery_cannot_pass(count):
    report = {'status': 'ok', 'result_count': 1, 'fidelity_hook_responses': count,
              'host_inventory': {'accuracy_plugin_count': 1, 'tool_count': 0, 'mcp_count': 0}}
    assert not bundle.delivery_passed(report)
    report['fidelity_hook_responses'] = 1
    assert bundle.delivery_passed(report)


def test_live_prompt_with_tools_or_mcps_cannot_pass():
    report = {'status': 'ok', 'result_count': 1, 'fidelity_hook_responses': 1,
              'host_inventory': {'accuracy_plugin_count': 1, 'tool_count': 1, 'mcp_count': 0}}
    assert not bundle.delivery_passed(report)
    report['host_inventory'].update(tool_count=0, mcp_count=1)
    assert not bundle.delivery_passed(report)


def test_partial_installation_smoke_is_not_success(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bundle, 'run_smoke', lambda *a, **k: {'status': 'partial', 'partial': True})
    assert bundle.main(['--baseline', 'synthetic', '--receipt', str(tmp_path / 'receipt.json'), '--skip-live']) == 2
    assert json.loads(capsys.readouterr().out)['partial'] is True


def test_host_failure_never_echoes_raw_sensitive_content(tmp_path, monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise ValueError('SYNTHETIC_SENTINEL settings stdout stderr answer')
    monkeypatch.setattr(bundle, 'run_smoke', fail)
    path = tmp_path / 'receipt.json'
    assert bundle.main(['--baseline', 'synthetic', '--receipt', str(path)]) == 1
    assert 'SYNTHETIC_SENTINEL' not in capsys.readouterr().out + path.read_text()


def test_bundle_source_rejects_dirty_and_untracked_package_bytes(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.run(['git', '-C', str(tmp_path), *args], capture_output=True, check=True)
    git('init', '-q')
    git('config', 'user.name', 'Synthetic QA')
    git('config', 'user.email', 'qa@example.invalid')
    for name in bundle.PACKAGES:
        folder = tmp_path / 'plugins' / name
        folder.mkdir(parents=True)
        (folder / 'source.py').write_text('synthetic original')
    git('add', '.')
    git('-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic fixture')
    monkeypatch.setattr(bundle, 'ROOT', tmp_path)
    monkeypatch.setattr(bundle.smoke, 'ROOT', tmp_path)
    assert bundle.require_committed_source() == git('rev-parse', 'HEAD').stdout.decode().strip()
    file = tmp_path / 'plugins/llm-accuracy/source.py'
    file.write_text('synthetic dirty')
    with pytest.raises(ValueError):
        bundle.require_committed_source()
    file.write_text('synthetic original')
    (file.parent / 'extra.py').write_text('synthetic untracked')
    with pytest.raises(ValueError, match='bundle_source_not_committed'):
        bundle.require_committed_source()


def test_missing_upgrade_baseline_fails_before_host_runs(monkeypatch):
    monkeypatch.setattr(bundle, 'require_committed_source', lambda: 'synthetic')
    monkeypatch.setattr(bundle.smoke, 'auth_profile', lambda *a: pytest.fail('host setup ran'))
    with pytest.raises(ValueError, match='publication_base_unavailable'):
        bundle.run_smoke('synthetic-host', 'synthetic-missing-baseline')
