# Evidence Memory 0.1.0 (experimental)

Evidence Memory is a separate Claude Code plugin for current-session tool-call
and result retrieval after compaction. Installing it does not install or enable
Session Ledger. The plugin and capture are both off by default: after
installation, enable the plugin in `/plugin`, restart, then use
`/evidence-memory:memory enable` in each session where capture is wanted.

Exact logged results may contain credentials or other sensitive data. Storage
is local, scoped to the current session and plan, expires after 30 days of
inactivity, and stops new writes at a retryable cursor when its 128 MiB database
cap is reached. `disable`, `begin-plan`, and `clear` delete this plugin's
evidence and state; a cutoff prevents reindexing earlier rows on re-enable.

See the [install guide](INSTALL.md), [plugin guide](../plugins/evidence-memory/README.md),
and [validation receipt](validation/evidence-memory-standalone-2026-09-25.json).
Synthetic retrieval tests supported exact recovery after simulated compaction,
but no live long-session accuracy or token-saving uplift has been measured.
