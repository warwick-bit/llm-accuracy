#!/usr/bin/env python3
"""Require installed-host evidence before marketplace bytes reach main."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_compatibility import ROOT, overlay_ci_receipts, validate  # noqa: E402


def exempt_path(path: str, *, symlink: bool = False) -> bool:
    """Exempt only ordinary review docs and Python tests outside packages."""
    if symlink:
        return False
    return (path in ('README.md', 'CONTRIBUTING.md')
            or (path.startswith('docs/') and path.endswith('.md'))
            or (path.startswith('tests/') and path.endswith('.py')))


def changed_paths(root: Path, base: str) -> list:
    """Read both sides of renames/deletions; never guess an unavailable base."""
    if not base or not base.strip() or set(base) == {'0'}:
        raise ValueError('publication_base_unavailable')
    resolved = subprocess.run(
        ['git', '-C', str(root), 'rev-parse', '--verify', '--end-of-options', base + '^{commit}'],
        capture_output=True, timeout=30, check=False)
    commit = resolved.stdout.decode('ascii').strip()
    if resolved.returncode or not re.fullmatch(r'[0-9a-f]{40,64}', commit):
        raise ValueError('publication_base_unavailable')
    ancestor = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', commit, 'HEAD'],
                              capture_output=True, timeout=30, check=False)
    if ancestor.returncode:
        raise ValueError('publication_base_not_ancestor')
    result = subprocess.run(['git', '-C', str(root), 'diff', '--raw', '--no-renames', '-z', commit, 'HEAD'],
                            capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError('publication_diff_unavailable')
    fields = result.stdout.split(b'\0')
    if fields[-1] != b'' or len(fields) % 2 != 1:
        raise ValueError('publication_diff_unreadable')
    rows = []
    for header, name in zip(fields[0:-1:2], fields[1:-1:2]):
        modes = header.split()[:2]
        if len(modes) != 2:
            raise ValueError('publication_diff_unreadable')
        rows.append((name.decode('utf-8'), b'120000' in (modes[0].lstrip(b':'), modes[1])))
    return rows


def publication_errors(root: Path, *, base: str | None = None, release: bool = False,
                       ci_receipts: Path | None = None) -> list:
    """Validate all host contracts whenever the diff could affect publication."""
    if not release:
        paths = changed_paths(root, base or '')
        if all(exempt_path(name, symlink=symlink) for name, symlink in paths):
            return []
    receipt = json.loads((root / 'docs/validation/compatibility-candidate.json').read_text(encoding='utf-8'))
    if ci_receipts is not None:
        receipt = overlay_ci_receipts(root, receipt, ci_receipts)
    return validate(root, receipt, release=True)


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--ci-receipts', type=Path, help='Native installed QA from this CI run only')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--base-ref', help='Exact PR base commit; must be available and an ancestor.')
    mode.add_argument('--release', action='store_true', help='Always enforce publication QA on main/tags.')
    options = parser.parse_args(arguments)
    try:
        errors = publication_errors(options.root, base=options.base_ref, release=options.release,
                                    ci_receipts=options.ci_receipts)
    except ValueError as error:
        label = str(error)
        errors = [label if label.startswith('publication_') else 'invalid_publication_evidence']
    except (OSError, KeyError, TypeError, AttributeError, UnicodeError, subprocess.SubprocessError):
        errors = ['publication_evidence_unavailable']
    print(json.dumps({'status': 'fail' if errors else 'pass', 'errors': errors}))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
