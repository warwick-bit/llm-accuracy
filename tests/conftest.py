"""Hook tests use the host POSIX shell, including explicit Git Bash on Windows."""

import copy
import inspect
import os
import sys
import shlex
import subprocess
from pathlib import Path

import pytest

HOOK_SHELL = os.environ.get("HOOK_TEST_SHELL", "/bin/sh" if os.name == "posix" else "")


def symlink_or_skip(link, target, *, target_is_directory=False):
    """Exercise real symlinks wherever the current Windows token permits them."""
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink creation requires Developer Mode or symlink privilege")
        raise


@pytest.fixture(autouse=True)
def hide_windows_test_children(monkeypatch):
    """Noninteractive test children must never open a console window."""
    if os.name != "nt":
        return
    real_init = subprocess.Popen.__init__
    signature = inspect.signature(real_init)

    def hidden_init(*args, **kwargs):
        call = signature.bind(*args, **kwargs)
        startupinfo = call.arguments.get("startupinfo")
        startupinfo = copy.copy(startupinfo) if startupinfo is not None else subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        call.arguments["startupinfo"] = startupinfo
        call.arguments["creationflags"] = call.arguments.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        return real_init(*call.args, **call.kwargs)

    # Keep Popen a class: asyncio.windows_utils subclasses it on import.
    monkeypatch.setattr(subprocess.Popen, "__init__", hidden_init)


def fidelity_responses(prompt):
    """Claim-fidelity hook responses a one-turn default-mode session receives."""
    import importlib.util
    path = Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/hooks/claim-fidelity-trigger.py"
    spec = importlib.util.spec_from_file_location("claim_fidelity_trigger", path)
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    # Match the host probe's evidence-label count. A Clarify-only prompt response
    # is a separate reminder, not another full claim-fidelity response.
    return sum("CLAIM FIDELITY CHECK" in context for context in (
        hook.context_for_session("session"), hook.context_for_prompt(prompt, "session"),
    ))


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
        # The prefix below uses PowerShell syntax; an ambient Claude Bash
        # preference must not override this test's selected shell.
        env.pop('CLAUDE_CODE_GIT_BASH_PATH', None)
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
