# Session evidence memory: experimental, local, session-scoped

## Contract

Problem: a bounded rolling conversation loses early corrections and exact tool
results during long work. Increasing the injected context does not provide
reliable retrieval. Owning surface: the separately installed Session Ledger.

Acceptance: explicit current decisions and exact logged tool call/result pairs
remain retrievable after repeated compactions and original-log deletion; search
and fetch do not reread transcripts. Calls with missing or failed results cannot
be represented as successful evidence. All automatic work remains advisory.

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
no failed/missing result marked successful; zero original-transcript bytes read
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
