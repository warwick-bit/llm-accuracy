: << 'WINDOWS_LAUNCHER'
@echo off
REM Delayed expansion keeps executable/data values out of cmd syntax parsing.
setlocal EnableDelayedExpansion
set "PYTHONUTF8=1"
set "llm_python_flag="
if defined CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE (
    set "llm_python=!CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE!"
    "!llm_python!" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if errorlevel 1 goto python_unavailable
    goto run_python_hook
)
for %%P in (python3 python py) do (
    set "llm_python=%%P"
    set "llm_python_flag="
    if "%%P"=="py" set "llm_python_flag=-3"
    "!llm_python!" !llm_python_flag! -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
    if not errorlevel 1 goto run_python_hook
)
:python_unavailable
echo {"systemMessage":"Plugin hooks need working Python 3.9+. Install Python or set the optional Python executable in /config. If already set, correct or clear it to use automatic discovery."}
exit /b 0
:run_python_hook
set "llm_hook_action="
for /f "tokens=1,2 delims=:" %%A in ("%~1") do (
    set "llm_hook_target=%%A"
    set "llm_hook_action=%%B"
)
set "llm_runner=!CLAUDE_PLUGIN_ROOT!\hooks\hook_runner.py"
if defined llm_hook_action (
    "!llm_python!" !llm_python_flag! -c "import os,runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name='__main__') if os.path.isfile(p) else None" "!llm_runner!" "!llm_hook_target!" "!llm_hook_action!" --plugin-data "!CLAUDE_PLUGIN_DATA!"
) else (
    "!llm_python!" !llm_python_flag! -c "import os,runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name='__main__') if os.path.isfile(p) else None" "!llm_runner!" "!llm_hook_target!"
)
exit /b !ERRORLEVEL!
WINDOWS_LAUNCHER
# Sourced by sh: the hook command sets $1 because dash ignores dot arguments.
export PYTHONUTF8=1
llm_hook_target=${1%%:*}
llm_hook_action=${1#*:}
llm_probe='import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'
llm_python=${CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE:-}
llm_python_flag=
if [ -n "$llm_python" ]; then
    "$llm_python" -c "$llm_probe" >/dev/null 2>&1 || llm_python=
else
    for llm_candidate in python3 python py; do
        llm_candidate_flag=
        [ "$llm_candidate" != py ] || llm_candidate_flag=-3
        if "$llm_candidate" $llm_candidate_flag -c "$llm_probe" >/dev/null 2>&1; then
            llm_python=$llm_candidate
            llm_python_flag=$llm_candidate_flag
            break
        fi
    done
fi
if [ -z "$llm_python" ]; then
    printf '%s\n' '{"systemMessage":"Plugin hooks need working Python 3.9+. Install Python or set the optional Python executable in /config. If already set, correct or clear it to use automatic discovery."}'
    return 0
fi
if [ "$llm_hook_action" = "$1" ]; then
    set -- "$llm_hook_target"
else
    set -- "$llm_hook_target" "$llm_hook_action" --plugin-data "${CLAUDE_PLUGIN_DATA:-}"
fi
exec "$llm_python" $llm_python_flag -c 'import os,runpy,sys; p=sys.argv.pop(1); runpy.run_path(p,run_name="__main__") if os.path.isfile(p) else None' "$CLAUDE_PLUGIN_ROOT/hooks/hook_runner.py" "$@"
