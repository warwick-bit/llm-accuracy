---
name: begin-plan
description: Start a clean Session Ledger plan boundary for unrelated work in the current long Claude Code session.
disable-model-invocation: true
---

!`if command -v python3 >/dev/null 2>&1; then PLUGIN_PYTHON=python3; else PLUGIN_PYTHON=python; fi; "$PLUGIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py" begin-plan --session-id "${CLAUDE_SESSION_ID}" --plugin-data "${CLAUDE_PLUGIN_DATA}"`

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
