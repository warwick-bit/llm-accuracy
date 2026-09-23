# Customer metrics: separate rendering follow-up

The user requested continuation after the stopped first pilot. This is a new
protocol, not a retry, rescoring or replacement of its unscored receipt.
The original raw answer is unavailable; its specific formatting fault is unknown.

## Decision and alternatives

Keep the same SQL, synthetic fixture, independent truth, current-plugin arms,
model and runtime attestation. Add a shared explicit output-structure example
and permit exactly one whole-answer Markdown JSON fence. Preserve semantic
scoring. Reject surrounding prose, multiple objects, duplicate JSON keys and
nonfinite JSON constants. Record fixed diagnostic categories, never raw answers.
The structure example uses an empty metric array and an arbitrary allowed enum;
it is explicitly not the expected answer and appears equally in both arms.

Alternatives rejected: another model extractor introduces semantic judge risk;
a new general reviewer prompt changes the intervention before measuring checks.
This repair addresses a plausible rendering problem, not a proven root cause.

## Frozen hypothesis and population

Executed checks may help the existing plugin assess the authored defect while
accepting correct SQL. The competing hypothesis is that the existing plugin
already answers correctly. Same single public artifact, two implementations,
one fictional snapshot; a development demonstration, not a holdout or general
finance/systems evaluation. Inspect all results.

## Rungs and stop rules

Pass deterministic scorer negatives and independent design review before spend.
Run one correct-query pair, existing then checks. Stop immediately on any runtime
or shape failure. Stop before defective work if either clean control is wrong.
Only if both clean controls pass, run the defective pair, checks then existing.
At most four calls, no retries, extraction fallback or live-answer-based tuning.
If results tie, report no incremental gain on this artifact. A discordance is a
single exploratory observation, not an improvement claim; no repeats in this
follow-up. Variance is unmeasured because this bounded follow-up tests viability.

Primary score: correct decision AND all customer-keyed reference counts and
payment values, with complete nonduplicated coverage and correct NULLs. Failure
categories distinguish unscored JSON/root/field/runtime problems from scored
wrong answers. Report scored calls and complete pairs as separate denominators.
Prose explanations and unsupported prose claims remain unmeasured, so this is
not a promotion gate. The treatment receives precomputed evidence; it does not
measure independent tool choice, execution, natural review or general accuracy.

## Artifacts and boundaries

Runner: `scripts/eval_customer_metrics_v2.py`; tests:
`tests/test_customer_metrics_v2.py`. Persist one separate typed receipt under
`docs/validation/`, with source/prompt/answer hashes and runtime metadata. The
original contract/results/receipt remain unchanged. No installed plugin change.
No pooling with the first pilot or earlier reviewer studies.
