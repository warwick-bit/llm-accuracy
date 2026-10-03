"""Recording a pass seals the actual run; it never writes a failed, partial or misrouted one."""

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
contract = importlib.import_module("check_compatibility")
recorder = importlib.import_module("record_compatibility_pass")
TESTED = "a" * 40


@pytest.fixture
def distribution(tmp_path):
    for folder in ("plugins", ".claude-plugin", ".agents"):
        shutil.copytree(
            ROOT / folder,
            tmp_path / folder,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    path = tmp_path / "docs/validation/compatibility-candidate.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(contract.candidate(tmp_path), indent=2) + "\n")
    return tmp_path, path


def bundle_report(root, platform="Linux/WSL"):
    return {
        "scope": "code_bundle_registration_accuracy_delivery",
        "source_commit": TESTED,
        "platform": platform,
        "desktop_gui": "not_tested",
        "windows_bash": "not_tested",
        "partial": False,
        "host_version": "2.1.288",
        "python_version": "3.12.3",
        "packages": contract.candidate(root)["packages"],
        "checks": dict.fromkeys(contract.CHECKS + ("installed_hook_execution",), True),
        "invalid_python_advisory_then_recovery": True,
        "isolated_cleanup": True,
        "status": "pass",
    }


def record(root, capsys, target, *arguments):
    code = recorder.main(["--root", str(root), "--target", target, *arguments])
    return code, json.loads(capsys.readouterr().out)


def write(root, name, value):
    path = root / name
    path.write_text(json.dumps(value))
    return str(path)


def test_records_one_sealed_code_pass_from_a_live_bundle_receipt(distribution, capsys):
    root, path = distribution
    report = bundle_report(root)
    code, output = record(
        root, capsys, "code-wsl", "--bundle-receipt", write(root, "run.json", report)
    )
    assert (code, output) == (0, {"status": "pass", "target": "code-wsl", "errors": []})
    receipt = json.loads(path.read_text())
    row = receipt["targets"]["code-wsl"]
    assert row["source_commit"] == TESTED
    assert row == contract.code_pass_row(report, "code-wsl", {})
    assert set(row["checks"]) == set(contract.CHECKS)
    assert contract.validate(root, receipt) == []
    assert b'\r' not in path.read_bytes()


@pytest.mark.parametrize(
    "change",
    [
        "failed",
        "partial",
        "unclean",
        "other_platform",
        "false_check",
        "stale_packages",
        "scope",
        "no_commit",
    ],
)
def test_failed_partial_misrouted_or_stale_run_is_never_written(
    distribution, capsys, change
):
    root, path = distribution
    before = path.read_bytes()
    report = bundle_report(root)
    if change == "failed":
        report["status"] = "fail"
    elif change == "partial":
        report["partial"] = True
    elif change == "unclean":
        report["isolated_cleanup"] = False
    elif change == "other_platform":
        report["platform"] = "Linux"
    elif change == "false_check":
        report["checks"]["upgrade"] = False
    elif change == "stale_packages":
        report["packages"]["llm-accuracy"]["sha256"] = "0" * 64
    elif change == "scope":
        report["scope"] = "code_install_only"
    else:
        del report["source_commit"]
    code, output = record(
        root, capsys, "code-wsl", "--bundle-receipt", write(root, "run.json", report)
    )
    assert code == 1 and output["status"] == "fail" and output["errors"]
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "target, state",
    [("code-windows-no-bash", "absent"), ("code-windows-git-bash", "present")],
)
def test_windows_pass_needs_the_bash_state_proved_for_that_run(
    distribution, capsys, target, state
):
    root, path = distribution
    receipt = write(root, "run.json", bundle_report(root, platform="Windows"))
    other = "present" if state == "absent" else "absent"
    for arguments in ([], ["--git-bash", other]):
        code, output = record(
            root, capsys, target, "--bundle-receipt", receipt, *arguments
        )
        assert (code, output["errors"]) == (1, ["git_bash_proof_mismatch"])
    code, output = record(
        root, capsys, target, "--bundle-receipt", receipt, "--git-bash", state
    )
    assert code == 0, output
    assert (
        json.loads(path.read_text())["targets"][target]["checks"]["git_bash_" + state]
        is True
    )
    code, output = record(
        root, capsys, "code-wsl", "--bundle-receipt", receipt, "--git-bash", state
    )
    assert (code, output["errors"]) == (1, ["git_bash_proof_mismatch"])


def test_desktop_row_is_sealed_with_its_tested_commit(distribution, capsys):
    root, path = distribution
    target = "desktop-chat-macos"
    platform, kind = contract.target_identity(target)
    row = {
        "outcome": "pass",
        "platform": platform,
        "host_kind": kind,
        "host_version": "1.2.3",
        "packages": contract.target_packages(
            contract.candidate(root)["packages"], target
        ),
        "checks": dict.fromkeys(contract.CHAT_CHECKS, True),
        "source_commit": TESTED,
    }
    code, output = record(root, capsys, target, "--row", write(root, "ui.json", row))
    assert code == 0, output
    assert json.loads(path.read_text())["targets"][target] == contract.seal_row(
        row, TESTED
    )
    del row["source_commit"]
    code, output = record(
        root, capsys, "desktop-chat-windows", "--row", write(root, "ui.json", row)
    )
    assert (code, output["errors"]) == (
        1,
        [
            "invalid_host_identity_desktop-chat-windows",
            "missing_source_commit_desktop-chat-windows",
        ],
    )


def test_each_host_kind_uses_its_own_evidence_source(distribution, capsys):
    root, path = distribution
    before = path.read_bytes()
    receipt = write(root, "run.json", bundle_report(root))
    code, output = record(root, capsys, "cowork-linux", "--bundle-receipt", receipt)
    assert (code, output["errors"]) == (1, ["desktop_pass_requires_row"])
    code, output = record(root, capsys, "code-wsl", "--row", receipt)
    assert (code, output["errors"]) == (1, ["code_pass_requires_bundle_receipt"])
    assert path.read_bytes() == before


def test_malformed_input_reports_a_fixed_label_without_echoing_it(distribution, capsys):
    root, path = distribution
    before = path.read_bytes()
    source = root / "run.json"
    source.write_text("SYNTHETIC_SECRET_NEEDLE {")
    code, output = record(root, capsys, "code-wsl", "--bundle-receipt", str(source))
    assert (code, output["errors"]) == (1, ["invalid_pass_input"])
    assert "SYNTHETIC_SECRET_NEEDLE" not in json.dumps(output)
    assert path.read_bytes() == before


def test_desktop_row_must_record_a_pass(distribution, capsys):
    root, path = distribution
    before = path.read_bytes()
    row = {'outcome': 'untested', 'platform': 'Darwin', 'source_commit': TESTED, 'note': 'synthetic'}
    code, output = record(root, capsys, 'desktop-chat-macos', '--row', write(root, 'ui.json', row))
    assert (code, output['errors']) == (1, ['desktop_pass_requires_row'])
    assert path.read_bytes() == before


def test_failed_write_leaves_the_candidate_intact(distribution, capsys, monkeypatch):
    root, path = distribution
    before = path.read_bytes()
    def fail(source, target):
        raise PermissionError('synthetic read-only candidate')
    monkeypatch.setattr(contract.os, 'replace', fail)
    code, output = record(root, capsys, 'code-wsl', '--bundle-receipt', write(root, 'run.json', bundle_report(root)))
    assert (code, output['errors']) == (1, ['candidate_write_failed'])
    assert path.read_bytes() == before
    assert sorted(item.name for item in path.parent.iterdir()) == [path.name]


def test_deeply_nested_input_gets_a_fixed_label(distribution, capsys):
    root, path = distribution
    before = path.read_bytes()
    source = root / 'run.json'
    source.write_text('[' * 200000 + ']' * 200000)
    code, output = record(root, capsys, 'code-wsl', '--bundle-receipt', str(source))
    assert (code, output['errors']) == (1, ['invalid_pass_input'])
    assert path.read_bytes() == before


def test_receipt_writer_replaces_atomically_with_lf_endings(tmp_path):
    path = tmp_path / 'candidate.json'
    path.write_bytes(b'{"old": true}\r\n')
    contract.write_receipt(path, {'schema_version': 5, 'nested': {'value': 'synthetic'}})
    assert path.read_bytes() == b'{\n  "schema_version": 5,\n  "nested": {\n    "value": "synthetic"\n  }\n}\n'
    assert [item.name for item in tmp_path.iterdir()] == ['candidate.json']


def test_row_too_deep_to_write_gets_a_fixed_label(distribution, capsys, monkeypatch):
    # The depth at which the indented writer recurses out differs by Python version
    # (about 3000 levels on 3.12, deeper on 3.13+), so force it here.
    root, path = distribution
    before = path.read_bytes()
    def too_deep(target, receipt):
        raise RecursionError('synthetic maximum recursion depth')
    monkeypatch.setattr(recorder, 'write_receipt', too_deep)
    code, output = record(root, capsys, 'code-wsl', '--bundle-receipt', write(root, 'run.json', bundle_report(root)))
    assert (code, output['errors']) == (1, ['invalid_pass_input'])
    assert path.read_bytes() == before
