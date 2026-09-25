# Session evidence memory: experimental, local, session-scoped

## Contract

Problem: a bounded rolling conversation loses early corrections and exact tool
results during long work. Increasing the injected context does not provide
reliable retrieval. Owning surface: the separately installed Session Ledger.

Acceptance: explicit current decisions and exact logged tool call/result pairs
remain retrievable after repeated compactions and original-log deletion; search
and fetch do not reread transcripts. Missing pairs and host-reported failures
remain explicit. A host that omits an execution-error flag cannot establish
whether a logged result came from a successful call. All automatic work remains advisory.

Constraints: local only, current session and plan only, 30-day expiry, no external
services or dependencies, no captured data in source/tests. Capture is experimental
and explicitly enabled per session pending usefulness tests. This deliberately
extends the old persistence boundary to logged tool data. It is not a release or
an installation change. Codex support is explicit CLI ingestion, not host hooks.

Consumers: Claude hooks and memory skill, portable CLI, existing clear/begin-plan
and expiry, distribution archives, Python 3.9–3.13 and Windows Git Bash.

## Alternatives and hypotheses

1. Larger FIFO: helps recent recall but still loses early corrections; rejected
   as the primary design. Test by exceeding the existing rolling cap.
2. Search original logs on demand: exact when logs survive, low upfront cost;
   control/oracle for correctness. Repeated scans and deleted logs are its limits.
3. Incremental local index plus explicit state: chosen experiment. Extra storage
   and capture complexity must earn their cost in paired replay tests.

Other failure hypotheses: wrong source/session pairing; truncated host results;
encoding differences; rewritten logs; stale results treated as current; state
supersession lost; inaccessible evidence despite correct storage. Tests must
separate these from model failure to call the retrieval skill. Storage tests alone
cannot establish improved model answers or frequency of real-world memory need.

## Implementation sequence

1. Add a stdlib SQLite store: atomic event/cursor commits, linked calls/results,
   full-text search with literal fallback, immutable hashed logged evidence,
   explicit state revisions. Bounded incremental reads and bounded paged output.
2. Add CLI and optional hook bridge. Record the session identity, plan and expiry;
   integrate clear/reset/expiry. Restore a small untrusted active-state packet and
   retrieval directions. Do not inject full results.
3. Add synthetic parser, lifecycle, failure, Windows subprocess and replay tests.
4. Run native gates, independent review, fix findings, open a stacked draft PR.

## Evaluation contract (pinned before implementation)

Hypothesis: indexed memory recovers exact historical evidence and the latest
explicit correction with less repeated transcript I/O than scanning, without
claiming stale/failed/missing results are verified current data.

Population/unit: all synthetic cases in the committed replay, each an earlier
evidence request following at least three compactions and FIFO overflow. Control:
rolling ledger, individual full-log scans and a single batched scan oracle; baseline source is the parent commit
of this feature. Treatment: enabled memory. Include ordinary/repeated queries,
correction, error, missing result, source deletion, Unicode and truncation.

Gates: every expected call/result and current correction recovered exactly;
no host-reported failed/missing result marked successful; zero original-transcript bytes read
by search/fetch after indexing; bounded output and storage; old ledger still
behaves identically when disabled. Report initial index I/O and retained bytes
separately. Tests are deterministic, so sampling variance is not estimated.
Elapsed times are observations only. No model-answer accuracy uplift is claimed.

Artifacts: tests/test_session_memory.py and scripts/session_memory_replay.py
aggregate JSON output. All values synthetic. A live clean-host smoke remains a
release gate. Default-on capture remains undecided; reversible next action is
explicit enable in a disposable test session, then clear.


## Review-driven measurement clarification

The replay instruments Python file opens/reads, including identity and anchor
reads. It measures logical bytes, not physical disk I/O or cold-cache latency.
A batched full scan is reported alongside independent per-request scans. Indexing
is not expected to beat a single batched scan's initial cost. Its value is stable
addressable evidence, subsequent lookup without transcript access, and recovery
after deletion. The gate rejects transcript-open attempts after source deletion
and initial capture exceeding twice the single-scan bytes in this fixture.
Some small early conversation messages fit in the rolling ledger's leftover
budget; the replay reports that instead of assuming all old messages disappear.

## Exploratory model-in-loop result (25 Sep 2026)

The reproducible optional harness is `scripts/session_memory_model_eval.py`;
aggregate numeric receipts are in
`docs/validation/session-memory-model-pilot-2026-09-25.json`. The fixture has
three simulated compactions, 48 successful synthetic tool results, an explicit
correction, one failed result and one missing result. A deliberately wrong value
fails the scorer. The model is Claude Sonnet at low effort. Counted tokens are
CLI input (including cache creation/read) plus output; they include fixed host
context and are not a billing or end-user cost estimate.

The five-case packet comparison recovered exact answers in 5/5 with indexed
evidence and 5/5 with a batched log scan, versus 0/5 with the rolling ledger
alone or an equally sized irrelevant packet. Indexed lookup read no transcript
bytes; the repeated scan read 5,055,600 bytes across the five questions.
Mean model tokens were 4,230 for memory and 4,229 for the scan: indexing did
not reduce model tokens when both supplied the same useful evidence.

In the final-head seven-case tool-using run, both isolated arms recovered all
five answerable results. The index arm scored 6/7 overall: it returned a
non-JSON answer for the failed-result case. The surviving-log arm scored 7/7.
Mean counted tokens were 18,300.0 for one-call memory lookup and 17,806.1
for log search, a 493.9-token or 2.8% overhead for memory. Each used two
model turns. An earlier isolated run scored 7/7 for both arms; the negative
case's output-format variance prevents a stable reliability claim. The first
source-loss pilot was
invalid because both arms shared the database; it was discarded. In the
isolated final-head one-case source-loss rerun, memory recovered the answer and
the arm with neither transcript nor index did not produce a valid exact answer.

The tool-using prompt named the retrieval command, so this does not measure
spontaneous skill selection. Negative-control pilots produced some non-JSON
answers even with complete model turns. No real-session frequency, live
answer-accuracy uplift, or general token saving is established. Capture
therefore remains opt-in while a real-session study is designed.

## Follow-up measurement boundary

CLI retrieval outcomes are counted locally by status without storing queries or
content. This measures attempts and coverage only, not whether a retrieved
answer was used correctly. Counts belong to the same session/plan database and
are deleted with it. Counting failures cannot block evidence retrieval.

The follow-up aggregate receipt is
`docs/validation/session-memory-followup-2026-09-25.json`. A raw-free local
audit scanned Codex and Claude JSONL files for a distinctive token in an early
logged tool result that reappeared in assistant prose after a third compaction,
but was absent from the third compacted payload and surrounding user prose.
There were candidates in 3/17 long Codex sessions and 1/2 long Claude sessions.
The smallest eligible candidate from each host was indexed from a disposable
source copy, then fetched exactly after that copy was deleted. This is a strict
lexical opportunity proxy: paraphrases are missed, and overlap does not prove
that the answer needed memory. The public audit script emits only aggregates.

The optional `scripts/session_memory_spontaneous_eval.py` loads a disposable
skill with this branch's CLI and synthetic index. With no retrieval cue, three
positive questions produced no lookup and no exact answer. Naming the skill in
the prompt yielded 2/3. The original post-compaction packet yielded 2/3; a
clearer instruction to check earlier tool results yielded 3/3 on those same
cases and 2/2 additional cases. One missing-result case returned unavailable;
three completed failed-result runs did invoke lookup but returned non-JSON
answers, so they remain unscorable on the exact-answer rubric. One visible
context control answered correctly without retrieval. The model test is small,
synthetic, and partly tuned on the evaluated cases; it does not show production
accuracy lift or token savings. Capture stays opt-in.

A native Windows Claude Code 2.1.281 smoke used a disposable enabled plugin
copy and a persisted synthetic session. SessionStart, UserPromptSubmit,
PostToolUse and Stop fired; the index held the call/result pair, and both the
session transcript and plugin state were deleted afterward. A
`--no-session-persistence` control supplied a transcript path without a file,
so automatic indexing had no source. The normal authenticated profile supplied
auth while settings and plugin source were isolated. A clean authenticated
installation smoke and macOS remain outside this evidence.

An eval-only JSON Schema probe separated failed-result content from formatting.
With the same restored memory cue, three failed-result runs invoked lookup,
received `unverified`, and returned the exact unavailable object under the
schema. The evaluator required Claude's structured-output field, so it could
not silently score free-form text. One supported, one missing, and one uncued
case were single-run smoke controls; the uncued case did not retrieve the old
value. These are not rate estimates. Ordinary production answers are not
schema-constrained, so free-form JSON failures remain possible.

A fresh temporary Claude profile added this branch as a local marketplace,
installed and enabled Session Ledger, and matched all 11 installed source files
to the branch. That validates package installation. A model call from an
isolated profile returned `api_error` even without the plugin on Linux and
Windows; its precise environment cause was not determined. No credentials
were copied into that profile, so authenticated installed-host hook delivery
remains untested.

On native Windows, a direct marketplace add from the WSL UNC worktree exited
with code 1. Staging the committed source as a local Windows archive succeeded:
marketplace add, install and enable all exited 0, all 11 plugin files matched,
and the disposable profile was removed. The cause of the UNC-path failure was
not diagnosed. This adds package compatibility evidence, not an authenticated
installed-host hook test.

A full-branch review found a restore-size boundary: delimiter-heavy state text
could expand after JSON escaping and exceed the 9,500-character host response
limit even after rolling context was removed. The packet now drops older state
excerpts until its final escaped response fits; the host boundary also drops
any future packet that still cannot fit. A synthetic four-correction case
reproduced 11,913 characters before this fix.

Codex's sampled `function_call_output` and `custom_tool_call_output` rows did
not expose a structured execution-error field. Retrieval now reports whether
the host's `is_error` flag was true, false or absent. `lookup.status=found` means
a unique paired log entry was retrieved; it does not assert successful tool or
provider execution. The memory skill requires inspecting and rechecking such
evidence. Read/write CLI actions now apply the same session-path symlink check
as disable.
