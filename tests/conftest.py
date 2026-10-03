"""Hook tests use the host POSIX shell, including explicit Git Bash on Windows."""

import os
import sys
from pathlib import Path

import pytest

HOOK_SHELL = os.environ.get("HOOK_TEST_SHELL", "/bin/sh" if os.name == "posix" else "")


def hook_argv(handler, root, data="", executable=None):
    """Apply the documented exec-form substitutions without involving a shell."""
    values = {"CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PLUGIN_DATA": str(data),
              "user_config.python_executable": executable or sys.executable}

    def expand(value):
        for key, replacement in values.items():
            value = value.replace("${" + key + "}", replacement)
        assert "${" not in value
        return value

    assert isinstance(handler["args"], list)
    return [expand(handler["command"]), *map(expand, handler["args"])]


@pytest.fixture(autouse=True)
def isolate_accuracy_configuration(monkeypatch, tmp_path):
    """Dynamic hook imports use sibling modules and never the user's config."""
    hooks = Path(__file__).resolve().parents[1] / "plugins" / "llm-accuracy" / "hooks"
    monkeypatch.syspath_prepend(str(hooks))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-profile"))
    monkeypatch.delenv("LLM_ACCURACY_CONFIG", raising=False)
    monkeypatch.delenv("CC_CLAIM_FIDELITY_MODE", raising=False)
