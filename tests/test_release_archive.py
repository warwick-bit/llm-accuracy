"""Checks for the uploadable Claude Desktop and Cowork release archive."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
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
    source_manifest = json.loads(
        (ROOT / "plugins/llm-accuracy/.claude-plugin/plugin.json").read_text()
    )
    assert manifest["version"] == source_manifest["version"]
    assert "LICENSE.md" in names
    assert "hooks/hooks.json" in names
    assert "hooks/accuracy_config.py" in names
    assert "hooks/builtin_result_signals.py" in names
    assert "scripts/accuracy_doctor.py" in names
    assert "scripts/host_probe.py" in names
    assert "skills/accuracy-doctor/SKILL.md" in names
    assert "skills/verify-technical/SKILL.md" in names
    assert "skills/self-audit/SKILL.md" in names
    assert not any(name.startswith("plugins/") for name in names)
    assert not any("__pycache__" in name for name in names)


def test_deterministic_data_archive_is_independent(tmp_path: Path) -> None:
    builder = load_builder()
    plugin = ROOT / "plugins" / "deterministic-data"
    output = builder.build_archive(tmp_path / "deterministic-data.zip", plugin=plugin)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read(".claude-plugin/plugin.json"))

    assert manifest["name"] == "deterministic-data"
    assert manifest["version"] == "0.1.0"
    assert "catalogues/example.catalogue.json" in names
    assert "skills/data-routing/SKILL.md" in names
    assert "references/evidence-receipt.schema.json" in names
    assert not any(name.startswith("plugins/") for name in names)


def test_deterministic_data_cli_uses_manifest_version(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    builder = load_builder()
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_plugin_zip.py", "--plugin", "deterministic-data"],
    )

    assert builder.main() == 0
    output = Path(capsys.readouterr().out.strip())
    assert output == tmp_path / "dist" / "deterministic-data-0.1.0.zip"
    assert output.is_file()


def test_release_archive_rejects_external_symlink(tmp_path: Path) -> None:
    builder = load_builder()
    plugin = tmp_path / "plugin"
    plugin.mkdir()
    outside = tmp_path.parent / "outside-release-artifact.md"
    outside.write_text("private source", encoding="utf-8")
    (plugin / "linked.md").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink artifact: linked.md"):
        builder.build_archive(tmp_path / "llm-accuracy.zip", plugin=plugin)


def tracked_test_plugin(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    plugin = repository / "plugins" / "llm-accuracy"
    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
    (plugin / "README.md").write_text("tracked source", encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.name", "Test User"], check=True
    )
    subprocess.run(["git", "-C", str(repository), "add", "plugins"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "commit", "-qm", "fixture"], check=True
    )
    return plugin


def test_release_archive_omits_untracked_plugin_files(tmp_path: Path) -> None:
    builder = load_builder()
    plugin = tracked_test_plugin(tmp_path)
    (plugin / "untracked-release-note.md").write_text("do not ship", encoding="utf-8")

    archive_path = builder.build_archive(tmp_path / "llm-accuracy.zip", plugin=plugin)
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())

    assert "README.md" in names
    assert "untracked-release-note.md" not in names


def test_release_archive_rejects_uncommitted_tracked_changes(tmp_path: Path) -> None:
    builder = load_builder()
    plugin = tracked_test_plugin(tmp_path)
    (plugin / "README.md").write_text("uncommitted change", encoding="utf-8")

    with pytest.raises(ValueError, match="plugin source has uncommitted changes"):
        builder.build_archive(tmp_path / "llm-accuracy.zip", plugin=plugin)


@pytest.mark.parametrize("failure", ["validation", "write", "replace"])
def test_failed_archive_build_preserves_prior_output_and_cleans_temp(
    tmp_path, monkeypatch, failure
):
    builder = load_builder()
    plugin = tracked_test_plugin(tmp_path)
    output = tmp_path / "previous.zip"
    builder.build_archive(output, plugin=plugin)
    previous = output.read_bytes()
    if failure == "validation":
        (plugin / "README.md").write_text("synthetic dirty change", encoding="utf-8")
        error = ValueError
    elif failure == "write":
        def fail_write(*args, **kwargs):
            raise OSError("Synthetic write failure")
        monkeypatch.setattr(builder.zipfile.ZipFile, "write", fail_write)
        error = OSError
    else:
        def fail_replace(*args, **kwargs):
            raise OSError("Synthetic replacement failure")
        monkeypatch.setattr(Path, "replace", fail_replace)
        error = OSError
    with pytest.raises(error):
        builder.build_archive(output, plugin=plugin)
    assert output.read_bytes() == previous
    assert sorted(path.name for path in tmp_path.iterdir()) == ["previous.zip", "source"]


def test_successful_archive_replaces_previous_output(tmp_path):
    builder = load_builder()
    plugin = tracked_test_plugin(tmp_path)
    output = tmp_path / "previous.zip"
    output.write_bytes(b"synthetic previous artifact")
    assert builder.build_archive(output, plugin=plugin) == output
    with zipfile.ZipFile(output) as archive:
        assert archive.read("README.md") == b"tracked source"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["previous.zip", "source"]
