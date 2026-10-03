"""Construct the platform shell vector without interpolating paths into code."""

import os
import shutil


def shell_argv(command: str, env: dict, *, test_shell: bool = False) -> list[str]:
    if os.name != 'nt':
        return [(env.get('HOOK_TEST_SHELL') if test_shell else None) or '/bin/sh', '-c', command]
    bash = (env.get('HOOK_TEST_SHELL') if test_shell else None) or env.get('CLAUDE_CODE_GIT_BASH_PATH')
    if bash:
        return [bash, '-c', command]
    shell = shutil.which('pwsh', path=env.get('PATH')) or shutil.which('powershell', path=env.get('PATH'))
    if not shell:
        raise ValueError('hook_shell_unavailable')
    command = command.replace('${CLAUDE_PLUGIN_ROOT}', '${env:CLAUDE_PLUGIN_ROOT}')
    return [shell, '-NoProfile', '-NonInteractive', '-Command', command]
