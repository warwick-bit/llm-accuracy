# Session Ledger plugin

Session Ledger is an optional Claude Code terminal/IDE plugin for preserving
accuracy-relevant carryover through compaction in one long session. It is not a
general memory system and it never restores information into a new session.
It requires Claude Code 2.1.78 or later: `PostCompact` was added in 2.1.76
and `${CLAUDE_PLUGIN_DATA}` in 2.1.78. Use a current Claude Code release;
the live Windows smoke test for this release used 2.1.281. See the
[Claude Code changelog](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md).

It also requires Python 3.9 or later, available as `python3` or `python`, on the machine running Claude Code
(CI-tested on 3.9-3.13). Hooks and ledger commands prefer `python3` and fall back
to `python` when that command is absent. Windows requires a POSIX-compatible
hook shell such as Git Bash.

## Install and enable

In Claude Code, run these commands separately:

```text
/plugin marketplace add warwick-bit/llm-accuracy
/plugin install session-ledger@llm-accuracy
/plugin enable session-ledger@llm-accuracy
```

The plugin is deliberately disabled by default because it persists local
conversation text. Installing it alone does not confirm that its hooks run.
Open `/plugin`, show disabled plugins if needed, enable Session Ledger, and
check that the Errors tab is empty. Then exit and start a new Claude Code
session. After updating Claude Code itself, check the new session's version;
an already-open process continues to use its previous version.

For an existing installation, run these commands in your terminal, outside
Claude Code, to refresh the marketplace and update the plugin:

```sh
claude plugin marketplace update llm-accuracy
claude plugin update session-ledger@llm-accuracy
```

Confirm version 0.2.6 or later and the enabled state in `/plugin`, then restart
Claude Code. This production plugin is separate from any temporary QA plugin;
close the QA launcher and use your normal Claude Code launch for everyday work.

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

For untruncated entries, duplicate suppression recognises matching text and
narrowly supported host wrappers; added correction or source-withdrawal text
is retained as a separate entry. Unrecognised renderings may remain duplicated.
Truncated entries still use a retained-prefix match. This is not semantic
correction resolution: older statements and summaries may still be present,
and fixed byte limits can omit earlier context or truncate a long message.

The default boundary is one session. `/session-ledger:begin-plan` optionally
starts a clean plan section for unrelated work within that same session;
starting a plan boundary discards the ledger record captured so far and records
a timestamp cutoff for subsequent transcript capture, without a plan name. `/session-ledger:clear`
deletes all local ledger state.

Shell directory changes do not reset or disable the ledger. The first captured
workspace hash is reused for the same session and plan, including after `cd`,
compaction, and resume. Existing unexpired records remain readable without a
migration. An explicit plan marker takes precedence over a prior record, so a
partially failed reset cannot directly restore the stale stored record. New
session IDs never inherit this record. `/session-ledger:begin-plan` remains the deliberate way to
discard earlier work within a session. This is a same-session boundary, not
workspace isolation: starting in one project and navigating to another retains
both projects' conversation in that session.

After an explicit reset, transcript rows at or before the cutoff are excluded.
Undated rows are skipped with a fixed warning because their plan cannot be
established. Legacy plan markers without a cutoff skip transcript history until
a new plan is started; current hook-provided text remains eligible. Scope expiry
refreshes preserve the original cutoff. The cutoff adds one local timestamp to
the plan marker, not a transcript copy.

A ledger reset does **not** clear Claude's conversation or establish a privacy
boundary. Later model replies, current hook text, or host compact summaries can
restate old material and will still be captured as untrusted reference. Use a
new Claude session when conversation isolation is required.

Host summary copies marked `isCompactSummary: true` are excluded from new
transcript capture. Records marked `isMeta: true` are excluded only when their
entire text is a recognised `local-command-caveat`, `local-command-stdout`, or
`task-notification` envelope. Mixed prose and unknown metadata remain eligible.
Compact summaries are still kept separately through `PostCompact`. Unmarked command
output and task notifications remain eligible: text that resembles a host
wrapper can also be a genuine user message, so text alone never triggers
exclusion. Existing stored entries without origin metadata are not retroactively
removed; ordinary retention limits and explicit clear/reset still apply.

## Capture and retention warnings

Successful captures stay quiet. Hooks emit a short `systemMessage` when capture
is skipped for missing identity/data directory or locking
failure; when a storage/internal error prevents confirming an update; or when
rolling entries, a compact summary, or restored context are shortened. A rolling
limit warning can mean omission as well as shortening. The rolling entries have
an aggregate 64 KiB budget (JSON-escaped bytes) and a 16 KiB per-entry cap;
compact summaries have a separate 32 KiB budget. Long sessions therefore retain
only a bounded portion of earlier conversation. A restore warning does not mean
the stored record was changed.

Transcript history is reconciled in its observed order before applying the
budget, so previously evicted messages are not appended as though they were
newest. Hook-only entries missing from the transcript stay between their shared
anchors, preserving interleaved corrections. First-capture backfill is bounded
after reconciliation; it is not skipped merely because the latest hook was
already saved. A replaced transcript with no overlap is appended as new input.
Actual new trimming still warns; unchanged replay stays quiet. No additional
state files, cursor fields, or migration are required.

Warnings contain fixed text only, never transcript content, file paths, or
exception details. They are deduplicated within each invocation, not across
turns, and are not stored in a separate diagnostics file. They never block a
turn. A compact/resume with no valid record reports that restore was skipped;
a directory change alone is not a failure. Warnings cannot report hooks that never run or a process killed before
it emits output. Malformed hook JSON is still ignored.

Claude Code's [hook output contract](https://code.claude.com/docs/en/hooks#json-output)
supports these warnings on ordinary prompt, turn-end, and session-start hooks.
Its compaction hooks discard `systemMessage`, so pre/post-compaction-only warnings
are not guaranteed to appear in the UI. The plugin does not queue them for a
later turn. Client versions can differ in how warnings are displayed.

## Concurrent updates

Same-session updates hold an operating-system file lock across the full read,
merge, and atomic replacement. POSIX uses `flock`; Windows uses a one-byte
`msvcrt` lock with a one-second wait limit. If locking fails or times out, the
hook skips that update and continues without writing unlocked state. Later
transcript capture may recover skipped text, but recovery is not guaranteed.
Locks are released when the descriptor or process closes. This does not change
the rolling byte limits or make explicit clear/plan-boundary actions lossless.

## Privacy boundary

The rolling record and compact summary can contain sensitive local content,
including the session's user/assistant text, paths, names, and credentials if
they appear in ordinary conversation text. Install only if this is acceptable.
The plugin stores a bounded rolling user/assistant session record, bounded
compact summary, hashed session/workspace identifiers, schema version, and
expiry metadata. It does not retain raw JSONL transcript structure, the hook's
separate workspace-path or plan-name fields, telemetry, or any server-side copy.
Tool input/output is not retained unless experimental memory is explicitly
enabled (see below). That mode can retain sensitive provider data locally. The record is deliberately full-fidelity
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
remainder of that message. Enabling redaction later also
masks previously stored text whenever the record is re-injected or
re-persisted; raw text already on disk is rewritten the next time the record
changes.

The restored context injected after compaction is additionally bounded to fit
Claude Code's hook-output limit: when the stored record renders larger than
that limit, the injection keeps the newest entries within a reduced render
budget, shortens the compact summary as needed, marks the restore truncated,
and leaves the stored record on disk unchanged. Older decisions can be omitted;
newest-first selection is not a relevance or correctness judgement. A synthetic
[selection comparison](../../docs/validation/session-ledger-selection.md)
demonstrates why reserving space for older entries is not a universal improvement.

Records are never read or injected after 30 days and are purged on the next
Session Ledger hook. Claude Code's default final-scope uninstall also removes
plugin data; `--keep-data` deliberately preserves it. Hooks are advisory,
local, and fail open: unavailable, malformed, expired, or unsupported records
simply produce no carryover and never block Claude Code.

This plugin improves continuity and evidence hygiene; it does not guarantee
factual correctness, completeness, freshness, or domain truth.


## Experimental evidence memory (explicit enable)

This experiment separates bounded injected conversation from durable decisions
and searchable logged tool evidence. It is off by default. Enabling it is a
separate choice from installing Session Ledger; the current small follow-up
does not justify default-on capture.

An exploratory synthetic model comparison found better recovery than the
rolling record after simulated compactions, but no model-token saving versus
an efficient search of a surviving log. A follow-up with the post-compaction
memory packet recovered five synthetic earlier results in five tool-using runs;
without a cue, three runs never invoked retrieval. A strict lexical audit found
possible earlier-evidence reuse in local long sessions, but did not establish
that memory improved real answers. See `docs/plans/session-evidence-memory.md`
and its validation receipts for the exact populations and limits.

The `memory` skill provides commands and model guidance. For a disposable test:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/memory.py" --plugin-data "${CLAUDE_PLUGIN_DATA}" --session-id "${CLAUDE_SESSION_ID}" enable
```

Use `python` if `python3` is unavailable. The CLI also accepts explicit paths and
session IDs for manual Codex transcript ingestion. This does not install Codex
hooks. `status`, `sync /exact/transcript.jsonl`, `lookup KEY`, `search "keywords"`,
`fetch ID`, `state`, `remember` and `disable` are subcommands; see the memory skill for paging
and revision syntax. `status` also shows local counts of completed CLI lookup
outcomes, search hits/misses and successful fetches. It stores no query keys,
searched text, result content or timestamps in those counters; failed counting
never blocks retrieval. The counts reset with disable, clear or begin-plan.
Claude's PostToolUse, PostToolUseFailure, Stop and compaction
hooks sync incrementally while enabled. A call result not yet flushed to the
transcript is captured on a later hook; there is no guarantee after abrupt exit.
Claude runs with `--no-session-persistence` may supply a transcript path without
creating the file; a native Windows control did so, leaving the index empty.
Use a persisted session when testing automatic tool capture.

Storage: one SQLite database per hashed session directory, bound to the current
plan. It stores exact JSON **values logged by the host** for tool calls/results,
including arguments, rendered result blocks and Claude's richer `toolUseResult`
when present. It is not a complete raw transcript or a complete provider archive.
It preserves evidence after the original log is deleted. IDs link calls/results;
hashes check local body integrity. `lookup KEY` returns one unambiguous linked
call/result and the latest correction for that exact key in one bounded response.
It reports failed, missing, ambiguous and paged evidence instead of silently
treating it as a complete answer. FTS5 provides literal keyword search; Python
builds without FTS5 fall back to a bounded-output local database scan. Search and
fetch never read original logs. Neither mode guarantees semantic recall.

Decisions and corrections are explicitly written, with revision checks and
optional evidence IDs. Corrections supersede the same key; audit history remains.
They do not expire merely because the rolling conversation reaches 64 KiB.
After compaction, a bounded subset of current state and retrieval directions is
injected within the existing host output budget. The model must use the skill to
retrieve additional state/evidence; storage alone does not guarantee it will.

Limits: database pages are capped at 128 MiB per session (temporary SQLite journal
space is additional); a source line is capped at 8 MiB; each sync processes up to
one 8 MiB batch plus at most one line, with a one-second cooperative loop budget.
A single line/SQLite transaction can take longer; the host's existing five-second
hook timeout remains the outer limit. Search returns at most 20 previews; fetch
returns 2,048 characters per page. Large results are paged, not silently truncated.
A full database stops new writes and rolls back the cursor without evicting old
evidence. Malformed/oversized lines similarly stop at a retryable cursor. Repeated
warnings mean capture still cannot progress; use explicit sync/status to diagnose.

`lookup.status=found` means one paired historical log entry was retrieved. It
does not prove that a tool call or provider request succeeded. `host_error_signal`
distinguishes a reported error, a reported no-error flag and an absent flag;
Codex transcript outputs often omit that signal. Treat `error_flag_absent` as
unknown execution status and inspect the result before using it in an answer.

Clear, disable and begin-plan delete evidence and state; begin-plan also disables
capture until re-enabled. Explicit plan cutoffs exclude old or untimestamped log
rows. Successful capture or an explicit remember/enable action refreshes the shared
30-day inactivity expiry, including the rolling conversation record. Passive
search/fetch/status and a sync with no new rows do not refresh it. Expiry is
checked on access/pruning, not by a background
scheduler. Data can remain on an unused disk until the next cleanup. The rolling
record's expiry can also prune the corresponding memory database. File permissions
are restricted on POSIX; Windows protection depends on the containing directory's
ACLs. SQLite journals may temporarily contain the same sensitive values.

**Redaction:** `SESSION_LEDGER_REDACT` applies to the rolling record, not this
opt-in exact-evidence archive or durable state. Enabling memory may retain secrets
and provider payloads from tool output. Do not enable it where that is unacceptable.
No network, external telemetry or cross-session retrieval is added. Never commit captured
memory, transcripts or real query results as fixtures.

Synthetic replay tests establish storage/retrieval properties and measured local
I/O, not a general improvement in model answer accuracy. A clean installation and
live host smoke remain required before release.
