"""Real Git diffs must not hide changes from the pre-merge publication gate."""
import importlib.util
import json
import subprocess
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('publication_guard', ROOT / 'scripts/check_marketplace_publication.py')
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


def git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), *arguments], capture_output=True,
                          text=True, check=True).stdout.strip()


def commit(root, path, text='synthetic'):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')
    git(root, 'add', '--', path)
    git(root, '-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic fixture')
    return git(root, 'rev-parse', 'HEAD')


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, 'init', '-q')
    git(tmp_path, 'config', 'user.name', 'Synthetic QA')
    git(tmp_path, 'config', 'user.email', 'qa@example.invalid')
    base = commit(tmp_path, 'README.md')
    return tmp_path, base


@pytest.mark.parametrize('name', [
    'plugins/llm-accuracy/README.md', 'plugins/llm-accuracy/hooks/hooks.json',
    '.claude-plugin/marketplace.json', '.agents/plugins/marketplace.json',
    'scripts/check_compatibility.py', 'scripts/check_marketplace_publication.py',
    '.github/workflows/release-gates.yml', 'docs/validation/compatibility-candidate.json',
    'tests/fixture.json', 'nested/README.md', 'docs/guide.MD', 'unknown/input.txt',
])
def test_protected_and_unknown_changes_require_release_qa(repository, monkeypatch, name):
    root, base = repository
    commit(root, name, 'changed synthetic')
    receipt = root / 'docs/validation/compatibility-candidate.json'
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text('{}', encoding='utf-8')
    calls = []
    def validate(root_arg, evidence, *, release):
        calls.append((root_arg, evidence, release))
        return ['missing_installed_qa']
    monkeypatch.setattr(guard, 'validate', validate)
    assert guard.publication_errors(root, base=base) == ['missing_installed_qa']
    assert calls == [(root, {}, True)]


@pytest.mark.parametrize('name', ['README.md', 'CONTRIBUTING.md', 'docs/nested/guide.md',
                                  'tests/test_guard.py', 'docs/space and\nnewline.md'])
def test_narrow_docs_and_tests_exemption_uses_real_diff(repository, monkeypatch, name):
    root, base = repository
    commit(root, name, 'changed synthetic')
    monkeypatch.setattr(guard, 'validate', lambda *a, **k: pytest.fail('release validator ran'))
    assert guard.publication_errors(root, base=base) == []


@pytest.mark.parametrize('base', ['', ' ', '0' * 40, 'does-not-exist', '--all', 'f' * 40])
def test_missing_base_cannot_skip_qa(repository, base):
    root, _ = repository
    with pytest.raises(ValueError, match='publication_base_unavailable'):
        guard.changed_paths(root, base)


def test_non_ancestor_base_fails_closed(repository):
    root, base = repository
    later = commit(root, 'docs/later.md')
    git(root, 'checkout', '--detach', base)
    with pytest.raises(ValueError, match='publication_base_not_ancestor'):
        guard.changed_paths(root, later)


def test_deleted_or_renamed_package_remains_protected(repository):
    root, _ = repository
    base = commit(root, 'plugins/example/source.py')
    git(root, 'rm', 'plugins/example/source.py')
    commit(root, 'docs/moved.md')
    rows = guard.changed_paths(root, base)
    assert ('plugins/example/source.py', False) in rows
    assert any(not guard.exempt_path(name, symlink=link) for name, link in rows)


def test_symlink_does_not_inherit_docs_exemption(repository):
    root, base = repository
    (root / 'docs').mkdir()
    (root / 'docs/guide.md').symlink_to('../README.md')
    git(root, 'add', 'docs/guide.md')
    git(root, '-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic symlink')
    assert guard.changed_paths(root, base) == [('docs/guide.md', True)]
    assert guard.exempt_path('docs/guide.md', symlink=True) is False


def test_main_and_tags_always_require_release_qa(repository, monkeypatch):
    root, _ = repository
    receipt = root / 'docs/validation/compatibility-candidate.json'
    receipt.parent.mkdir(parents=True)
    receipt.write_text('{}', encoding='utf-8')
    calls = []
    monkeypatch.setattr(guard, 'validate', lambda r, e, *, release: calls.append(release) or ['qa_required'])
    assert guard.publication_errors(root, release=True) == ['qa_required']
    assert calls == [True]


def test_invalid_base_cli_emits_fixed_failure(repository, capsys):
    root, _ = repository
    assert guard.main(['--root', str(root), '--base-ref', '/private/path/needle']) == 1
    report = json.loads(capsys.readouterr().out)
    assert report == {'status': 'fail', 'errors': ['publication_base_unavailable']}


def test_missing_ci_artifacts_emit_fixed_diagnostic(tmp_path, capsys):
    assert guard.main(['--root', str(ROOT), '--release', '--ci-receipts',
                       str(tmp_path / 'private-missing-directory')]) == 1
    assert json.loads(capsys.readouterr().out) == {
        'status': 'fail', 'errors': ['publication_evidence_unavailable']}


def test_required_aggregate_cannot_ignore_publication_failure_or_skip():
    source = (ROOT / '.github/workflows/release-gates.yml').read_text(encoding='utf-8')
    publication, aggregate = source.split('\n  publication:\n', 1)[1].split('\n  release-gates:\n', 1)
    assert 'fetch-depth: 0' in publication
    assert 'github.event.pull_request.base.sha' in publication
    assert 'needs: installed-code' in publication
    assert 'if: always()' in publication
    assert '--ci-receipts' in publication
    assert 'needs: [gates, windows, windows-native, macos, installed-code, publication]' in aggregate
    assert 'if: always()' in aggregate
    assert 'test "${{ needs.publication.result }}" = "success"' in aggregate
    assert 'test "${{ needs.installed-code.result }}" = "success"' in aggregate


def test_actual_all_pass_receipt_cannot_certify_redirected_catalog(repository):
    root, _ = repository
    for folder in ('plugins', '.claude-plugin', '.agents'):
        shutil.copytree(ROOT / folder, root / folder, ignore=shutil.ignore_patterns('__pycache__'))
    contract = importlib.import_module('check_compatibility')
    receipt = contract.candidate(root)
    for target in contract.TARGETS:
        platform, kind = contract.target_identity(target)
        receipt['targets'][target] = {
            'outcome': 'pass', 'host_version': '2.1.287', 'python_version': '3.12.3',
            'platform': platform, 'host_kind': kind,
            'packages': contract.target_packages(receipt['packages'], target),
            'checks': dict.fromkeys(contract.target_checks(target), True)}
    assert guard.validate(root, receipt, release=True) == []
    path = root / 'docs/validation/compatibility-candidate.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(receipt))
    git(root, 'add', '.')
    git(root, '-c', 'commit.gpgsign=false', 'commit', '-qm', 'synthetic all-pass baseline')
    base = git(root, 'rev-parse', 'HEAD')
    path = root / '.claude-plugin/marketplace.json'
    catalog = json.loads(path.read_text())
    catalog['plugins'][0]['source'] = 'https://example.invalid/untested'
    commit(root, '.claude-plugin/marketplace.json', json.dumps(catalog))
    assert guard.publication_errors(root, base=base) == ['invalid_claude_marketplace_routes']
