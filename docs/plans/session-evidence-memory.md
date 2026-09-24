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
