# Source verification expansion

## Outcome and scope

Add direct CSV checking, explicit old/current source rechecks and local citation/
quotation checking to the existing optional Accuracy skills. Preserve original
claims, unavailable evidence and the distinction between calculations, quote
presence and semantic support. The smallest deliverable reuses the three bounded
monetary checks and standard-library readers; it adds no hooks, network client,
persistence, report generator or new plugin dependency.

Essential checks are real CLI cases with independently calculated expectations,
wrong-result controls and valid alternatives; missing/duplicate/mixed-unit source
boundaries; changed or unavailable evidence; source preservation; package and
Python compatibility; and independent delivery review. Current candidate hashes
must be reset after package changes. Local tests do not certify installed/live
delivery or establish a general model-accuracy improvement.

## What the evaluation repository adds

Reviewed the public evaluation repository at
[`39223f6`](https://github.com/warwick-bit/llm-finance-data-eval/tree/39223f6).
The later evidence companion takes precedence over historical pending-work notes.
Existing frozen studies were inspected, not rerun or relabelled as fresh evidence.

| Observed limitation | Preventive choice in this expansion | Named checks / residual gap |
| --- | --- | --- |
| Correct updated calculations can coexist with stale policy prose; a generator-based checker can repeat its own error. | Compare original claim lines against independently supplied old/current source files; retain unsupported prose explicitly. | `test_changed_source_rechecks_same_claims_and_failed_refresh_keeps_history`; arbitrary prose and omitted claims still need a separate inventory. |
| A checker rejected a legitimate reordering while failing to protect all semantic associations. | Aggregate by explicit period/region/series and record distinct transaction IDs; attach source record locations. | `test_reordered_records_and_split_transactions_are_valid_alternatives`, missing-region and wrong-amount checks; CSV source definitions remain supplied assumptions. |
| A failed refresh left mixed generations of output files. | Read original sources and emit results on stdout; never rewrite inputs or prior reports. | Source byte-preservation tests and old/current unavailable-source checks; another application's publication atomicity remains outside this plugin. |
| Mentioning price was interpreted as evidence of dissatisfaction or cause. | Keep quotation matching separate from entailment; a matching quote never sets claim support to verified. | `test_quotes_resolve_beside_manifest_with_hashes_without_entailment`; a model still needs to judge meaning against surrounding context. |

Sources: [evidence companion, sections 1–3 and 5](https://github.com/warwick-bit/llm-finance-data-eval/blob/39223f6/followup/evaluation/RELEASE-EVIDENCE.md),
[checking-guidance study](https://github.com/warwick-bit/llm-finance-data-eval/blob/39223f6/followup/evaluation/results/2026-10-24-checkable-working-capital/REPORT.md),
[working-capital reuse diagnostic](https://github.com/warwick-bit/llm-finance-data-eval/blob/39223f6/followup/evaluation/results/2026-10-23-working-capital/REPORT.md),
and [retention wording/coverage findings](https://github.com/warwick-bit/llm-finance-data-eval/blob/39223f6/followup/evaluation/results/2026-10-24-subscription-retention/REPORT.md).
These are observed scoped failure examples, not comparable model failure rates.

## Further additions worth evaluating

The strongest next addition is a final-report assertion inventory: bind each
material number, policy threshold, population label and consequential qualification
to its checked source or explicitly mark it unchecked. Check the delivered prose
after shortening or regeneration, including side claims. The present helpers
cannot prove the inventory is complete; adding automatic extraction would need
its own omission and false-positive controls.

A second opportunity is an optional deliverable/reuse check for user-authored
analysis programs: required files, changed-input runs and preservation of the
previous complete output on failure. It belongs at the consuming application's
publication boundary; the stateless Accuracy plugin should not claim to enforce
arbitrary writers or silently rerun a user's program.

Neither recommendation is implemented as an additional framework here. For a new
model efficacy study, follow the eval repository's standing protocol: observed-
failure replay and realistic human-led conversation, each in matched clean and
current-harness sessions, with actual delivery verified and original failures
retained. The new deterministic tests are regression checks, not that study.
