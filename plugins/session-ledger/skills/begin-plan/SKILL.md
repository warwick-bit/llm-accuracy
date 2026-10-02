---
name: begin-plan
description: Start a clean Session Ledger plan boundary for unrelated work in the current long Claude Code session.
disable-model-invocation: true
---

Run the configured Python executable (`${user_config.python_executable}`)
with `${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py`, the begin-plan action,
`--plugin-data` and `${CLAUDE_PLUGIN_DATA}`. For `begin-plan`, also pass
`--session-id` and `${CLAUDE_SESSION_ID}`. Use an argument vector when available;
otherwise quote each value as a literal for the active shell (PowerShell: single
quotes with embedded apostrophes doubled; POSIX: shell-escaped single arguments).
Never execute the substituted text as a complete shell command. If local
execution or any placeholder is unavailable, report that the operation could
not be confirmed. This skill does not run a shell during preprocessing.

Use this only when you deliberately begin unrelated work in the current session.
Starting a plan boundary discards the stored ledger record and excludes earlier
transcript rows using a timestamp cutoff. It does not clear Claude's conversation:
later replies or compact summaries can restate prior material. Use a new session
for conversation isolation. The boundary stores no plan name and never carries
ledger data into a different session.

Report a new boundary only if the command printed `Started a fresh Session
Ledger plan boundary`. On any other output — including no output at all — tell
the user the boundary could not be confirmed and that the previous ledger
record may still be active; do not claim the boundary started.
