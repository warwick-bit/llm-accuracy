"""Hook tests use the host POSIX shell, including explicit Git Bash on Windows."""

import os
import sys
import shlex
from pathlib import Path

import pytest

HOOK_SHELL = os.environ.get("HOOK_TEST_SHELL", "/bin/sh" if os.name == "posix" else "")


def fidelity_responses(prompt):
    """Claim-fidelity hook responses a one-turn default-mode session receives."""
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/hooks/claim-fidelity-trigger.py"
    spec = importlib.util.spec_from_file_location("claim_fidelity_trigger", path)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return bool(hook.context_for_session("session")) + bool(hook.context_for_prompt(prompt, "session"))


def hook_argv(handler, root, data="", executable=None):
    """Export synthetic host values, preserving the shipped shell command."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    from hook_command import shell_argv
    values = {"CLAUDE_PLUGIN_ROOT": str(root), "CLAUDE_PLUGIN_DATA": str(data),
              "CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE": executable or sys.executable}
    command = handler['command']
    env = dict(os.environ, HOOK_TEST_SHELL=HOOK_SHELL)
    powershell = os.name == 'nt' and not HOOK_SHELL
    if powershell:
        def quote(value):
            for character in ("'", '\u2018', '\u2019', '\u201a', '\u201b'):
                value = value.replace(character, character * 2)
            return "'" + value + "'"
        prefix = '; '.join('$env:' + key + '=' + quote(value) for key, value in values.items())
    else:
        prefix = '; '.join('export ' + key + '=' + shlex.quote(value) for key, value in values.items())
    return shell_argv(prefix + '; ' + command, env, test_shell=True)


@pytest.fixture(autouse=True)
def isolate_accuracy_configuration(monkeypatch, tmp_path):
    """Dynamic hook imports use sibling modules and never the user's config."""
    hooks = Path(__file__).resolve().parents[1] / "plugins" / "llm-accuracy" / "hooks"
    monkeypatch.syspath_prepend(str(hooks))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude-profile"))
    monkeypatch.delenv("LLM_ACCURACY_CONFIG", raising=False)
    monkeypatch.delenv("CC_CLAIM_FIDELITY_MODE", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_CLAIM_FIDELITY_MODE", raising=False)
