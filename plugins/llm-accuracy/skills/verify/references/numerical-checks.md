# Numerical checks

Read [numerical-verification.md](numerical-verification.md) for the supported
helper forms and source mapping. Use [mathematical-verification.md](mathematical-verification.md)
for consequential calculations outside those forms. Resolve `<skill-directory>`
to the directory containing SKILL.md; never pass the literal placeholder to a tool.

- Preserve the agreed metric, currency, included population, grain, denominator,
  dates and source version. A common convention does not settle an unresolved
  definition. Apply Verify's clarification step before choosing a result.
- When execution is available, execute arithmetic not already calculated by a
  tool, including explanatory working. Reuse an observed executed tool calculation
  only when its inputs and source version match the requested calculation; check
  definitions, units and faithful transcription. Recalculate after input changes,
  transformations or rounding introduced in the answer, or if a discrepancy appears.
  Values quoted directly from a source need source and transcription checks, not
  an invented equation. Check the expression actually printed, not just a correct
  headline or a related helper result. Keep ratios distinct from growth (ratio minus
  one). If execution is unavailable, calculate what is supportable and state the
  consequential gap.
  Do not add unchecked alternative calculations merely to expand the answer.
  Use exact counts/cents or decimal/rational arithmetic when useful. Aggregate
  totals before a pooled rate; do not substitute an unweighted average. Distinguish
  percentage points from relative change, missing from zero, and an undefined
  denominator from a defined rate. Round only the displayed result.
- For supported monetary growth, every-region or declared ratio claims not already
  covered by a matching executed tool calculation, run
  `<skill-directory>/scripts/check_numerical_claims.py` with original inputs.
  For CSV use its explicit column/unit/population mapping. Preserve source hashes
  and inspect each claim's result. Other new arithmetic needs separate calculations;
  do not rename a metric or rewrite the population to fit a helper.
- For changed sources, use `--previous-source` when applicable and inspect both
  historical and current results, including unavailable sources. Revisit affected
  prose and recommendations; retain valid independently supported claims.
- Check row membership, identities, duplicate/revision rules and join cardinality
  when the result depends on them. Equal totals do not prove equal membership.
- Reconcile every explanation against the final figures: comparison direction,
  favourable/unfavourable, units, dates, median versus mean, causal claims and
  counts of correct or incorrect audit claims. When a category's members or a
  variance's cause are unknown, do not invent examples or explanations.

For an audit, confirm correct figures as well as correcting errors. A correct
input is still correct when the aggregation method is wrong. Preserve conditional
statements that do not assert an unknown condition holds. Give individual verdicts
before an overall summary. For a direct calculation, return the result, useful
working and material limits; do not add an unsolicited report or generic advice.
