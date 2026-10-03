import importlib.util
import shutil
import json

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compatibility_guard', ROOT / 'scripts/check_compatibility.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_candidate_requires_current_installed_smoke_before_release():
    receipt = guard.candidate(ROOT)
    assert guard.validate(ROOT, receipt) == []
    assert guard.validate(ROOT, receipt, release=True) == [
        'native_installation_required_' + target for target in guard.CI_TARGETS] + ['local_live_code_smoke_required']


def test_wsl_smoke_cannot_certify_native_windows_or_macos():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = {'outcome': 'pass', 'host_version': '2.1.287',
                                    'platform': 'Linux/WSL', 'host_kind': 'code',
                                    'python_version': '3.12.3', 'packages': receipt['packages'],
                                    'checks': dict.fromkeys(guard.CHECKS, True)}
    errors = guard.validate(ROOT, receipt, release=True)
    assert 'local_live_code_smoke_required' not in errors
    assert 'native_installation_required_code-windows-no-bash' in errors
    assert 'native_installation_required_code-macos' in errors


def test_old_package_hash_cannot_claim_current_smoke():
    receipt = guard.candidate(ROOT)
    receipt['packages']['llm-accuracy']['sha256'] = '0' * 64
    assert 'invalid_or_stale_packages' in guard.validate(ROOT, receipt)


def test_matrix_cannot_drop_windows_or_desktop_gap():
    receipt = guard.candidate(ROOT)
    del receipt['targets']['code-windows-no-bash']
    assert 'missing_or_unknown_target' in guard.validate(ROOT, receipt)


def test_unsubstantiated_pass_does_not_satisfy_release():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = {'outcome': 'pass'}
    errors = guard.validate(ROOT, receipt, release=True)
    assert 'missing_host_version_code-wsl' in errors
    assert 'missing_checks_code-wsl' in errors


def test_each_pass_keeps_its_original_source_binding_and_python_version():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-windows-no-bash'] = {
        'outcome': 'pass', 'host_version': '2.1.287', 'python_version': '3.8.0',
        'packages': {}, 'checks': dict.fromkeys(guard.CHECKS, True)}
    errors = guard.validate(ROOT, receipt)
    assert 'missing_or_unsupported_python_version_code-windows-no-bash' in errors
    assert 'stale_target_packages_code-windows-no-bash' in errors


def passing_row(receipt, target):
    platform, kind = guard.target_identity(target)
    return {'outcome': 'pass', 'host_version': '2.1.287', 'python_version': '3.12.3',
            'platform': platform, 'host_kind': kind,
            'packages': guard.target_packages(receipt['packages'], target),
            'checks': dict.fromkeys(guard.target_checks(target), True)}


def test_code_checks_cannot_certify_chat_or_cowork():
    receipt = guard.candidate(ROOT)
    for target in guard.TARGETS[5:]:
        row = passing_row(receipt, target)
        row['checks'] = dict.fromkeys(guard.CHECKS, True)
        receipt['targets'][target] = row
    errors = guard.validate(ROOT, receipt)
    assert all('missing_checks_' + target in errors for target in guard.TARGETS[5:])


def installed_row(receipt, target):
    row = passing_row(receipt, target)
    row.update(outcome='installed', live_delivery='not_tested', isolated_cleanup=True)
    row['checks'] = dict.fromkeys(guard.installation_checks(target), True)
    return row


def test_release_requires_native_installations_and_one_local_live_code_pass():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = passing_row(receipt, 'code-wsl')
    for target in guard.CI_TARGETS:
        receipt['native_installations'][target] = installed_row(receipt, target)
    assert guard.validate(ROOT, receipt, release=True) == []
    assert receipt['targets']['code-macos'] == {'outcome': 'untested'}
    for target in guard.CI_TARGETS:
        saved = receipt['native_installations'][target]
        receipt['native_installations'][target] = {'outcome': 'untested'}
        assert 'native_installation_required_' + target in guard.validate(ROOT, receipt, release=True)
        receipt['native_installations'][target] = saved
    receipt['targets']['code-wsl'] = {'outcome': 'untested'}
    assert 'local_live_code_smoke_required' in guard.validate(ROOT, receipt, release=True)


def test_offline_rows_cannot_be_used_as_live_passes_or_drop_native_targets():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-linux'] = installed_row(receipt, 'code-linux')
    assert 'invalid_outcome_code-linux' in guard.validate(ROOT, receipt)
    del receipt['native_installations']['code-macos']
    assert 'missing_or_unknown_native_installation' in guard.validate(ROOT, receipt)


def test_schema3_cannot_silently_pass_schema4_policy():
    receipt = guard.candidate(ROOT)
    receipt['schema_version'] = 3
    assert 'invalid_or_stale_schema_version' in guard.validate(ROOT, receipt)


def test_support_policy_cannot_silently_promote_desktop_or_relax_code():
    receipt = guard.candidate(ROOT)
    receipt['support_policy']['code'] = 'experimental'
    assert 'invalid_or_stale_support_policy' in guard.validate(ROOT, receipt)
    receipt = guard.candidate(ROOT)
    receipt['support_policy']['desktop_chat'] = 'verified'
    assert 'invalid_or_stale_support_policy' in guard.validate(ROOT, receipt)


def test_desktop_pass_cannot_claim_local_persistence_or_hook_capture():
    receipt = guard.candidate(ROOT)
    for target in ('desktop-chat-windows', 'cowork-macos'):
        row = passing_row(receipt, target)
        row['packages'] = receipt['packages']
        row['checks']['prompt_delivery'] = True
        receipt['targets'][target] = row
    errors = guard.validate(ROOT, receipt)
    for target in ('desktop-chat-windows', 'cowork-macos'):
        assert 'stale_target_packages_' + target in errors
        assert 'missing_checks_' + target in errors


def test_desktop_skills_do_not_require_python_but_do_require_invocation():
    receipt = guard.candidate(ROOT)
    target = 'desktop-chat-windows'
    receipt['targets'][target] = passing_row(receipt, target)
    del receipt['targets'][target]['python_version']
    assert guard.validate(ROOT, receipt) == []
    receipt['targets'][target]['checks']['skill_invocation'] = False
    assert 'missing_checks_' + target in guard.validate(ROOT, receipt)


def test_malformed_receipt_and_target_fail_closed():
    assert guard.validate(ROOT, [], release=True) == ['invalid_compatibility_receipt']
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-linux'] = None
    errors = guard.validate(ROOT, receipt, release=True)
    assert 'invalid_outcome_code-linux' in errors
    assert 'native_installation_required_code-linux' in errors


def test_each_windows_receipt_requires_its_own_bash_environment_proof():
    receipt = guard.candidate(ROOT)
    for target, field in (('code-windows-no-bash', 'git_bash_absent'),
                          ('code-windows-git-bash', 'git_bash_present')):
        receipt['targets'][target] = passing_row(receipt, target)
        del receipt['targets'][target]['checks'][field]
        assert 'missing_checks_' + target in guard.validate(ROOT, receipt)


def test_package_binding_changes_only_with_packaged_source(tmp_path):
    shutil.copytree(ROOT / 'plugins/llm-accuracy', tmp_path / 'plugins/llm-accuracy',
                    ignore=shutil.ignore_patterns('__pycache__'))
    before = guard.package_binding(tmp_path, 'llm-accuracy')
    (tmp_path / 'README.md').write_text('Synthetic root guide change')
    assert guard.package_binding(tmp_path, 'llm-accuracy') == before
    packaged = tmp_path / 'plugins/llm-accuracy/README.md'
    packaged.write_text('Synthetic packaged guide change')
    assert guard.package_binding(tmp_path, 'llm-accuracy') != before


@pytest.fixture
def distribution(tmp_path):
    for folder in ('plugins', '.claude-plugin', '.agents'):
        shutil.copytree(ROOT / folder, tmp_path / folder, ignore=shutil.ignore_patterns('__pycache__'))
    return tmp_path


@pytest.mark.parametrize('change', ['external', 'dictionary', 'unknown', 'duplicate', 'name',
                                  'inline_hooks', 'strict_override', 'traversal', 'missing_prefix',
                                  'null', 'case', 'extra_codex', 'codex_redirect', 'codex_policy'])
def test_catalog_routes_and_behavior_cannot_reuse_package_attestations(distribution, change):
    path = distribution / ('.agents/plugins/marketplace.json' if change.startswith(('extra_codex', 'codex_'))
                           else '.claude-plugin/marketplace.json')
    value = json.loads(path.read_text())
    entry = value['plugins'][0]
    if change == 'external':
        entry['source'] = 'https://example.invalid/untested'
    elif change == 'dictionary':
        entry['source'] = {'source': 'github', 'repo': 'synthetic/untested'}
    elif change == 'unknown':
        value['plugins'].append({'name': 'untested', 'source': './plugins/untested'})
    elif change == 'duplicate':
        value['plugins'][1] = entry.copy()
    elif change == 'name':
        value['name'] = 'untested-marketplace'
    elif change == 'inline_hooks':
        entry['hooks'] = {'SessionStart': []}
    elif change == 'strict_override':
        entry['strict'] = False
    elif change == 'traversal':
        entry['source'] = './plugins/../untested'
    elif change == 'missing_prefix':
        entry['source'] = 'plugins/llm-accuracy'
    elif change == 'null':
        entry['name'] = None
    elif change == 'case':
        entry['name'] = 'LLM-Accuracy'
    elif change == 'extra_codex':
        value['plugins'].append(entry.copy())
    elif change == 'codex_redirect':
        entry['source']['path'] = './plugins/untested'
    elif change == 'codex_policy':
        entry['policy']['installation'] = 'REQUIRED'
    path.write_text(json.dumps(value))
    label = 'invalid_codex_marketplace_routes' if 'codex' in change else 'invalid_claude_marketplace_routes'
    assert label in guard.validate(distribution, guard.candidate(distribution))


def test_metadata_only_catalog_edit_keeps_fixed_routes(distribution):
    path = distribution / '.claude-plugin/marketplace.json'
    value = json.loads(path.read_text())
    value['description'] = value['plugins'][0]['description'] = 'Synthetic metadata'
    path.write_text(json.dumps(value))
    assert guard.validate(distribution, guard.candidate(distribution)) == []


def test_host_identity_cannot_be_copied_between_os_or_modes():
    receipt = guard.candidate(ROOT)
    for target, donor in (('code-macos', 'code-wsl'), ('code-linux', 'code-wsl'),
                          ('cowork-windows', 'desktop-chat-windows'),
                          ('desktop-chat-linux', 'cowork-linux')):
        row = passing_row(receipt, target)
        row['platform'], row['host_kind'] = guard.target_identity(donor)
        receipt['targets'][target] = row
        assert 'invalid_host_identity_' + target in guard.validate(ROOT, receipt)
    receipt['targets']['code-wsl'] = passing_row(receipt, 'code-wsl')
    del receipt['targets']['code-wsl']['platform']
    assert 'invalid_host_identity_code-wsl' in guard.validate(ROOT, receipt)


@pytest.mark.parametrize('value', [None, 1, 'true', False])
def test_code_pass_requires_actual_invalid_python_recovery(value):
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = passing_row(receipt, 'code-wsl')
    checks = receipt['targets']['code-wsl']['checks']
    if value is None:
        del checks['invalid_python_advisory_then_recovery']
    else:
        checks['invalid_python_advisory_then_recovery'] = value
    assert 'missing_checks_code-wsl' in guard.validate(ROOT, receipt)


def test_package_hash_order_is_independent_of_native_path_comparison(tmp_path):
    directory = tmp_path / 'plugins/llm-accuracy'
    (directory / '.claude-plugin').mkdir(parents=True)
    (directory / '.claude-plugin/plugin.json').write_text('{"version":"1.0.0"}')
    for filename in ('B.py', 'a.py', 'a.b', 'a/nested.py'):
        path = directory / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic source')
    class FoldedPath(type(Path())):
        def __lt__(self, other):
            return str(self).lower() < str(other).lower()
    original = sorted(directory.rglob('*'))
    folded = sorted(FoldedPath(directory).rglob('*'))
    assert [str(p) for p in original] != [str(p) for p in folded]
    assert guard.package_binding(tmp_path, 'llm-accuracy') == guard.package_binding(FoldedPath(tmp_path), 'llm-accuracy')
