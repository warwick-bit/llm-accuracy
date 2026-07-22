#!/usr/bin/env python3
"""Build the uploadable Claude Desktop and Cowork plugin archive."""

from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from pathlib import Path

try:
    from scripts.check_private_preview_boundary import boundary_violations
except ModuleNotFoundError:  # Direct script execution puts scripts/ on sys.path.
    from check_private_preview_boundary import boundary_violations


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "llm-accuracy"
IGNORED_PARTS = frozenset({"__pycache__"})
IGNORED_SUFFIXES = frozenset({".pyc", ".pyo"})


def plugin_version(plugin: Path = PLUGIN) -> str:
    """Return the declared plugin version from its Claude manifest."""
    manifest = plugin / ".claude-plugin" / "plugin.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    version = payload.get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("plugin manifest must declare a non-empty version")
    return version


def repository_root(plugin: Path) -> Path:
    """Return the Git worktree that owns the plugin source."""
    result = subprocess.run(
        ["git", "-C", str(plugin), "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode:
        raise ValueError("plugin source must be inside a Git worktree")
    return Path(result.stdout.strip())


def tracked_plugin_files(plugin: Path) -> list[Path]:
    """Return the Git-tracked files rooted at the plugin source."""
    repository = repository_root(plugin)
    try:
        relative_plugin = plugin.relative_to(repository)
    except ValueError as error:
        raise ValueError("plugin source must be inside its Git worktree") from error
    for diff_args in (("diff",), ("diff", "--cached")):
        result = subprocess.run(
            ["git", "-C", str(repository), *diff_args, "--quiet", "--", relative_plugin.as_posix()],
            check=False,
        )
        if result.returncode:
            raise ValueError("plugin source has uncommitted changes")
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "ls-files",
            "--cached",
            "-z",
            "--",
            relative_plugin.as_posix(),
        ],
        capture_output=True,
        check=True,
    )
    return sorted(
        repository / Path(relative_path)
        for relative_path in result.stdout.decode().split("\0")
        if relative_path
    )


def archive_members(plugin: Path = PLUGIN) -> list[Path]:
    """Return deterministic, preview-safe tracked files for the release archive."""
    violations = boundary_violations(plugin)
    if violations:
        raise ValueError("private-preview boundary check failed: " + "; ".join(violations))
    return [
        path
        for path in tracked_plugin_files(plugin)
        if path.is_file()
        and not (IGNORED_PARTS & set(path.relative_to(plugin).parts))
        and path.suffix.lower() not in IGNORED_SUFFIXES
    ]


def build_archive(output: Path, plugin: Path = PLUGIN) -> Path:
    """Write an uploadable archive whose root is the plugin root."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in archive_members(plugin):
            archive.write(path, path.relative_to(plugin).as_posix())
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        help="Archive destination (defaults to dist/llm-accuracy-<version>.zip).",
    )
    args = parser.parse_args()
    output = args.output or ROOT / "dist" / f"llm-accuracy-{plugin_version()}.zip"
    print(build_archive(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
