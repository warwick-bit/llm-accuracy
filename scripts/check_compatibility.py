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
TARGETS = ('code-linux', 'code-wsl', 'code-windows', 'code-macos',
           'desktop-chat-windows', 'desktop-chat-macos', 'cowork-windows', 'cowork-macos')
CHECKS = ('clean_install', 'configured_python', 'prompt_delivery', 'upgrade', 'uninstall')


def package_binding(root: Path, name: str) -> dict:
    directory = root / 'plugins' / name
    digest = hashlib.sha256()
    for path in sorted(directory.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            digest.update(path.relative_to(directory).as_posix().encode() + b'\0' + path.read_bytes() + b'\0')
    manifest = json.loads((directory / '.claude-plugin/plugin.json').read_text())
    return {'version': manifest['version'], 'sha256': digest.hexdigest()}


def candidate(root: Path) -> dict:
    return {'schema_version': 1, 'minimum_claude_code': '2.1.287',
            'python_minimum': '3.9', 'packages': {name: package_binding(root, name) for name in PACKAGES},
            'targets': {target: {'outcome': 'untested'} for target in TARGETS},
            'capabilities': {'code': 'configured_exec_hooks', 'desktop_chat': 'skills_only',
                             'cowork': 'stateless_plugins_only', 'codex_memory': 'experimental_posix_only'}}


def validate(root: Path, receipt: dict, *, release: bool = False) -> list[str]:
    errors = []
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
            version = row.get('host_version', '')
            checks = row.get('checks', {})
            if not isinstance(version, str) or not re.fullmatch(r'\d+\.\d+\.\d+', version):
                errors.append('missing_host_version_' + target)
            if not isinstance(checks, dict) or set(checks) != set(CHECKS) or any(v is not True for v in checks.values()):
                errors.append('missing_checks_' + target)
    if release and not any(targets[t].get('outcome') == 'pass' for t in TARGETS[:4]):
        errors.append('clean_installed_claude_code_smoke_required')
    for name in ('llm-accuracy', 'session-ledger', 'evidence-memory'):
        directory = root / 'plugins' / name
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
    except (OSError, ValueError, KeyError, TypeError):
        errors = ['invalid_compatibility_receipt']
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
