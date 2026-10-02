---
name: clear
description: Permanently delete all locally stored Session Ledger state.
disable-model-invocation: true
---

Run the configured Python executable (`${user_config.python_executable}`)
with `${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py`, the clear action,
`--plugin-data` and `${CLAUDE_PLUGIN_DATA}`. For `begin-plan`, also pass
`--session-id` and `${CLAUDE_SESSION_ID}`. Use an argument vector when available;
otherwise quote each value as a literal for the active shell (PowerShell: single
quotes with embedded apostrophes doubled; POSIX: shell-escaped single arguments).
Never execute the substituted text as a complete shell command. If local
execution or any placeholder is unavailable, report that the operation could
not be confirmed. This skill does not run a shell during preprocessing.

Report deletion only if the command says `Cleared local Session Ledger state.`
If it cannot confirm deletion — or prints nothing at all — tell the user that
local state may remain and do not claim it was removed.
