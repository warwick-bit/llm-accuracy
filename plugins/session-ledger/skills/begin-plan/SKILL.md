---
name: begin-plan
description: Start a clean Session Ledger plan boundary for unrelated work in the current long Claude Code session.
disable-model-invocation: true
---

!`python3 "${CLAUDE_PLUGIN_ROOT}/hooks/session-ledger.py" begin-plan --session-id "${CLAUDE_SESSION_ID}"`

Use this only when you deliberately begin unrelated work in the current session.
It does not store a plan name and does not carry ledger data to another session.
