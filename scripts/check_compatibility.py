#!/usr/bin/env python3
"""Validate current package bindings and explicit installed-host coverage gaps."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('llm-accuracy', 'deterministic-data', 'session-ledger', 'evidence-memory')
TARGETS = ('code-linux', 'code-wsl', 'code-windows-no-bash', 'code-windows-git-bash', 'code-macos',
           'desktop-chat-windows', 'desktop-chat-macos', 'cowork-windows', 'cowork-macos',
           'desktop-chat-linux', 'cowork-linux')
CODE_TARGETS = TARGETS[:5]
CI_TARGETS = tuple(target for target in CODE_TARGETS if target != 'code-wsl')
SUPPORT_POLICY = {'code': 'native_installation_and_local_live_qa',
                  'desktop_chat': 'experimental_stateless_skills',
                  'cowork': 'experimental_stateless_skills'}
LAUNCHER_COMMAND = (r'set -- "([a-z][a-z_-]*\.py(?::[a-z-]+)?)"; '
                    r'\(\. "\$\{CLAUDE_PLUGIN_ROOT\}/hooks/python-launcher\.cmd" "\1"\); exit 0')
CHECKS = ('clean_install', 'configured_python', 'automatic_python_upgrade', 'automatic_python_fresh',
          'unconfigured_prompt_delivery', 'prompt_delivery', 'upgrade', 'uninstall',
          'invalid_python_advisory_then_recovery')
INSTALL_CHECKS = ('clean_install', 'configured_python', 'automatic_python_upgrade', 'automatic_python_fresh',
                 'upgrade', 'uninstall', 'installed_hook_execution')
CHAT_CHECKS = ('clean_install', 'skills_available', 'skill_invocation', 'no_local_hooks', 'upgrade', 'uninstall')
COWORK_CHECKS = ('clean_install', 'skills_available', 'skill_invocation', 'stateless_boundary', 'upgrade', 'uninstall')


def target_checks(target: str) -> tuple:
    if target.startswith('desktop-chat-'):
        return CHAT_CHECKS
    if target.startswith('cowork-'):
        return COWORK_CHECKS
    if target == 'code-windows-no-bash':
        return CHECKS + ('git_bash_absent',)
    if target == 'code-windows-git-bash':
        return CHECKS + ('git_bash_present',)
    return CHECKS


def target_packages(packages: dict, target: str) -> dict:
    names = PACKAGES if target.startswith('code-') else PACKAGES[:2]
    return {name: packages[name] for name in names}


def installation_checks(target: str) -> tuple:
    return INSTALL_CHECKS + tuple(check for check in target_checks(target) if check.startswith('git_bash_'))


def target_identity(target: str) -> tuple[str, str]:
    if target not in TARGETS:
        raise ValueError('unknown_compatibility_target')
    platform = 'Windows' if 'windows' in target else 'Darwin' if 'macos' in target else 'Linux/WSL' if target == 'code-wsl' else 'Linux'
    kind = 'code' if target.startswith('code-') else 'desktop_chat' if target.startswith('desktop-chat-') else 'cowork'
    return platform, kind


def package_binding(root: Path, name: str) -> dict:
    directory = root / 'plugins' / name
    digest = hashlib.sha256()
    for path in sorted(directory.rglob('*'), key=lambda item: item.relative_to(directory).as_posix()):
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(path.relative_to(directory).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    manifest = json.loads((directory / '.claude-plugin/plugin.json').read_text())
    return {'version': manifest['version'], 'sha256': digest.hexdigest()}


def candidate(root: Path) -> dict:
    return {'schema_version': 4, 'minimum_claude_code': '2.1.287',
            'python_minimum': '3.9', 'packages': {name: package_binding(root, name) for name in PACKAGES},
            'support_policy': SUPPORT_POLICY.copy(),
            'targets': {target: {'outcome': 'untested'} for target in TARGETS},
            'native_installations': {target: {'outcome': 'untested'} for target in CI_TARGETS},
            'capabilities': {'code': 'automatic_python_hooks', 'desktop_chat': 'skills_only',
                             'cowork': 'stateless_skills_only_unverified_hooks',
                             'desktop_code': 'unverified_ui', 'codex_memory': 'experimental_posix_only'}}


def marketplace_errors(root: Path) -> list[str]:
    errors = []
    claude = json.loads((root / '.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
    entries = claude.get('plugins') if isinstance(claude, dict) else None
    if (not isinstance(entries, list) or len(entries) != len(PACKAGES)
            or claude.get('name') != 'llm-accuracy'
            or set(claude) - {'$schema', 'name', 'description', 'owner', 'plugins'}
            or any(not isinstance(row, dict) or set(row) - {'name', 'source', 'description', 'category'}
                   or row.get('name') not in PACKAGES
                   or row.get('source') != './plugins/' + row.get('name', '') for row in entries)
            or {row.get('name') for row in entries} != set(PACKAGES)):
        errors.append('invalid_claude_marketplace_routes')
    codex = json.loads((root / '.agents/plugins/marketplace.json').read_text(encoding='utf-8'))
    entries = codex.get('plugins') if isinstance(codex, dict) else None
    if (not isinstance(entries, list) or len(entries) != 1 or not isinstance(entries[0], dict)
            or codex.get('name') != 'llm-accuracy' or set(codex) - {'name', 'interface', 'plugins'}
            or set(entries[0]) - {'name', 'source', 'policy', 'category', 'description'}
            or entries[0].get('name') != 'evidence-memory'
            or entries[0].get('source') != {'source': 'local', 'path': './plugins/evidence-memory'}
            or entries[0].get('policy') != {'installation': 'AVAILABLE', 'authentication': 'ON_USE'}):
        errors.append('invalid_codex_marketplace_routes')
    for name in PACKAGES:
        manifest = json.loads((root / 'plugins' / name / '.claude-plugin/plugin.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('name') != name:
            errors.append('invalid_package_identity_' + name)
    return errors


def host_row_errors(row: dict, target: str, packages: dict, checks: tuple) -> list[str]:
    errors = []
    if (row.get('platform'), row.get('host_kind')) != target_identity(target):
        errors.append('invalid_host_identity_' + target)
    version = row.get('host_version', '')
    if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        errors.append('missing_host_version_' + target)
    elif tuple(map(int, version.split('.'))) < (2, 1, 287) and target.startswith('code-'):
        errors.append('unsupported_host_version_' + target)
    python = row.get('python_version', '')
    if target.startswith('code-') and (not isinstance(python, str)
            or not re.fullmatch(r'\d+\.\d+\.\d+', python)
            or tuple(map(int, python.split('.'))) < (3, 9, 0)):
        errors.append('missing_or_unsupported_python_version_' + target)
    if row.get('packages') != target_packages(packages, target):
        errors.append('stale_target_packages_' + target)
    actual = row.get('checks', {})
    if not isinstance(actual, dict) or set(actual) != set(checks) or any(v is not True for v in actual.values()):
        errors.append('missing_checks_' + target)
    return errors


def installation_errors(row: dict, target: str, packages: dict) -> list[str]:
    fields = {'outcome', 'platform', 'host_kind', 'host_version', 'python_version',
              'packages', 'checks', 'live_delivery', 'isolated_cleanup'}
    if (not isinstance(row, dict) or set(row) != fields or row.get('outcome') != 'installed'
            or row.get('live_delivery') != 'not_tested' or row.get('isolated_cleanup') is not True):
        return ['invalid_installation_scope_' + target]
    return host_row_errors(row, target, packages, installation_checks(target))


def validate(root: Path, receipt: dict, *, release: bool = False) -> list[str]:
    errors = marketplace_errors(root)
    if not isinstance(receipt, dict):
        return ['invalid_compatibility_receipt']
    expected = candidate(root)
    for key in ('schema_version', 'minimum_claude_code', 'python_minimum', 'packages', 'capabilities', 'support_policy'):
        if receipt.get(key) != expected[key]:
            errors.append('invalid_or_stale_' + key)
    targets = receipt.get('targets', {})
    if not isinstance(targets, dict) or set(targets) != set(TARGETS):
        return errors + ['missing_or_unknown_target']
    for target, row in targets.items():
        if not isinstance(row, dict) or row.get('outcome') not in ('pass', 'untested'):
            errors.append('invalid_outcome_' + target)
            continue
        if row['outcome'] == 'pass':
            errors.extend(host_row_errors(row, target, expected['packages'], target_checks(target)))
    installations = receipt.get('native_installations')
    if not isinstance(installations, dict) or set(installations) != set(CI_TARGETS):
        return errors + ['missing_or_unknown_native_installation']
    for target, row in installations.items():
        if row != {'outcome': 'untested'}:
            errors.extend(installation_errors(row, target, expected['packages']))
        if release and (not isinstance(row, dict) or row.get('outcome') != 'installed'):
            errors.append('native_installation_required_' + target)
    if release:
        if not any(isinstance(targets[target], dict) and targets[target].get('outcome') == 'pass'
                   for target in CODE_TARGETS):
            errors.append('local_live_code_smoke_required')
    for name in ('llm-accuracy', 'session-ledger', 'evidence-memory'):
        directory = root / 'plugins' / name
        option = json.loads((directory / '.claude-plugin/plugin.json').read_text())['userConfig']['python_executable']
        if option.get('type') != 'string' or option.get('required') is not False or 'default' in option:
            errors.append('python_override_optional_' + name)
        hooks = json.loads((directory / 'hooks/hooks.json').read_text())['hooks']
        for groups in hooks.values():
            for group in groups:
                for hook in group['hooks']:
                    command = hook.get('command')
                    match = re.fullmatch(LAUNCHER_COMMAND, command) if isinstance(command, str) else None
                    if not match or 'args' in hook:
                        errors.append('automatic_launcher_required_' + name)
                    elif not (directory / 'hooks' / match.group(1).partition(':')[0]).is_file():
                        errors.append('missing_hook_target_' + name)
        for filename in ('hook_runner.py', 'python-launcher.cmd'):
            if (directory / 'hooks' / filename).read_bytes() != (root / 'plugins/llm-accuracy/hooks' / filename).read_bytes():
                errors.append('runner_drift_' + name)
    return errors


def overlay_ci_receipts(root: Path, receipt: dict, directory: Path) -> dict:
    """Accept only this checkout's complete native CI receipts; never persist them."""
    commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    expected = {target + '.json' for target in CI_TARGETS}
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise ValueError('ci_run_identity_unavailable')
    if {path.name for path in directory.iterdir()} != expected:
        raise ValueError('ci_receipts_missing_or_unknown')
    result = json.loads(json.dumps(receipt))
    for target in CI_TARGETS:
        report = json.loads((directory / (target + '.json')).read_text(encoding='utf-8'))
        if (not isinstance(report, dict) or set(report) != {'schema_version', 'target', 'source_commit', 'run_id', 'row'}
                or report['schema_version'] != 2 or report['target'] != target or report['run_id'] != run_id
                or report['source_commit'] != commit or not isinstance(report['row'], dict)
                or report['row'].get('outcome') != 'installed'):
            raise ValueError('ci_receipt_invalid_or_stale')
        result['native_installations'][target] = report['row']
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--ci-receipts', type=Path, help='Current-run native evidence; never changes committed receipts')
    parser.add_argument('--write-candidate', action='store_true', help='Reset every installed-host result to untested')
    args = parser.parse_args()
    path = args.root / 'docs/validation/compatibility-candidate.json'
    if args.write_candidate:
        path.write_text(json.dumps(candidate(args.root), indent=2) + '\n')
        return 0
    try:
        receipt = json.loads(path.read_text())
        if args.ci_receipts is not None:
            receipt = overlay_ci_receipts(args.root, receipt, args.ci_receipts)
        errors = validate(args.root, receipt, release=args.release)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError):
        errors = ['invalid_compatibility_receipt']
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
