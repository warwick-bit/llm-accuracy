"""Checks for the uploadable Claude Desktop and Cowork release archive."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_builder() -> ModuleType:
    path = ROOT / "scripts" / "build_plugin_zip.py"
    spec = importlib.util.spec_from_file_location("build_plugin_zip", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_archive_has_plugin_root_contents_only(tmp_path: Path) -> None:
    builder = load_builder()
    output = builder.build_archive(tmp_path / "llm-accuracy.zip")

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read(".claude-plugin/plugin.json"))

    assert manifest["name"] == "llm-accuracy"
    assert manifest["version"] == "0.3.0"
    assert "hooks/hooks.json" in names
    assert "skills/self-audit/SKILL.md" in names
    assert not any(name.startswith("plugins/") for name in names)
    assert not any("__pycache__" in name for name in names)


def test_release_archive_rejects_external_symlink(tmp_path: Path) -> None:
    builder = load_builder()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    outside = tmp_path.parent / "outside-release-artifact.md"
    outside.write_text("private source", encoding="utf-8")
    (plugin / "linked.md").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink artifact: linked.md"):
        builder.build_archive(tmp_path / "llm-accuracy.zip", plugin=plugin)


def test_release_archive_omits_untracked_plugin_files(tmp_path: Path) -> None:
    builder = load_builder()
    repository = tmp_path / "source"
    plugin = repository / "plugins" / "llm-accuracy"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (plugin / "README.md").write_text("tracked source", encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "plugins"], check=True)
    (plugin / "untracked-release-note.md").write_text("do not ship", encoding="utf-8")

    archive_path = builder.build_archive(tmp_path / "llm-accuracy.zip", plugin=plugin)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "README.md" in names
    assert "untracked-release-note.md" not in names
