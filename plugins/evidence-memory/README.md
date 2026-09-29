# Evidence Memory plugin (experimental)

Evidence Memory is an independent Claude Code plugin for exact, local,
current-session tool-result retrieval and revisioned corrections. It can run
without Session Ledger. The plugin is disabled by default. Once you enable it
in Claude settings, capture starts automatically in each session at a fresh
cutoff; earlier transcript rows are not imported. Stored results may contain
sensitive data. Disable the plugin in Claude settings to stop future sessions.
After session-level disable, clear or begin-plan, the retained cutoff prevents
earlier rows from being indexed on an explicit resume.

Install it with `/plugin install evidence-memory@llm-accuracy`, then enable the
plugin in `/plugin` and restart Claude Code or run `/reload-plugins`. Capture
begins at the next session start or prompt. `/evidence-memory:memory disable`
stops capture and deletes that session's evidence and state. `begin-plan` and
`clear` do the same. Each deletion retains a fresh local cutoff marker so
capture stays stopped in that session until `/evidence-memory:memory enable`
explicitly resumes it.

## What is captured

Since 0.3.0 the default capture scope is **external results**: the calls and
results of MCP tools (`mcp__*`), `WebFetch` and `WebSearch`. Local shell, file,
edit and agent tools are skipped because their output can usually be reproduced
in the same session, and they carried most of the stored volume without being
retrieved. A result is stored only beside its own stored call from the same
transcript; results without one are counted, not archived as unpaired evidence.

Codex records one outer JavaScript cell per turn step. A cell is treated as
external when its code calls `tools.mcp__…(` or `tools.web__run(`; the whole cell
and its combined output are stored, including any local commands in the same
cell. This is a signal from the logged code, not proof of which inner tools ran.

Calls to MCP tools whose names contain a restricted word are **withheld**: neither
the call nor its result is stored, in any capture mode. The default words cover
HR, payroll, bank, tax, identity and secret tools (`bank`, `credential(s)`,
`employee(s)`, `hr`, `leave`, `passport`, `password(s)`, `payroll`, `payslip(s)`,
`pension`, `salary`/`salaries`, `secret(s)`, `ssn`, `superannuation`, `tax`,
`timesheet(s)`), matched as whole words after splitting the name on
punctuation and case changes (`getSSNProfile` contains `ssn`). A Codex cell
that mentions any restricted MCP name is withheld whole. Withholding is best
effort and name-based: a tool with an innocuous name,
such as a general SQL tool, can still return sensitive rows.

An optional `${CLAUDE_PLUGIN_DATA}/config.json` changes the preference:

```json
{"capture": "all", "extra_restricted_tokens": ["patient"]}
```

`capture` is `external` (default) or `all`, which restores the 0.2 behaviour of
storing every tool call except withheld ones. `extra_restricted_tokens` adds
alphanumeric words to the withheld list; the defaults cannot be removed. An
invalid, oversized or symlinked file is ignored and `status.capture.config`
reports `invalid_using_default`. The file is a local preference, not a security
boundary. A change applies to rows read afterwards, including results of calls
stored earlier; rows already stored stay until `disable`. `status` also reports
`capture_counts` (calls out of scope, calls withheld, results without a stored
call, results withheld because their call is out of the current scope) and
`capture_policy`.

Indexes created before 0.3.0 keep their earlier unscoped rows, reported as
`capture_policy: legacy_unscoped_rows`; new rows follow the current scope. Run
`clear` to remove the earlier rows.

## Codex (experimental)

The same hook commands also run as a Codex plugin. Codex CLI 0.158 was
smoke-tested with synthetic data; other versions are untested.

```bash
codex plugin marketplace add warwick-bit/llm-accuracy
codex plugin add evidence-memory@llm-accuracy
```

A local clone path also works as the marketplace source. Plugin hooks need
`[features] hooks = true` in Codex's `config.toml`, and Codex must trust them
before they run. Unlike Claude Code, **installing the plugin in Codex enables
it**: capture starts at a fresh cutoff in each new session. Remove it with
`codex plugin remove evidence-memory@llm-accuracy`. Data is stored in the
`evidence-memory-llm-accuracy` folder under `$CODEX_HOME/plugins/data`
(normally `~/.codex`).

- **Captured unit:** Codex logs one code-mode `exec` cell, not each tool call. A
  cell is stored when its code calls `tools.mcp__…(` or `tools.web__run(`, and
  its stored result is only what the cell printed. A cell that calls a tool
  without printing stores no values. A cell that mentions any restricted MCP
  name is withheld whole, so other results in that cell are not stored either.
- **Error signal:** cell outputs carry no error flag
  (`host_error_signal: error_flag_absent`); inspect the result before using it.
- **Skill paths:** Codex does not fill in the skill's `${CLAUDE_…}`
  placeholders. After the first compaction the restore packet's
  `command_prefix` is the resolved command. Before that, run `memory.py` from
  `$CODEX_HOME/plugins/cache/llm-accuracy/evidence-memory/<version>/hooks/`
  with `--plugin-data` set to that data folder and the session ID from the
  rollout file name.
- **Sandbox:** read actions work in Codex's read-only sandbox. `remember`,
  `sync`, `enable` and `disable` need a writable plugin data directory, which
  the default Codex sandboxes do not grant.
- **Events:** Codex has no `PostCompact` or `PostToolUseFailure` hook. Capture
  runs on prompt, tool, stop and pre-compaction events; the packet is restored
  on `SessionStart`.

See the [Codex smoke receipt](../../docs/validation/evidence-memory-codex-smoke-2026-09-30.json)
for what was checked.

## Experimental evidence memory (plugin opt-in)

This experiment stores durable decisions and searchable logged tool evidence.
It is off by default, and installing or enabling Session Ledger does not enable
it. Enabling this plugin is a one-time choice to capture exact tool evidence in
every new session; no extra per-session command is needed.

An exploratory synthetic model comparison found better recovery than the
rolling record after simulated compactions, but no model-token saving versus
an efficient search of a surviving log. A follow-up with the post-compaction
memory packet recovered five synthetic earlier results in five tool-using runs;
without a cue, three runs never invoked retrieval. A strict lexical audit found
possible earlier-evidence reuse in local long sessions, but did not establish
that memory improved real answers. See `docs/plans/session-evidence-memory.md`
and its validation receipts for the exact populations and limits.

The `memory` skill provides commands and model guidance. To resume a session
after its evidence was cleared, run `/evidence-memory:memory enable`; the skill
text carries the resolved plugin paths and session ID. `${CLAUDE_PLUGIN_ROOT}`,
`${CLAUDE_PLUGIN_DATA}` and `${CLAUDE_SESSION_ID}` are substituted in hook and
skill text, not set in an ordinary shell, so a manual command needs explicit
values:

```bash
python3 ~/.claude/plugins/cache/llm-accuracy/evidence-memory/<version>/hooks/memory.py \
  --plugin-data ~/.claude/plugins/data/evidence-memory-llm-accuracy \
  --session-id <session-id> enable
```

Use `python` if `python3` is unavailable. The CLI also accepts explicit paths and
session IDs for manual Codex transcript ingestion. This does not install Codex
hooks. `status`, `sync /exact/transcript.jsonl`, `lookup KEY`, `search "keywords"`,
`fetch ID`, `state`, `remember` and `disable` are subcommands; see the memory skill for paging
and revision syntax. `status` also shows local counts of completed CLI lookup
outcomes, search hits/misses and successful fetches. It stores no query keys,
searched text, result content or timestamps in those counters; failed counting
never blocks retrieval. The counts reset with disable, clear or begin-plan.
When a sandbox makes the plugin data directory read-only, `status`, `lookup`,
`search`, `fetch` and `state` still work: they open the index read-only, share
the session lock if it exists, and record no retrieval counts (`status` reports
`read_only: true`). `sync`, `remember`, `enable` and `disable` still need a
writable data directory; only permission and read-only filesystem refusals fall
back.
Claude's prompt, PostToolUse, PostToolUseFailure, Stop and compaction hooks sync
incrementally while capture is active. A call result not yet flushed to the
transcript is captured on a later hook; there is no guarantee after abrupt exit.
Claude runs with `--no-session-persistence` may supply a transcript path without
creating the file; a native Windows control did so, leaving the index empty.
Use a persisted session when testing automatic tool capture.

Storage: one SQLite database per hashed session directory, bound to the current
plan. It stores exact JSON **values logged by the host** for tool calls/results,
including arguments, rendered result blocks and Claude's richer `toolUseResult`
when present. It is not a complete raw transcript or a complete provider archive.
It preserves evidence after the original log is deleted. IDs link calls/results;
hashes check local body integrity. `fetch` accepts a full ID or a unique prefix
of at least 12 characters and reports `ambiguous_id` otherwise. `lookup KEY` returns one unambiguous linked
call/result and the latest correction for that exact key in one bounded response.
It reports failed, missing, ambiguous and paged evidence instead of silently
treating it as a complete answer. FTS5 provides literal keyword search; Python
builds without FTS5 fall back to a bounded-output local database scan. Search and
fetch never read original logs. Neither mode guarantees semantic recall.

Decisions and corrections are explicitly written, with revision checks and
optional evidence IDs. Corrections supersede the same key; audit history remains.
They do not expire merely because the rolling conversation reaches 64 KiB.
After compaction, the injected packet lists up to ten recent paired external
results, newest first, as a short ID, tool name(s), time, logged size and host
error flag. It carries no call arguments or result content, because call input
can hold secrets or instruction-like text; the model fetches the ID to see both.
The packet also carries a bounded subset of current state and a resolved
`command_prefix` for the CLI. It stays within the host output budget, dropping
the oldest listed results before any state, and is omitted when there is no
listed result or state. The model must still choose to retrieve; storage alone
does not guarantee it will. An ID is provenance for a logged historical result,
not verification.

Limits: database pages are capped at 128 MiB per session (temporary SQLite journal
space is additional); a source line is capped at 8 MiB; each sync processes up to
one 8 MiB batch plus at most one line, with a one-second cooperative loop budget.
A single line/SQLite transaction can take longer; the host's configured ten-second
hook timeout remains the outer limit. Search returns at most 20 previews; fetch
returns 2,048 characters per page. Large results are paged, not silently truncated.
A full database stops new writes and rolls back the cursor without evicting old
evidence. Malformed, oversized or invalid-tool-identity lines similarly stop at a
retryable cursor. A row with another explicit session ID rejects the transcript
as a scope mismatch. Repeated warnings mean capture still cannot progress; use
explicit sync/status to diagnose.
An uncreated or empty transcript is retried quietly twice; a third missed hook
reports a notice once, and later hooks keep retrying. A busy session lock reports
a safe error class and can catch up on a later hook. Other hook failures report
a fixed error code or exception class, without transcript text or paths.

`lookup.status=found` means one paired historical log entry was retrieved. It
does not prove that a tool call or provider request succeeded. `host_error_signal`
distinguishes a reported error, a reported no-error flag and an absent flag;
Codex transcript outputs often omit that signal. Treat `error_flag_absent` as
unknown execution status and inspect the result before using it in an answer.

Clear, disable and begin-plan delete this plugin's evidence and state and stop
capture for that session until explicitly resumed. They retain a minimal cutoff marker (session/workspace
hashes, a plan ID and timestamp) to prevent reingestion from a surviving host
transcript. They do not clear Session Ledger data.
Automatic session starts and explicit plan cutoffs exclude old or untimestamped log rows. Successful capture
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
The 0.3.0 scope choices and restore-packet comparison are in the
[0.3.0 receipt](../../docs/validation/evidence-memory-0.3.0-2026-09-30.json).
