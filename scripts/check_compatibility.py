#!/usr/bin/env python3
"""Validate current package bindings and explicit installed-host coverage gaps."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('llm-accuracy', 'deterministic-data', 'session-ledger', 'evidence-memory')
TARGETS = ('code-linux', 'code-wsl', 'code-windows-no-bash', 'code-windows-git-bash', 'code-macos',
           'desktop-chat-windows', 'desktop-chat-macos', 'cowork-windows', 'cowork-macos',
           'desktop-chat-linux', 'cowork-linux')
CHECKS = ('clean_install', 'configured_python', 'prompt_delivery', 'upgrade', 'uninstall',
          'invalid_python_advisory_then_recovery')
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
    return {'schema_version': 2, 'minimum_claude_code': '2.1.287',
            'python_minimum': '3.9', 'packages': {name: package_binding(root, name) for name in PACKAGES},
            'targets': {target: {'outcome': 'untested'} for target in TARGETS},
            'capabilities': {'code': 'configured_exec_hooks', 'desktop_chat': 'skills_only',
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


def validate(root: Path, receipt: dict, *, release: bool = False) -> list[str]:
    errors = marketplace_errors(root)
    if not isinstance(receipt, dict):
        return ['invalid_compatibility_receipt']
    expected = candidate(root)
    for key in ('schema_version', 'minimum_claude_code', 'python_minimum', 'packages', 'capabilities'):
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
            if (row.get('platform'), row.get('host_kind')) != target_identity(target):
                errors.append('invalid_host_identity_' + target)
            version = row.get('host_version', '')
            checks = row.get('checks', {})
            if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
                errors.append('missing_host_version_' + target)
            elif tuple(map(int, version.split('.'))) < (2, 1, 287) and target.startswith('code-'):
                errors.append('unsupported_host_version_' + target)
            python = row.get('python_version', '')
            if target.startswith('code-') and (not isinstance(python, str)
                    or not re.fullmatch(r'\d+\.\d+\.\d+', python)
                    or tuple(map(int, python.split('.'))) < (3, 9, 0)):
                errors.append('missing_or_unsupported_python_version_' + target)
            if row.get('packages') != target_packages(expected['packages'], target):
                errors.append('stale_target_packages_' + target)
            if not isinstance(checks, dict) or set(checks) != set(target_checks(target)) or any(v is not True for v in checks.values()):
                errors.append('missing_checks_' + target)
    if release:
        for target in TARGETS:
            if not isinstance(targets[target], dict) or targets[target].get('outcome') != 'pass':
                errors.append('clean_installed_smoke_required_' + target)
    for name in ('llm-accuracy', 'session-ledger', 'evidence-memory'):
        directory = root / 'plugins' / name
        option = json.loads((directory / '.claude-plugin/plugin.json').read_text())['userConfig']['python_executable']
        if option.get('required') is not True or 'default' in option:
            errors.append('explicit_python_configuration_required_' + name)
        hooks = json.loads((directory / 'hooks/hooks.json').read_text())['hooks']
        for groups in hooks.values():
            for group in groups:
                for hook in group['hooks']:
                    if hook.get('command') != '${user_config.python_executable}' or not isinstance(hook.get('args'), list):
                        errors.append('shell_launcher_' + name)
        if (directory / 'hooks/hook_runner.py').read_bytes() != (root / 'plugins/llm-accuracy/hooks/hook_runner.py').read_bytes():
            errors.append('runner_drift_' + name)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--release', action='store_true')
    parser.add_argument('--write-candidate', action='store_true', help='Reset every installed-host result to untested')
    args = parser.parse_args()
    path = args.root / 'docs/validation/compatibility-candidate.json'
    if args.write_candidate:
        path.write_text(json.dumps(candidate(args.root), indent=2) + '\n')
        return 0
    try:
        receipt = json.loads(path.read_text())
        errors = validate(args.root, receipt, release=args.release)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        errors = ['invalid_compatibility_receipt']
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
