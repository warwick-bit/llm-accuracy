"""Direct installed-hook probes must prove behavior, including silent failures."""

import importlib
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
probe = importlib.import_module("installed_hook_probe")


@pytest.fixture
def installed(tmp_path):
    copies = {}
    for name in ("llm-accuracy", "session-ledger", "evidence-memory"):
        target = tmp_path / "installed O'Brien é" / name
        shutil.copytree(
            ROOT / "plugins" / name,
            target,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        copies[name] = target
    return copies


def environment():
    # A failed assertion must never render inherited service credentials.
    names = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR")
    return {key: os.environ[key] for key in names if key in os.environ}


def test_installed_vectors_emit_accuracy_restore_ledger_and_capture_memory_once(
    installed, tmp_path
):
    assert probe.run(
        installed, tmp_path, dict.fromkeys(installed, sys.executable), environment()
    )


def test_unconfigured_launchers_execute_all_hook_plugins(installed, tmp_path):
    assert probe.run(installed, tmp_path, dict.fromkeys(installed, ''), environment())


@pytest.mark.parametrize("name", ["llm-accuracy", "session-ledger"])
def test_missing_runner_cannot_silently_certify_installed_hook_execution(
    installed, tmp_path, name
):
    (installed[name] / "hooks/hook_runner.py").unlink()
    assert (
        probe.run(
            installed, tmp_path, dict.fromkeys(installed, sys.executable), environment()
        )
        is False
    )


def test_missing_memory_runner_cannot_silently_certify_persistence(installed, tmp_path):
    (installed["evidence-memory"] / "hooks/hook_runner.py").unlink()
    with pytest.raises(ValueError, match="installed_hook_probe_failed"):
        probe.run(
            installed, tmp_path, dict.fromkeys(installed, sys.executable), environment()
        )


def test_duplicate_initial_capture_cannot_certify_exactly_once(
    installed, tmp_path, monkeypatch
):
    original = probe.memory_cli

    def duplicate_count(*arguments):
        result = original(*arguments)
        if "events" in result:
            result["events"] += 1
        return result

    monkeypatch.setattr(probe, "memory_cli", duplicate_count)
    assert not probe.memory_probe(
        installed["evidence-memory"], tmp_path, sys.executable, environment()
    )
