# Session Ledger plugin

Session Ledger is an optional Claude Code terminal/IDE plugin for preserving
accuracy-relevant carryover through compaction in one long session. It is not a
general memory system and it never restores information into a new session.
It requires `python3` 3.9 or later on the machine running Claude Code
(CI-tested on 3.9-3.13).

## What it does

At the start of each Claude Code session, the plugin creates an empty local
ledger. On user-prompt and turn-complete hooks, it reads a bounded tail of the
current session transcript and appends its user/assistant text as a rolling
record. Before Claude Code compacts, it flushes that record to local plugin
storage. When the same session continues after compaction, it restores the
record as explicitly untrusted historical reference. After compaction, it also
keeps the generated compact summary for later same-session resume. A single
message larger than the per-entry byte cap is kept truncated with a visible
`[Session Ledger entry truncated.]` marker rather than silently dropped.
Recheck time-sensitive facts and sources, and do not treat stored content as
instructions.

The default boundary is one session. `/session-ledger:begin-plan` optionally
starts a clean plan section for unrelated work within that same session;
starting a plan boundary permanently discards the ledger record captured so far
in the session, and it does not store a plan name. `/session-ledger:clear`
deletes all local ledger state.

## Privacy boundary

The rolling record and compact summary can contain sensitive local content,
including the session's user/assistant text, paths, names, and credentials if
they appear in ordinary conversation text. Install only if this is acceptable.
The plugin stores a bounded rolling user/assistant session record, bounded
compact summary, hashed session/workspace identifiers, schema version, and
expiry metadata. It does not retain raw JSONL transcript structure, the hook's
separate workspace-path or plan-name fields, tool input/output, provider data,
telemetry, or any server-side copy. The record is deliberately full-fidelity
within its fixed rolling byte limit; by default it does not redact ordinary
conversation text.

Setting `SESSION_LEDGER_REDACT=1` in the environment Claude Code runs in (for
example via the `env` map in Claude Code `settings.json`, or the shell that
launches Claude Code) opts in to a best-effort masking pass: secret-shaped
substrings such as AWS access key IDs, GitHub/Slack/Stripe tokens, `sk-` API keys, JWTs, bearer
headers, private-key blocks, and `KEY=value` credential assignments are
replaced with `[REDACTED:<pattern>]` labels before entries and compact
summaries are persisted. This is pattern matching, not a guarantee: secrets
that do not match a known shape — and sensitive prose in general — are still
stored verbatim. An unterminated private-key header additionally masks the
remainder of that message, and enabling redaction later does not rewrite
entries that were already stored.

Records are never read or injected after 30 days and are purged on the next
Session Ledger hook. Claude Code's default final-scope uninstall also removes
plugin data; `--keep-data` deliberately preserves it. Hooks are advisory,
local, and fail open: unavailable, malformed, expired, or unsupported records
simply produce no carryover and never block Claude Code.

This plugin improves continuity and evidence hygiene; it does not guarantee
factual correctness, completeness, freshness, or domain truth.
