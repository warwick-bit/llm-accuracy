---
name: begin-plan
description: Start a clean Session Ledger plan boundary for unrelated work in the current long Claude Code session.
disable-model-invocation: true
---

Execute this argument vector after substituting the host placeholders:

```json
[
  "${user_config.python_executable}",
  "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py",
  "begin-plan",
  "--plugin-data",
  "${CLAUDE_PLUGIN_DATA}",
  "--session-id",
  "${CLAUDE_SESSION_ID}"
]
```

Use direct execution when available. With a shell tool, quote every element
as a literal for the active shell (PowerShell: `&` before the executable and
single quotes with embedded ASCII/smart single quotes (U+2018–U+201B) doubled; POSIX: shell-escaped single
arguments). Never evaluate substituted text as a complete shell command.
If local execution or a required placeholder is unavailable, report that the
operation could not be confirmed. This skill has no shell preprocessing.

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
