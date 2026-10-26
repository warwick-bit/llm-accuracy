# Accuracy 0.8.3

This release adds optional source-verification tools and failed-refresh checks:

- CSV input with explicit column/unit/population mappings and source-row lineage.
- Old/current source rechecks retaining both results for every original claim.
- Local citation and quotation checks, separate from semantic claim support.
- A final-report assertion inventory showing unlisted lines, rewritten assertions
  and changed source files behind manual assessments.
- Declared input/output snapshots and failed-refresh checks that detect overwritten
  or deleted required outputs without running or repairing a producer.

Accuracy and Deterministic Data receipt validators reject duplicate JSON keys and
return structured errors for decoder limits. The companion Deterministic Data
package is version 0.1.2; its declared catalogue/routing scope is unchanged.

These are bounded verification capabilities. Exact source definitions remain
supplied assumptions; quote presence is not entailment; line coverage is not
semantic completeness; observed file preservation does not guarantee atomicity,
crash durability or content correctness. No general model-accuracy improvement
has been measured for these additions. See the [source/eval evidence mapping](source-verification-evidence.md).

Qualification receipts and final publication status are recorded below before release.
