"""CI must distinguish real installed delivery from partial or stale evidence."""

import copy
import hashlib
import importlib
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
contract = importlib.import_module("check_compatibility")
ci = importlib.import_module("ci_installed_smoke")
download = importlib.import_module("install_ci_claude")


def passing_row(target, packages):
    platform, kind = contract.target_identity(target)
    return {
        "outcome": "pass",
        "platform": platform,
        "host_kind": kind,
        "host_version": "2.1.287",
        "python_version": "3.14.0",
        "packages": packages,
        "checks": dict.fromkeys(contract.target_checks(target), True),
    }


def installed_row(target, packages):
    row = passing_row(target, packages)
    row['outcome'] = 'installed'
    row['checks'] = dict.fromkeys(contract.installation_checks(target), True)
    row['live_delivery'] = 'not_tested'
    row['isolated_cleanup'] = True
    return row


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_RUN_ID", "12345")
    root, artifacts = tmp_path / "repo", tmp_path / "artifacts"
    root.mkdir()
    artifacts.mkdir()

    def git(*args):
        return (
            subprocess.run(
                ["git", "-C", str(root), *args], capture_output=True, check=True
            )
            .stdout.decode()
            .strip()
        )

    git("init", "-q")
    git("config", "user.name", "Synthetic QA")
    git("config", "user.email", "qa@example.invalid")
    for name in ("plugins", ".claude-plugin", ".agents"):
        shutil.copytree(
            ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__")
        )
    git("add", ".")
    git("-c", "commit.gpgsign=false", "commit", "-qm", "synthetic fixture")
    sha = git("rev-parse", "HEAD")
    candidate = contract.candidate(root)
    candidate["targets"]["code-wsl"] = contract.seal_row(
        passing_row("code-wsl", candidate["packages"]), sha
    )
    for target in contract.CI_TARGETS:
        value = {
            "schema_version": 2,
            "run_id": "12345",
            "target": target,
            "source_commit": sha,
            "row": installed_row(target, candidate["packages"]),
        }
        (artifacts / (target + ".json")).write_text(json.dumps(value))
    return root, artifacts, candidate


def test_same_run_code_receipts_allow_experimental_desktop_gaps_without_rewriting_source(
    evidence,
):
    root, artifacts, candidate = evidence
    original = copy.deepcopy(candidate)
    merged = contract.overlay_ci_receipts(root, candidate, artifacts)
    assert contract.validate(root, merged, release=True) == []
    assert candidate == original
    assert all(
        merged["targets"][target] == {"outcome": "untested"}
        for target in contract.TARGETS[5:]
    )
    # WSL cannot be provided by native Linux, even when all hosted cells pass.
    merged["targets"]["code-wsl"] = {"outcome": "untested"}
    assert "local_live_code_smoke_required" in contract.validate(
        root, merged, release=True
    )


@pytest.mark.parametrize(
    "change", ["stale", "wrong-target", "partial", "missing", "extra", "mixed-run", "old-schema"]
)
def test_ci_overlay_rejects_missing_partial_misrouted_and_other_commit_receipts(
    evidence, change
):
    root, artifacts, candidate = evidence
    path = artifacts / "code-macos.json"
    value = json.loads(path.read_text())
    if change == "stale":
        value["source_commit"] = "0" * 40
    if change == "wrong-target":
        value["target"] = "code-linux"
    if change == "mixed-run":
        value["run_id"] = "67890"
    if change == "old-schema":
        value["schema_version"] = 1
    if change == "partial":
        value["row"]["outcome"] = "untested"
    path.write_text(json.dumps(value))
    if change == "missing":
        path.unlink()
    if change == "extra":
        (artifacts / "unknown.json").write_text("{}")
    with pytest.raises(ValueError):
        contract.overlay_ci_receipts(root, candidate, artifacts)


@pytest.mark.parametrize("change", ["os", "package", "false", "hook", "version", "cleanup", "live-scope", "extra-field"])
def test_ci_overlay_still_requires_current_source_identity_and_all_real_checks(
    evidence, change
):
    root, artifacts, candidate = evidence
    path = artifacts / "code-macos.json"
    value = json.loads(path.read_text())
    row = value["row"]
    if change == "os":
        row["platform"] = "Linux/WSL"
    if change == "package":
        row["packages"]["llm-accuracy"]["sha256"] = "0" * 64
    if change == "false":
        row["checks"]["clean_install"] = False
    if change == "hook":
        row["checks"].pop("installed_hook_execution")
    if change == "cleanup":
        row["isolated_cleanup"] = False
    if change == "live-scope":
        row["live_delivery"] = "pass"
    if change == "extra-field":
        row["raw_provider_payload"] = "synthetic"
    if change == "version":
        row["host_version"] = "2.1.286"
    path.write_text(json.dumps(value))
    merged = contract.overlay_ci_receipts(root, candidate, artifacts)
    assert contract.validate(root, merged, release=True)


@pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"])
def test_ci_auth_is_explicit_and_never_copies_login_or_other_auth_controls(
    tmp_path, monkeypatch, name
):
    source = tmp_path / "user"
    source.mkdir()
    (source / ".credentials.json").write_text("SYNTHETIC_LOGIN")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(source))
    for key in ci.bundle.smoke.CONTROL_VARS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(source))
    monkeypatch.setenv(name, "SYNTHETIC_CI_AUTH")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://example.invalid")
    monkeypatch.setenv("CLAUDE_CODE_GIT_BASH_PATH", "synthetic-bash.exe")
    monkeypatch.setenv("CLAUDE_CODE_USE_POWERSHELL_TOOL", "1")
    (tmp_path / "isolated").mkdir()
    env = ci.bundle.smoke.auth_profile(tmp_path / "isolated", ci=True)
    assert env[name] == "SYNTHETIC_CI_AUTH"
    assert "ANTHROPIC_BASE_URL" not in env
    assert env['CLAUDE_CODE_GIT_BASH_PATH'] == 'synthetic-bash.exe'
    assert env['CLAUDE_CODE_USE_POWERSHELL_TOOL'] == '1'
    assert not (Path(env["CLAUDE_CONFIG_DIR"]) / ".credentials.json").exists()


@pytest.mark.parametrize("auth", ["none", "both"])
def test_live_auth_never_falls_back_to_local_login(tmp_path, monkeypatch, auth):
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
        if auth == "both":
            monkeypatch.setenv(key, "SYNTHETIC_AUTH")
    (tmp_path / "isolated").mkdir()
    with pytest.raises(ValueError, match="ci_authentication_required"):
        ci.bundle.smoke.auth_profile(tmp_path / "isolated", ci=True)
    (tmp_path / "offline").mkdir()
    env = ci.bundle.smoke.auth_profile(tmp_path / "offline", ci=True, live=False)
    assert not any(
        key in env for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
    )


def test_auth_failure_is_fixed_and_happens_before_any_cli_call(
    tmp_path, monkeypatch, capsys
):
    for key in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(ci, "host_checks", lambda target: {})
    monkeypatch.setattr(
        ci.bundle, "run_smoke", lambda *a, **k: pytest.fail("CLI ran without auth")
    )
    assert (
        ci.main(
            [
                "--target",
                "code-linux",
                "--claude",
                "synthetic",
                "--live",
                "--receipt",
                str(tmp_path / "qa.json"),
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "fail",
        "error": "ci_authentication_required",
    }
    assert not (tmp_path / "qa.json").exists()


def test_partial_or_unclean_live_report_never_becomes_a_pass():
    for report in (
        {"status": "partial"},
        {"status": "pass", "partial": False, "isolated_cleanup": False},
    ):
        with pytest.raises(ValueError, match="ci_live_smoke_failed"):
            ci.live_receipt(report, "code-linux", {})


def test_ci_live_pass_is_sealed_to_the_commit_it_tested():
    report = {
        "status": "pass", "partial": False, "isolated_cleanup": True,
        "scope": "code_bundle_registration_accuracy_delivery", "platform": "Linux",
        "source_commit": "b" * 40, "host_version": "2.1.288", "python_version": "3.12.3",
        "packages": contract.candidate(ROOT)["packages"],
        "checks": dict.fromkeys(contract.CHECKS + ("installed_hook_execution",), True),
    }
    receipt = ci.live_receipt(report, "code-linux", {})
    assert receipt["source_commit"] == receipt["row"]["source_commit"] == "b" * 40
    assert contract.seal_errors(receipt["row"], "code-linux") == []
    assert "installed_hook_execution" not in receipt["row"]["checks"]


def test_cli_output_cannot_echo_provider_exception(tmp_path, monkeypatch, capsys):
    def fail(options):
        raise ValueError("SYNTHETIC_PROVIDER_ERROR raw secret or answer")

    monkeypatch.setattr(ci, "run", fail)
    assert (
        ci.main(
            [
                "--target",
                "code-linux",
                "--claude",
                "synthetic",
                "--receipt",
                str(tmp_path / "qa.json"),
            ]
        )
        == 1
    )
    assert "SYNTHETIC_PROVIDER_ERROR" not in capsys.readouterr().out


def test_receipt_too_deep_to_check_emits_fixed_failure(tmp_path, monkeypatch, capsys):
    # The depth at which parsing or hashing recurses out differs by Python version, so force it here.
    def too_deep(options):
        raise RecursionError("synthetic maximum recursion depth")

    monkeypatch.setattr(ci, "run", too_deep)
    arguments = ["--target", "code-linux", "--claude", "synthetic", "--receipt", str(tmp_path / "qa.json")]
    assert ci.main(arguments) == 1
    assert json.loads(capsys.readouterr().out) == {"status": "fail", "error": "ci_installed_qa_failed"}
    assert not (tmp_path / "qa.json").exists()


def test_windows_host_proof_rejects_usable_bash_in_no_bash_mode(monkeypatch):
    monkeypatch.setattr(ci.bundle.smoke, "platform_label", lambda: "Windows")
    monkeypatch.setattr(ci, "usable_bash", lambda p: bool(p))
    with pytest.raises(ValueError, match="ci_bash_mode_mismatch"):
        ci.host_checks("code-windows-no-bash")
    assert ci.host_checks("code-windows-git-bash") == {"git_bash_present": True}
    monkeypatch.setattr(ci, "usable_bash", lambda p: False)
    monkeypatch.delenv("CLAUDE_CODE_GIT_BASH_PATH", raising=False)
    assert ci.host_checks("code-windows-no-bash") == {"git_bash_absent": True}
    with pytest.raises(ValueError):
        ci.host_checks("code-windows-git-bash")


@pytest.mark.parametrize("directory", ["System32", "Sysnative", "SysWOW64", "WindowsApps"])
def test_windows_wsl_launcher_is_not_git_bash(monkeypatch, directory):
    calls = []
    monkeypatch.setattr(ci.subprocess, "run", lambda *a, **kw: calls.append(True))
    assert ci.usable_bash(f"C:/Windows/{directory}/bash.exe") is False
    assert calls == []


def test_native_git_bash_version_is_accepted(monkeypatch):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=b"GNU bash, version 5.2")

    monkeypatch.setattr(ci.subprocess, "run", run)
    path = "C:/Program Files/Git/bin/bash.exe"
    assert ci.usable_bash(path) is True
    assert calls == [[path, "--version"]]


def test_native_linux_receipt_cannot_be_collected_on_wsl(monkeypatch):
    monkeypatch.setattr(ci.bundle.smoke, "platform_label", lambda: "Linux/WSL")
    with pytest.raises(ValueError, match="ci_host_mismatch"):
        ci.host_checks("code-linux")


def test_downloader_rejects_changed_manifest_and_unsupported_platform():
    pins = {"platforms": {"linux-x64": "reviewed"}}
    with pytest.raises(ValueError, match="ci_claude_manifest_mismatch"):
        download.verify_manifest(
            {"platforms": {"linux-x64": {"checksum": "changed"}}}, pins, "linux-x64"
        )
    with pytest.raises(ValueError, match="ci_claude_platform_unsupported"):
        download.verify_manifest({}, pins, "unknown")


def test_bad_binary_cannot_replace_executable_and_partial_is_cleaned(
    tmp_path, monkeypatch
):
    pins = {
        "version": "2.1.287",
        "origin": "https://example.invalid",
        "platforms": {"linux-x64": hashlib.sha256(b"reviewed").hexdigest()},
    }
    pinfile = tmp_path / "pins.json"
    pinfile.write_text(json.dumps(pins))
    monkeypatch.setattr(download, "PINS", pinfile)
    monkeypatch.setattr(download, "native_platform", lambda: "linux-x64")
    manifest = {
        "platforms": {"linux-x64": {"checksum": pins["platforms"]["linux-x64"]}}
    }

    def fetch(url, **kw):
        return io.BytesIO(
            json.dumps(manifest).encode()
            if url.endswith("manifest.json")
            else b"changed"
        )

    monkeypatch.setattr(download.urllib.request, "urlopen", fetch)
    binary = tmp_path / "bin" / "claude"
    binary.parent.mkdir()
    binary.write_bytes(b"previous")
    with pytest.raises(ValueError, match="ci_claude_binary_mismatch"):
        download.download(binary.parent)
    assert binary.read_bytes() == b"previous"
    assert not binary.with_name("claude.partial").exists()


def test_installation_only_cannot_claim_live_pass(monkeypatch):
    monkeypatch.setattr(ci, 'host_checks', lambda target: {})
    report = {
        'status': 'partial', 'partial': True, 'isolated_cleanup': True,
        'scope': 'code_bundle_registration_accuracy_delivery', 'platform': 'Linux',
        'source_commit': 'synthetic', 'host_version': '2.1.287', 'python_version': '3.14.0',
        'packages': contract.candidate(ROOT)['packages'],
        'checks': dict.fromkeys(contract.INSTALL_CHECKS, True),
    }
    monkeypatch.setattr(ci.bundle, 'run_smoke', lambda *a, **k: report)
    result = ci.run(SimpleNamespace(target='code-linux', live=False, claude='synthetic', baseline='synthetic'))
    assert result['row']['outcome'] == 'installed'
    assert result['row']['live_delivery'] == 'not_tested'
    assert 'prompt_delivery' not in result['row']['checks']
    with pytest.raises(ValueError, match='ci_live_smoke_failed'):
        ci.live_receipt(report, 'code-linux', {})


def test_overlay_requires_actual_ci_run_context(evidence, monkeypatch):
    root, artifacts, candidate = evidence
    monkeypatch.delenv('GITHUB_RUN_ID', raising=False)
    with pytest.raises(ValueError, match='ci_run_identity_unavailable'):
        contract.overlay_ci_receipts(root, candidate, artifacts)


def test_powershell_mode_with_bash_present_cannot_certify_bash_absence(evidence):
    root, artifacts, candidate = evidence
    path = artifacts / 'code-windows-no-bash.json'
    value = json.loads(path.read_text())
    value['row']['checks'].pop('git_bash_absent')
    value['row']['checks']['powershell_mode_with_bash_present'] = True
    path.write_text(json.dumps(value))
    assert contract.validate(root, contract.overlay_ci_receipts(root, candidate, artifacts), release=True)
