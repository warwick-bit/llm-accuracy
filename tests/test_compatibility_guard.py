import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compatibility_guard', ROOT / 'scripts/check_compatibility.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_candidate_requires_current_installed_smoke_before_release():
    receipt = guard.candidate(ROOT)
    assert guard.validate(ROOT, receipt) == []
    assert guard.validate(ROOT, receipt, release=True) == [
        'clean_installed_smoke_required_' + target for target in guard.TARGETS[:4]]


def test_wsl_smoke_cannot_certify_native_windows_or_macos():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = {'outcome': 'pass', 'host_version': '2.1.287',
                                    'python_version': '3.12.3', 'packages': receipt['packages'],
                                    'checks': dict.fromkeys(guard.CHECKS, True)}
    errors = guard.validate(ROOT, receipt, release=True)
    assert 'clean_installed_smoke_required_code-wsl' not in errors
    assert 'clean_installed_smoke_required_code-windows' in errors
    assert 'clean_installed_smoke_required_code-macos' in errors


def test_old_package_hash_cannot_claim_current_smoke():
    receipt = guard.candidate(ROOT)
    receipt['packages']['llm-accuracy']['sha256'] = '0' * 64
    assert 'invalid_or_stale_packages' in guard.validate(ROOT, receipt)


def test_matrix_cannot_drop_windows_or_desktop_gap():
    receipt = guard.candidate(ROOT)
    del receipt['targets']['code-windows']
    assert 'missing_or_unknown_target' in guard.validate(ROOT, receipt)


def test_unsubstantiated_pass_does_not_satisfy_release():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-wsl'] = {'outcome': 'pass'}
    errors = guard.validate(ROOT, receipt, release=True)
    assert 'missing_host_version_code-wsl' in errors
    assert 'missing_checks_code-wsl' in errors


def test_each_pass_keeps_its_original_source_binding_and_python_version():
    receipt = guard.candidate(ROOT)
    receipt['targets']['code-windows'] = {
        'outcome': 'pass', 'host_version': '2.1.287', 'python_version': '3.8.0',
        'packages': {}, 'checks': dict.fromkeys(guard.CHECKS, True)}
    errors = guard.validate(ROOT, receipt)
    assert 'missing_or_unsupported_python_version_code-windows' in errors
    assert 'stale_target_packages_code-windows' in errors
