---
name: clear
description: Permanently delete all locally stored Session Ledger state.
disable-model-invocation: true
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py" clear --plugin-data "${CLAUDE_PLUGIN_DATA}"`

Report deletion only if the command says `Cleared local Session Ledger state.`
If it cannot confirm deletion — or prints nothing at all — tell the user that
local state may remain and do not claim it was removed.
