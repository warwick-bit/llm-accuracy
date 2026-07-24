---
name: begin-plan
description: Start a clean Session Ledger plan boundary for unrelated work in the current long Claude Code session.
disable-model-invocation: true
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py" begin-plan --session-id "${CLAUDE_SESSION_ID}" --plugin-data "${CLAUDE_PLUGIN_DATA}"`

Use this only when you deliberately begin unrelated work in the current session.
Starting a plan boundary permanently discards the ledger record captured so far
in this session. It does not store a plan name and does not carry ledger data to
another session.

Report a new boundary only if the command printed `Started a fresh Session
Ledger plan boundary`. On any other output — including no output at all — tell
the user the boundary could not be confirmed and that the previous ledger
record may still be active; do not claim the boundary started.
