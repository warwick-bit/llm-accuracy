"""The installation smoke keeps answers in memory and gates only on delivery."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "claude_install_smoke", ROOT / "scripts/claude_install_smoke.py"
)
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)

FOOTER_ANSWER = (
    "PRIVATE-ANSWER-NEEDLE stays local.\n\n---\n\n"
    "- **Checked:** supplied statement\n- **Gap:** production state\n"
    "- **Next:** deploy and watch\n"
)


def probe(**updates):
    return {
        "status": "ok",
        "answers": [FOOTER_ANSWER],
        "result_count": 1,
        "fidelity_hook_responses": 1,
        "hook_response_count": 3,
        "builtin_signal_responses": 0,
        "host_inventory": {"status": "reported", "plugin_count": 1},
        "resolved_model": "claude-sonnet-5",
        **updates,
    }


def test_installed_session_loads_profile_plugins_without_tools():
    command = smoke.session_command("claude", "sonnet")
    # The marketplace install is enabled in the profile's user settings.
    assert "--setting-sources" not in command
    assert "--plugin-dir" not in command
    assert command[command.index("--tools") + 1] == ""
    assert command[command.index("--model") + 1] == "sonnet"
    assert {"--strict-mcp-config", "--no-session-persistence"} <= set(command)


def test_stream_input_is_one_user_turn():
    lines = smoke.stream_input("hello").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"type": "user", "message": {"role": "user", "content": "hello"}}
    ]


def test_session_summary_is_raw_free_and_observes_layout():
    summary = smoke.session_summary(probe(), 1)
    assert "PRIVATE-ANSWER-NEEDLE" not in json.dumps(summary)
    assert "answers" not in summary
    assert summary["footer_present"] is True
    assert summary["divider_before_footer"] is True
    assert summary["passed"] is True


def test_footer_layout_is_observed_not_gated():
    summary = smoke.session_summary(probe(answers=["No footer here."]), 1)
    assert summary["footer_present"] is False
    assert summary["divider_before_footer"] is False
    assert summary["passed"] is True


@pytest.mark.parametrize(
    ("updates", "expected_fidelity", "passed"),
    [
        ({"fidelity_hook_responses": 0}, 0, True),
        ({"fidelity_hook_responses": 0}, 1, False),
        ({"fidelity_hook_responses": 1}, 0, False),
        ({"status": "timeout", "answers": []}, 1, False),
        ({"result_count": 2}, 1, False),
    ],
)
def test_session_passes_only_on_expected_hook_delivery(
    updates, expected_fidelity, passed
):
    assert (
        smoke.session_summary(probe(**updates), expected_fidelity)["passed"] is passed
    )


def test_failed_probe_without_answers_still_summarizes():
    summary = smoke.session_summary({"status": "host_unavailable", "answers": []}, 1)
    assert summary["status"] == "host_unavailable"
    assert summary["footer_present"] is False
    assert summary["passed"] is False


def test_bypass_session_omits_footer_observations():
    summary = smoke.session_summary(probe(fidelity_hook_responses=0), 0)
    assert "footer_present" not in summary
    assert summary["passed"] is True


def test_installed_mismatches_counts_missing_and_changed(tmp_path):
    source, installed = tmp_path / "source", tmp_path / "installed"
    for root in (source, installed):
        (root / "hooks").mkdir(parents=True)
    (source / "same.txt").write_bytes(b"same")
    (installed / "same.txt").write_bytes(b"same")
    (source / "hooks/changed.py").write_bytes(b"new")
    (installed / "hooks/changed.py").write_bytes(b"old")
    (source / "missing.md").write_bytes(b"gone")
    tracked = [source / "same.txt", source / "hooks/changed.py", source / "missing.md"]
    assert smoke.installed_mismatches(tracked, source, installed) == 2
    assert smoke.installed_mismatches(tracked[:1], source, installed) == 0


def test_installed_entry_matches_exact_plugin_id():
    listing = json.dumps(
        [
            {"id": "other@llm-accuracy", "version": "9.9.9", "enabled": True},
            {"id": "llm-accuracy@llm-accuracy", "version": "0.6.6", "enabled": True},
        ]
    )
    entry = smoke.installed_entry(listing, "llm-accuracy@llm-accuracy")
    assert entry["version"] == "0.6.6"
    assert smoke.installed_entry("not json", "llm-accuracy@llm-accuracy") == {}
    assert smoke.installed_entry('{"id": "x"}', "x") == {}


def test_install_path_must_stay_inside_profile(tmp_path):
    profile = tmp_path / "profile"
    inside = profile / "plugins/cache/llm-accuracy"
    inside.mkdir(parents=True)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    assert smoke.path_inside(str(inside), profile) == inside.resolve()
    assert smoke.path_inside(str(outside), profile) is None
    assert smoke.path_inside(str(profile / "../elsewhere"), profile) is None
    assert smoke.path_inside(str(profile / "absent"), profile) is None
    assert smoke.path_inside(None, profile) is None


def test_receipt_passes_only_when_every_gate_passes():
    checks: dict[str, object] = {key: True for key in smoke.INSTALL_CHECKS}
    checks.update(
        isolated_cleanup=True,
        tracked_files=22,
        installed_byte_mismatches=0,
        installed_default_session={"passed": True},
        archive_session={"passed": True},
    )
    assert smoke.receipt_passed(checks) is True
    assert (
        smoke.receipt_passed({**checks, "archive_session": {"passed": False}}) is False
    )
    assert smoke.receipt_passed({**checks, "isolated_cleanup": False}) is False
    assert smoke.receipt_passed({**checks, "plugin_install": False}) is False
    skipped = {
        key: value for key, value in checks.items() if not isinstance(value, dict)
    }
    assert smoke.receipt_passed({**skipped, "live_sessions": "skipped"}) is True


def test_marketplace_plugin_id_comes_from_manifests():
    assert smoke.marketplace_plugin_id() == "llm-accuracy@llm-accuracy"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2.1.287 (Claude Code)", "2.1.287 (Claude Code)"),
        ("2.1.287", "2.1.287"),
        ("error: /home/someone/.claude is locked", "unreported"),
        ("", "unreported"),
    ],
)
def test_host_version_reports_only_expected_shape(monkeypatch, raw, expected):
    class Completed:
        stdout = raw

    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **k: Completed())
    assert smoke.host_version("claude") == expected


def test_auth_profile_copies_only_credentials_and_strips_controls(
    tmp_path, monkeypatch
):
    source = tmp_path / "home-profile"
    source.mkdir()
    (source / ".credentials.json").write_text("{}", encoding="utf-8")
    (source / "settings.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(source))
    monkeypatch.setenv("CC_SKIP_CLAIM_FIDELITY", "1")
    root = tmp_path / "smoke"
    root.mkdir()
    env = smoke.auth_profile(root)
    profile = Path(env["CLAUDE_CONFIG_DIR"])
    assert sorted(path.name for path in profile.iterdir()) == [".credentials.json"]
    assert (profile / ".credentials.json").stat().st_mode & 0o777 == 0o600
    assert "CC_SKIP_CLAIM_FIDELITY" not in env


def test_invalid_model_is_rejected_before_any_host_call(monkeypatch, capsys):
    monkeypatch.setattr(
        smoke.shutil, "which", lambda name: pytest.fail("host lookup ran")
    )
    assert smoke.main(["--model", "sonnet; rm -rf /"]) == 2
    assert "invalid model" in capsys.readouterr().err
