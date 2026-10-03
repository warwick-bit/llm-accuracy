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


@pytest.fixture
def evidence(tmp_path):
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
    candidate["targets"]["code-wsl"] = passing_row("code-wsl", candidate["packages"])
    for target in contract.CI_TARGETS:
        value = {
            "schema_version": 1,
            "target": target,
            "source_commit": sha,
            "row": passing_row(target, candidate["packages"]),
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
    assert "clean_installed_smoke_required_code-wsl" in contract.validate(
        root, merged, release=True
    )


@pytest.mark.parametrize(
    "change", ["stale", "wrong-target", "partial", "missing", "extra"]
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
    if change == "partial":
        value["row"]["outcome"] = "untested"
    path.write_text(json.dumps(value))
    if change == "missing":
        path.unlink()
    if change == "extra":
        (artifacts / "unknown.json").write_text("{}")
    with pytest.raises(ValueError):
        contract.overlay_ci_receipts(root, candidate, artifacts)


@pytest.mark.parametrize("change", ["os", "package", "false", "recovery", "version"])
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
        row["checks"]["prompt_delivery"] = False
    if change == "recovery":
        row["checks"].pop("invalid_python_advisory_then_recovery")
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


def test_offline_result_can_pass_installation_only_without_certifying_live_delivery(
    monkeypatch,
):
    monkeypatch.setattr(ci, "host_checks", lambda target: {})
    report = {
        "status": "partial",
        "partial": True,
        "isolated_cleanup": True,
        "source_commit": "synthetic",
        "packages": {},
        "checks": dict.fromkeys(
            ("clean_install", "configured_python", "upgrade", "uninstall"), True
        ),
    }
    monkeypatch.setattr(ci.bundle, "run_smoke", lambda *a, **k: report)
    result = ci.run(
        SimpleNamespace(
            target="code-linux", live=False, claude="synthetic", baseline="synthetic"
        )
    )
    assert result["status"] == "installation_only" and result["partial"] is True
    assert result["live_delivery"] == "not_tested"
    assert "row" not in result
