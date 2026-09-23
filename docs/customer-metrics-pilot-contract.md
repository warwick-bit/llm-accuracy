# Customer-metrics executable-check pilot

## Decision and alternatives

Stop tuning the analytical-review prompt. Test whether delivering executed
checks adds value on one concrete SQL artifact. A standalone example is the
smallest reversible addition; a new generic checking engine or another review
prompt is not justified. The existing Deterministic Data plugin routes
definitions and sources but does not execute this SQL oracle. Leave its scope
and all installed plugin behavior unchanged.

## Hypotheses and population

H1: executed reference/invariance results improve the scored review. H2: existing
guidance already finds the defect and correctly accepts valid work. H3: the
checker/scorer is wrong or a control fails, so comparison is uninterpretable.

One public SQL artifact from dbt Labs Jaffle Shop, pinned by revision and source
hash; one locally authored defective alternative; one synthetic snapshot. This
is a development demonstration, not real-company evidence, a holdout, a known
upstream regression or a generalized data/finance/systems benchmark.

## Independent truth and checks

The written contract defines source keys, membership, NULLs, currency and metric
grain. An independent Python grouping computes each customer's metrics. The
checker compares all output fields and tests invariance to a payment split.
Read-only SQLite executes the two queries after substituting three known refs.
No model determines source truth. Wrong-count, money, membership, duplicate,
NULL and source-integrity controls must fail, while the upstream query passes.
The model-output scorer must separately fail wrong verdict/count/value, missing,
duplicate or misattributed entities, and zero substituted for NULL. Pure row
reordering is accepted because entities are keyed.

## Arms and measurement

Both arms receive current 0.6.2 claim-fidelity/verify-technical/evidence-discipline
bodies explicitly and load the same native plugin hooks. Both get the same
contract, candidate SQL (without variant labels), fixture and observed SQL result.
The treatment alone additionally gets the actual checker report. It adds useful
computed information; this is not a prompt-only comparison or a test of whether
Claude can independently choose and execute tests.

Use the existing `host_probe` launcher: temporary auth profile and working
directory, no saved session, no tools/MCPs, explicit model `claude-sonnet-5` and
high effort. Require exactly one initialization/result, matching final model usage, a
successful UserPromptSubmit fidelity hook (event/outcome/exit/marker), and exact reported counts
for zero tools/MCPs, one accuracy plugin and one telemetry plugin. The launcher
attests these surfaces but not every implicit host instruction; this is not a
claim of an entirely neutral runtime or the user's installed setup.

Request JSON decision and verified customer counts/payment values plus textual
Checked/Gap/Next fields. Parse in memory; retain only hashes, enums/counts and
boolean scores. No raw model answer is saved. Compare decision and all keyed
metrics against independent truth; prose mechanism, additional findings,
execution-claim fidelity and semantic explanation quality are unscored. This
constrained output is shared across arms and limits applicability to free-form
review. No model extractor/judge owns the primary measurement.

## Rungs, variance and stopping

Pass local negatives and independent design review before spend. Start with the
correct query pair (existing then checks). Inspect that control before the
defective pair (checks then existing). Four initial review calls total. Stop
immediately on a runtime/shape failure, retaining the incomplete receipt and
excluding its pair. No retry or scorer tuning against live answers.

If both arms tie, stop: no incremental gain demonstrated on this artifact. If
there is a quality discordance, repeat both variants/arms once with reversed
order, preserving first outcomes. At most eight review calls. An improvement
requires correct verdict and every requested metric on defective work without
rejecting the correct query, and must recur on the repeat; even then it is only
one-artifact evidence. No confidence interval or generalized accuracy claim.
No content-versus-verbosity claim is made; the treatment is an executed report.

## Delivery boundary

Deliver a runnable, reviewed example and an honest result. Add no new installed
skill/hook and make no release or superiority claim from this pilot. Publish a
separate draft so the earlier reviewer experiment remains unchanged.

The existing launcher's parser does not attest hook success or final usage. A
pilot-local sequential wrapper adds those checks and restores the parser after
each call, including failures; no installed module is changed. Independent
pre-spend review caught this gap and the mutation's label comment. Regression
tests reject the old false-pass trace and packets omit variant labels/comments.
