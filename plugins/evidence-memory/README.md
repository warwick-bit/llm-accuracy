# Evidence Memory plugin (experimental)

Evidence Memory is an independent Claude Code plugin for exact, local,
current-session tool-result retrieval and revisioned corrections. It can run
without Session Ledger. It is disabled by default and requires a separate
per-session `enable` action before capture. The stored results may contain
sensitive data.
The first enable can index earlier rows from the current session if its host
transcript still exists. After disable, clear or begin-plan, the retained cutoff
prevents those earlier rows from being indexed on a later enable.

Install it with `/plugin install evidence-memory@llm-accuracy`, then enable the
plugin in `/plugin` and restart Claude Code. To begin capture in a session, run
`/evidence-memory:memory` and use its `enable` command. `disable` deletes that
session's evidence and state. `begin-plan` and `clear` also delete them. Each
deletion retains only a fresh local cutoff marker so later enablement cannot
reindex evidence from before the deletion.

## Experimental evidence memory (explicit enable)

This experiment stores durable decisions and searchable logged tool evidence.
It is off by default, and installing or enabling Session Ledger does not enable
it. The current small follow-up does not justify default-on capture.

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
evidence. Malformed, oversized or invalid-tool-identity lines similarly stop at a
retryable cursor. A row with another explicit session ID rejects the transcript
as a scope mismatch. Repeated warnings mean capture still cannot progress; use
explicit sync/status to diagnose.

`lookup.status=found` means one paired historical log entry was retrieved. It
does not prove that a tool call or provider request succeeded. `host_error_signal`
distinguishes a reported error, a reported no-error flag and an absent flag;
Codex transcript outputs often omit that signal. Treat `error_flag_absent` as
unknown execution status and inspect the result before using it in an answer.

Clear, disable and begin-plan delete this plugin's evidence and state and stop
capture until re-enabled. They retain a minimal cutoff marker (session/workspace
hashes, a plan ID and timestamp) to prevent reingestion from a surviving host
transcript. They do not clear Session Ledger data.
Explicit plan cutoffs exclude old or untimestamped log rows. Successful capture
or an explicit remember/enable action refreshes this plugin's 30-day inactivity
expiry. Passive search/fetch/status and a sync with no new rows do not refresh it.
Expired data cannot be retrieved and is replaced on the next enable; there is no
background deletion scheduler, so unused files may remain on disk until then or
until explicit deletion. File permissions are restricted on POSIX; Windows
protection depends on the containing directory's ACLs. SQLite journals may
temporarily contain the same sensitive values.

**Redaction:** Session Ledger's `SESSION_LEDGER_REDACT` setting does not apply to
this independent exact-evidence archive or durable state. Enabling memory may retain secrets
and provider payloads from tool output. Do not enable it where that is unacceptable.
No network, external telemetry or cross-session retrieval is added. Never commit captured
memory, transcripts or real query results as fixtures.

Synthetic replay tests establish storage/retrieval properties and measured local
I/O, not a general improvement in model answer accuracy. A clean native Windows
installed-host smoke passed with synthetic data; live long-session benefit and
macOS host behaviour remain unmeasured. See the
[standalone validation receipt](../../docs/validation/evidence-memory-standalone-2026-09-25.json).
