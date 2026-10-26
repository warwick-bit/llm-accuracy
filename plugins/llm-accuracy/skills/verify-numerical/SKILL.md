---
name: verify-numerical
description: Use when analysing supplied data, calculating or checking report figures, or updating numerical claims after source changes. Includes source-bound maths guidance and bounded monetary growth/ratio checks; other forms need separate calculations. Not for creative writing or ordinary coding without data analysis.
argument-hint: "[report and source files, or source update]"
---

# Verify analysis and numerical reports

Read `../../references/numerical-verification.md`, resolved from this skill's
directory, and follow its
workflow. Use the supplied sources and their definitions; do not invent a metric,
source authority or complete population to make a check pass.

For consequential calculations, claims outside the bounded helper, or a request
for mathematical proof, read `../../references/mathematical-verification.md`.
Use its relevant failure exploration, dataset-specific checks and proof boundaries;
the optional publication example is not a routine analysis step.

When the report contains a supported monetary growth, every-region or ratio form, run
`../../scripts/check_numerical_claims.py` with a working Python 3.9+
executable. Resolve that path from this skill's installed directory, not the user's
working directory; pass the resulting absolute path and quote paths. If no
execution tool or Python is available, state that the helper did not run.

Keep the original claims, source mapping and per-claim results together. Inspect
the entire report, including clauses the checker does not recognize. Correct
supported errors, retain useful valid wording and make unchecked claims clear.
For other figures use appropriate calculations or tests and identify them as
separate checks. Require the claim's metric to match the source; never relabel
another measure as revenue or invent retention definitions to fit the schema.
When a missing definition, population or comparison materially changes the result,
use [Clarify](../clarify/SKILL.md) before dependent calculations. Reuse settled
answers and prefer the host's available interactive question tool.

For a CSV export, use the helper's `--csv-mapping` option and an explicit mapping
from the numerical reference. It reads the original records and supplies exact
record/line references; do not manually rewrite a CSV into a more convenient
population. Resolve duplicate records or revised versions from the source's
rules, never silently deduplicate them. Missing regions or periods remain unknown.

For changed source files, use `--previous-source` to recheck the same original
claims against both snapshots. Inspect each `previous` and `current` result,
including unavailable-source outcomes. Revisit affected prose, recommendations
and qualifications in the final deliverable; changed calculations alone do not
update the narrative. Retain useful independently supported results.

Keep the response proportionate: corrected result, material corrections, and
remaining gaps. Save report/audit/evidence files when the user requests files or
the task needs reproducible deliverables; otherwise keep the audit concise in
the conversation and use temporary helper inputs. Do not modify the plugin or
original sources. Preserve prior requested deliverables on a source update.

This is an advisory workflow plus three bounded executable checks. A successful
execution is not whole-report approval, source authentication or a general proof.
