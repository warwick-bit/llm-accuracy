"""Fast checks for the private-preview distribution boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "llm-accuracy"


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_claude_plugin_manifest_identifies_the_preview() -> None:
    claude = load_json("plugins/llm-accuracy/.claude-plugin/plugin.json")

    assert claude["name"] == "llm-accuracy"
    assert claude["version"] == "0.3.0"
    assert "codex" not in str(claude).lower()


def test_claude_marketplace_publishes_only_the_preview_plugin() -> None:
    claude = load_json(".claude-plugin/marketplace.json")

    assert [entry["name"] for entry in claude["plugins"]] == ["llm-accuracy"]


def test_preview_contains_no_codex_runtime_package() -> None:
    assert not (ROOT / ".agents" / "plugins" / "marketplace.json").exists()
    assert not (PLUGIN / ".codex-plugin" / "plugin.json").exists()


def test_preview_excludes_external_integrations_and_updater() -> None:
    assert not (PLUGIN / "skills" / "verify-number").exists()
    assert not (PLUGIN / "references" / "contract-receipts.md").exists()
    assert not (PLUGIN / "hooks" / "codex_marketplace_autoupgrade.py").exists()
    assert not (PLUGIN / "hooks" / "session_ledger").exists()
    assert "codex_marketplace_autoupgrade.py" not in (
        (PLUGIN / "hooks.json").read_text(encoding="utf-8")
    )


def test_preview_docs_state_the_safety_boundary() -> None:
    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    preview = (ROOT / "PREVIEW.md").read_text(encoding="utf-8")
    plugin_readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    install_guide = (ROOT / "docs" / "INSTALL.md").read_text(encoding="utf-8")

    assert "not open source" in root_readme.lower()
    assert "Do not submit credentials" in root_readme
    assert "no command\nto run or system prompt to paste for matching prompts" in root_readme
    assert "No session ledger is" in root_readme
    assert "stale summary after a long session" in root_readme
    assert "Never submit" in preview
    assert "does not guarantee" in plugin_readme
    assert "No session ledger, prompt history, or tool output" in plugin_readme
    assert "Claude Code terminal or IDE — full preview" in install_guide
    assert "Claude Desktop Chat — skills-only" in install_guide
    assert "Claude Code on the web — pilot only" in install_guide
