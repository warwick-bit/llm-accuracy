---
name: clear
description: Permanently delete all locally stored Session Ledger state.
disable-model-invocation: true
---

Execute this argument vector after substituting the host placeholders:

```json
[
  "${user_config.python_executable}",
  "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py",
  "clear",
  "--plugin-data",
  "${CLAUDE_PLUGIN_DATA}"
]
```

Use direct execution when available. With a shell tool, quote every element
as a literal for the active shell (PowerShell: `&` before the executable and
single quotes with embedded apostrophes doubled; POSIX: shell-escaped single
arguments). Never evaluate substituted text as a complete shell command.
If local execution or a required placeholder is unavailable, report that the
operation could not be confirmed. This skill has no shell preprocessing.

Report deletion only if the command says `Cleared local Session Ledger state.`
If it cannot confirm deletion — or prints nothing at all — tell the user that
local state may remain and do not claim it was removed.
