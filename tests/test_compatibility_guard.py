import importlib.util
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compatibility_guard', ROOT / 'scripts/check_compatibility.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_candidate_requires_current_installed_smoke_before_release():
    receipt = guard.candidate(ROOT)
    assert guard.validate(ROOT, receipt) == []
    assert guard.validate(ROOT, receipt, release=True) == [
        'clean_installed_smoke_required_' + target for target in guard.TARGETS]


def test_wsl_smoke_cannot_certify_native_windows_or_macos():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = {'outcome': 'pass', 'host_version': '2.1.287',
                                    'python_version': '3.12.3', 'packages': receipt['packages'],
                                    'checks': dict.fromkeys(guard.CHECKS, True)}
    errors = guard.validate(ROOT, receipt, release=True)
    assert 'clean_installed_smoke_required_code-wsl' not in errors
    assert 'clean_installed_smoke_required_code-windows-no-bash' in errors
    assert 'clean_installed_smoke_required_code-macos' in errors


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
    return {'outcome': 'pass', 'host_version': '2.1.287', 'python_version': '3.12.3',
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


def test_full_release_requires_both_windows_scenarios_and_desktop_skills():
    receipt = guard.candidate(ROOT)
    receipt['targets'] = {target: passing_row(receipt, target) for target in guard.TARGETS}
    assert guard.validate(ROOT, receipt, release=True) == []
    for target in ('code-windows-git-bash', 'desktop-chat-macos', 'cowork-windows'):
        saved = receipt['targets'][target]
        receipt['targets'][target] = {'outcome': 'untested'}
        assert 'clean_installed_smoke_required_' + target in guard.validate(ROOT, receipt, release=True)
        receipt['targets'][target] = saved


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
    assert 'clean_installed_smoke_required_code-linux' in errors


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
