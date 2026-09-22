"""Fast checks for the distribution boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "llm-accuracy"
LEDGER = ROOT / "plugins" / "session-ledger"
DETERMINISTIC = ROOT / "plugins" / "deterministic-data"


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_claude_plugin_manifest_identifies_the_plugin() -> None:
    claude = load_json("plugins/llm-accuracy/.claude-plugin/plugin.json")

    assert claude["name"] == "llm-accuracy"
    assert claude["version"] == "0.6.0"
    assert claude["license"] == "MIT"
    assert "codex" not in str(claude).lower()


def test_claude_marketplace_publishes_the_three_isolated_plugins() -> None:
    claude = load_json(".claude-plugin/marketplace.json")

    assert claude["name"] == "llm-accuracy"
    assert [entry["name"] for entry in claude["plugins"]] == [
        "llm-accuracy",
        "deterministic-data",
        "session-ledger",
    ]


def test_deterministic_data_manifest_is_separate_and_claude_only() -> None:
    manifest = load_json("plugins/deterministic-data/.claude-plugin/plugin.json")

    assert manifest["name"] == "deterministic-data"
    assert manifest["version"] == "0.1.0"
    assert manifest["license"] == "MIT"
    assert not (DETERMINISTIC / ".codex-plugin").exists()


def test_session_ledger_manifest_is_separate_and_claude_only() -> None:
    manifest = load_json("plugins/session-ledger/.claude-plugin/plugin.json")

    assert manifest["name"] == "session-ledger"
    assert manifest["version"] == "0.2.4"
    assert manifest["license"] == "MIT"
    assert manifest["defaultEnabled"] is False
    assert not (LEDGER / ".codex-plugin").exists()
    assert "rolling record and compact summary can contain sensitive local content" in (
        (LEDGER / "README.md").read_text(encoding="utf-8")
    )


def test_distribution_contains_no_codex_runtime_package() -> None:
    assert not (ROOT / ".agents" / "plugins" / "marketplace.json").exists()
    assert not (PLUGIN / ".codex-plugin" / "plugin.json").exists()
    assert not (DETERMINISTIC / ".codex-plugin" / "plugin.json").exists()


def test_distribution_excludes_external_integrations_and_updater() -> None:
    assert not (PLUGIN / "skills" / "verify-number").exists()
    assert not (PLUGIN / "references" / "contract-receipts.md").exists()
    assert not (PLUGIN / "hooks" / "codex_marketplace_autoupgrade.py").exists()
    assert not (PLUGIN / "hooks" / "session_ledger").exists()
    assert not (PLUGIN / "hooks.json").exists()
    assert "codex_marketplace_autoupgrade.py" not in (
        (PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8")
    )


def test_docs_state_the_safety_boundary() -> None:
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    plugin_readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    install_guide = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")

    assert "MIT-licensed" in root_readme
    assert "MIT License" in license_text
    assert "Do not submit credentials" in root_readme
    assert (
        "no command\nto run or system prompt to paste for matching prompts"
        in root_readme
    )
    assert "LLM Accuracy itself remains stateless" in root_readme
    assert "stale summary after a long session" in root_readme
    assert "Never submit" in contributing
    assert "does not guarantee" in plugin_readme
    assert "stateless evidence-receipt schema and structural validator" in plugin_readme
    assert "certify source truth" in plugin_readme
    assert "No session ledger, prompt history, or tool output" in plugin_readme
    assert "Claude Code terminal or IDE — full plugin" in install_guide
    assert "Claude Desktop Chat — skills-only" in install_guide
    assert (
        "Claude chat on the web — personal marketplace (skills only)" in install_guide
    )
    assert "Add marketplace" in install_guide
    assert "Claude Code on the web — pilot only" in install_guide
    assert "Session Ledger — Claude Code terminal or IDE only" in install_guide
    assert "Deterministic Data — editable template" in install_guide
    assert "own fork or source copy" in install_guide
    assert "exact shipped hook commands" in install_guide
    assert "Authenticated, non-persistent local sessions" in install_guide
    assert install_guide.count("not runtime-smoke-tested for this release") == 2
    assert "initial Desktop 2.110.0 smoke" in install_guide
    assert "A follow-up Cowork smoke" in install_guide
    assert "`latest_complete_month` token" in install_guide
    assert "rebuilt ZIP has not yet been re-tested in Cowork" not in install_guide
    assert "temporary scratchpad receipt write" not in install_guide
    assert (
        "validation/cowork-deterministic-data-smoke-2026-09-16.json"
        in install_guide
    )
    assert "untested and unsupported for this release" in install_guide


def test_cowork_deterministic_data_smoke_receipt_records_final_boundaries() -> None:
    receipt = load_json(
        "docs/validation/cowork-deterministic-data-smoke-2026-09-16.json"
    )

    assert receipt["candidate_head"] == "ef4cc8e153312a231ae584dbd966758968706e2d"
    assert receipt["outcome"] == "PASS"
    assert receipt["session"] == {
        "cli_session_id": "76f5a9ea-90d3-5663-b574-499a7513d776",
        "parse_errors": 0,
        "record_count": 89,
        "transcript_sha256": (
            "3c7efff956752e0a38d4303855150f0d388567559ee4931c7cad22f638e53be0"
        ),
    }
    checks = receipt["checks"]
    assert checks["write_tool_calls"] == 0
    assert checks["prompt_epoch_equals_route_id"] is True
    assert checks["latest_complete_month_preserved"] is True
    assert checks["concrete_calendar_month_named"] is False
    assert checks["canonical_value"] == "withheld"
    assert checks["receipt_validator_exit_code"] == 0
    assert checks["receipt_validator_status"] == "pass"
    assert checks["receipt_validator_errors"] == []
    assert receipt["evidence_boundary"]["raw_content_committed"] is False
