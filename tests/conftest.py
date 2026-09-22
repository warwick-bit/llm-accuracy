"""Hook tests use the host POSIX shell, including explicit Git Bash on Windows."""

import os
from pathlib import Path

import pytest

HOOK_SHELL = os.environ.get("HOOK_TEST_SHELL", "/bin/sh" if os.name == "posix" else "")


@pytest.fixture(autouse=True)
def isolate_accuracy_configuration(monkeypatch, tmp_path):
    """Dynamic hook imports use sibling modules and never the user's config."""
    hooks = Path(__file__).resolve().parents[1] / "plugins" / "llm-accuracy" / "hooks"
    monkeypatch.syspath_prepend(str(hooks))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-profile"))
    monkeypatch.delenv("LLM_ACCURACY_CONFIG", raising=False)
    monkeypatch.delenv("CC_CLAIM_FIDELITY_MODE", raising=False)
