#!/usr/bin/env python3
"""Isolated Code bundle registration and Accuracy delivery QA; never publish."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import claude_install_smoke as smoke  # noqa: E402
from check_compatibility import PACKAGES, ROOT, package_binding  # noqa: E402
from check_marketplace_publication import changed_paths  # noqa: E402
import installed_hook_probe  # noqa: E402


def action(claude, env, cwd, *arguments, value=None):
    result = smoke.run_cli([claude, 'plugin', *arguments], env, cwd, value)
    if result.returncode:
        raise ValueError('bundle_plugin_action_failed')
    return result.stdout


def require_committed_source():
    for name in PACKAGES:
        directory = ROOT / 'plugins' / name
        tracked = smoke.tracked_plugin_files(directory)
        actual = source_files(directory)
        if set(actual) != {path.relative_to(directory).as_posix() for path in tracked}:
            raise ValueError('bundle_source_not_committed')
    status = subprocess.run(['git', '-C', str(ROOT), 'status', '--porcelain',
                             '--untracked-files=all', '--', 'plugins', '.claude-plugin'],
                            capture_output=True, check=True, timeout=30)
    if status.stdout:
        raise ValueError('bundle_source_not_committed')
    return smoke.git_value('rev-parse', 'HEAD')


def source_files(directory):
    return {path.relative_to(directory).as_posix(): path for path in directory.rglob('*')
            if path.is_file() and '__pycache__' not in path.parts}


def installation_matches(listing, source, profile):
    for name in PACKAGES:
        entry = smoke.installed_entry(listing, name + '@llm-accuracy')
        installed = smoke.path_inside(entry.get('installPath'), profile)
        if installed is None or entry.get('version') != package_binding(source, name)['version']:
            return False
        expected, actual = source_files(source / 'plugins' / name), source_files(installed)
        if set(expected) != set(actual):
            return False
        for path in expected:
            if expected[path].read_bytes() != actual[path].read_bytes():
                return False
    return True


def python_options(profile):
    settings = json.loads((profile / 'settings.json').read_text(encoding='utf-8'))
    configs = settings.get('pluginConfigs', {})
    return {name: configs.get(name + '@llm-accuracy', {}).get('options', {}).get('python_executable')
            for name in PACKAGES if name != 'deterministic-data'}


def configure_bundle(claude, env, cwd):
    for name in PACKAGES:
        if name != 'deterministic-data':
            action(claude, env, cwd, 'configure', name + '@llm-accuracy', '--values-stdin',
                   value=json.dumps({'python_executable': sys.executable}))


def refresh_bundle(claude, env, cwd):
    action(claude, env, cwd, 'marketplace', 'update', 'llm-accuracy')
    for name in PACKAGES:
        action(claude, env, cwd, 'update', name + '@llm-accuracy')


def installed_listing(claude, env, cwd):
    return action(claude, env, cwd, 'list', '--json')


def bundle_removed(listing):
    entries = json.loads(listing)
    return isinstance(entries, list) and not any(
        isinstance(row, dict) and row.get('id') == name + '@llm-accuracy'
        for row in entries for name in PACKAGES)


def delivery_passed(result):
    inventory = result.get('host_inventory', {})
    return (result.get('status') == 'ok' and result.get('result_count') == 1
            and result.get('fidelity_hook_responses') == 1
            and inventory.get('accuracy_plugin_count') == 1
            and inventory.get('tool_count') == 0 and inventory.get('mcp_count') == 0)


def probe_installed(claude, root, env, options):
    profile = Path(env['CLAUDE_CONFIG_DIR'])
    listing = installed_listing(claude, env, root)
    installed = {name: smoke.path_inside(smoke.installed_entry(listing, name + '@llm-accuracy').get('installPath'),
                                         profile) for name in PACKAGES}
    return installed_hook_probe.run(installed, root, options, env)


def lifecycle(claude, root, source, env, *, live=False, timeout=60):
    profile = Path(env['CLAUDE_CONFIG_DIR'])
    action(claude, env, root, 'marketplace', 'add', str(source))
    for name in PACKAGES:
        action(claude, env, root, 'install', name + '@llm-accuracy')
    if not installation_matches(installed_listing(claude, env, root), source, profile):
        raise ValueError('bundle_baseline_install_mismatch')
    shutil.rmtree(source / 'plugins')
    shutil.copytree(ROOT / 'plugins', source / 'plugins',
                    ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / '.claude-plugin', source / '.claude-plugin', dirs_exist_ok=True)
    refresh_bundle(claude, env, root)
    unset = all(value is None for value in python_options(profile).values())
    automatic_upgrade = unset and probe_installed(claude, root, env, dict.fromkeys(python_options(profile), ''))
    unconfigured_delivery = False
    if live:
        command = smoke.session_command(claude, 'sonnet') + ['--setting-sources', 'user', '--effort', 'low']
        result = smoke.communicate(command, root, env,
                                   smoke.stream_input('Reply exactly OK. Do not use tools.'), timeout)
        unconfigured_delivery = unset and delivery_passed(result)
    configure_bundle(claude, env, root)
    upgrade = installation_matches(installed_listing(claude, env, root), ROOT, profile)
    before = python_options(profile)
    refresh_bundle(claude, env, root)
    preserved = before == python_options(profile) and all(v == sys.executable for v in before.values())
    for name in PACKAGES:
        action(claude, env, root, 'uninstall', name + '@llm-accuracy')
    if not bundle_removed(installed_listing(claude, env, root)):
        raise ValueError('bundle_upgrade_uninstall_failed')
    for name in PACKAGES:
        action(claude, env, root, 'install', name + '@llm-accuracy')
    fresh_unset = all(value is None for value in python_options(profile).values())
    automatic_fresh = fresh_unset and probe_installed(claude, root, env, dict.fromkeys(python_options(profile), ''))
    configure_bundle(claude, env, root)
    clean = installation_matches(installed_listing(claude, env, root), ROOT, profile)
    configured = all(v == sys.executable for v in python_options(profile).values())
    return {'clean_install': clean, 'configured_python': configured,
            'upgrade': upgrade and preserved, 'automatic_python_upgrade': automatic_upgrade,
            'automatic_python_fresh': automatic_fresh, 'unconfigured_prompt_delivery': unconfigured_delivery}


def usable_bash(path):
    if not path:
        return False
    # Windows' WSL launcher can print GNU Bash's version without being Git Bash.
    candidate = Path(path)
    if candidate.name.lower() == 'bash.exe' and candidate.parent.name.lower() in (
            'system32', 'sysnative', 'syswow64', 'windowsapps'):
        return False
    try:
        env = {key: value for key, value in os.environ.items() if key not in smoke.CONTROL_VARS}
        result = subprocess.run([str(path), '--version'], env=env, capture_output=True, timeout=15)
        return result.returncode == 0 and b'GNU bash' in result.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def windows_bash_state():
    """The Git Bash state this Windows run proved: present, absent or unclear."""
    if smoke.platform_label() != 'Windows':
        return 'not_tested'
    git = shutil.which('git')
    roots = [Path('C:/Program Files/Git'), Path('C:/Program Files (x86)/Git')]
    if git:
        roots.append(Path(git).parent.parent)
    paths = [shutil.which('bash'), os.environ.get('CLAUDE_CODE_GIT_BASH_PATH')]
    paths.extend(root / suffix for root in roots for suffix in ('bin/bash.exe', 'usr/bin/bash.exe'))
    if any(usable_bash(path) for path in paths):
        return 'present'
    # An override that points at no usable Bash proves neither Windows scenario.
    return 'unclear' if os.environ.get('CLAUDE_CODE_GIT_BASH_PATH') else 'absent'


def run_smoke(claude, baseline, *, live=True, timeout=60, ci_auth=False):
    commit = require_committed_source()
    changed_paths(ROOT, baseline)  # Prove a real, available ancestor; never fall back.
    if subprocess.run(['git', '-C', str(ROOT), 'diff', '--quiet', baseline, 'HEAD', '--', 'plugins'],
                      capture_output=True, timeout=30).returncode != 1:
        raise ValueError('bundle_upgrade_requires_different_baseline')
    report = {'scope': 'code_bundle_registration_accuracy_delivery', 'source_commit': commit,
              'platform': smoke.platform_label(), 'desktop_gui': 'not_tested',
              'windows_bash': windows_bash_state(), 'partial': not live,
              'host_version': smoke.host_version(claude).split()[0],
              'python_version': '.'.join(map(str, sys.version_info[:3])),
              'packages': {name: package_binding(ROOT, name) for name in PACKAGES}}
    with smoke._termination_cleanup(), tempfile.TemporaryDirectory(prefix='accuracy-bundle-') as directory:
        root = Path(directory)
        source = root / "market O'Brien é"
        source.mkdir()
        baseline_files = subprocess.run(['git', '-C', str(ROOT), 'ls-tree', '-r', '--name-only', baseline,
                                         '--', 'plugins', '.claude-plugin'],
                                        capture_output=True, check=True, timeout=30).stdout.decode('utf-8').splitlines()
        for name in baseline_files:
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(subprocess.run(['git', '-C', str(ROOT), 'show', baseline + ':' + name],
                                            capture_output=True, check=True, timeout=30).stdout)
        report['baseline_packages'] = {name: package_binding(source, name) for name in PACKAGES}
        env = smoke.auth_profile(root, ci=True, live=live) if ci_auth else smoke.auth_profile(root)
        checks = lifecycle(claude, root, source, env, live=live, timeout=timeout)
        listing = installed_listing(claude, env, root)
        installed = {name: smoke.path_inside(smoke.installed_entry(listing, name + '@llm-accuracy').get('installPath'),
                                             Path(env['CLAUDE_CONFIG_DIR'])) for name in PACKAGES}
        checks['installed_hook_execution'] = installed_hook_probe.run(
            installed, root, python_options(Path(env['CLAUDE_CONFIG_DIR'])), env)
        checks['prompt_delivery'] = False
        checks['invalid_python_advisory_then_recovery'] = False
        if live:
            command = smoke.session_command(claude, 'sonnet')
            command.extend(['--setting-sources', 'user', '--effort', 'low'])
            action(claude, env, root, 'configure', 'llm-accuracy@llm-accuracy', '--values-stdin',
                   value=json.dumps({'python_executable': str(root / 'absent-python-executable')}))
            unavailable = smoke.communicate(command, root, env,
                                            smoke.stream_input('Reply exactly OK. Do not use tools.'), timeout)
            advisory = (unavailable.get('status') == 'ok' and unavailable.get('result_count') == 1
                        and unavailable.get('fidelity_hook_responses') == 0)
            configure_bundle(claude, env, root)
            result = smoke.communicate(command, root, env,
                                       smoke.stream_input('Reply exactly OK. Do not use tools.'), timeout)
            checks['prompt_delivery'] = delivery_passed(result)
            report['invalid_python_advisory_then_recovery'] = advisory and checks['prompt_delivery']
            checks['invalid_python_advisory_then_recovery'] = report['invalid_python_advisory_then_recovery']
        for name in PACKAGES:
            action(claude, env, root, 'uninstall', name + '@llm-accuracy')
        checks['uninstall'] = bundle_removed(installed_listing(claude, env, root))
        report['checks'] = checks
    report['isolated_cleanup'] = not root.exists()
    passed = all(checks.values()) and report['isolated_cleanup'] and report.get('invalid_python_advisory_then_recovery') is True
    report['status'] = 'pass' if passed else 'partial' if not live else 'fail'
    return report


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude', default='claude')
    parser.add_argument('--baseline', required=True, help='Available ancestor with previous package bytes.')
    parser.add_argument('--receipt', required=True, type=Path)
    parser.add_argument('--skip-live', action='store_true')
    options = parser.parse_args(arguments)
    try:
        report = run_smoke(options.claude, options.baseline, live=not options.skip_live)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        report = {'status': 'fail', 'error': 'bundle_smoke_failed', 'partial': options.skip_live}
    try:
        options.receipt.parent.mkdir(parents=True, exist_ok=True)
        options.receipt.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    except OSError:
        report = {'status': 'fail', 'error': 'bundle_receipt_write_failed'}
    print(json.dumps(report))
    return 0 if report['status'] == 'pass' else 2 if report['status'] == 'partial' else 1


if __name__ == '__main__':
    raise SystemExit(main())
