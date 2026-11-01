# Separate numerical-implication audit

Use this path for an existing answer containing quantitative if/then claims
when a separate evidence pass is needed, particularly after a repeated
implication error. Reuse an already authorized independent context when the
host provides one. Otherwise isolate the evidence pass in the current context
and state the independence gap; do not install integrations or switch profiles.
No script in this plugin calls a model, a provider or a network service.

1. Give the evidence pass the unchanged source and complete candidate. Include
   quantitative forecasts expressed without numerals. Separate premise evidence
   from implication validity. For an invalid implication choose admissible
   hypothetical inputs satisfying its exact premise but defeating the conclusion.
   For a valid one state its invariant and a numerical example. Do not strengthen
   premises, freeze free inputs at historical values or treat hypothetical inputs
   as observed facts. Keep valid controls; missing premise evidence alone does
   not invalidate a valid implication.
2. Save minimal JSON as `evidence.json`, with `checks` containing `quote` (an
   exact candidate excerpt), `verdict` (supported, qualified, unsupported,
   incorrect or unchecked), `scenario_inputs` (named numbers), `equations` (literal
   equalities with exact numerical results) and `invariant` (a short expression,
   or empty). Numeric arithmetic belongs on the left: `(2*3+4*5)/6=13/3`, not
   `result=13/3`. Omit explanatory paragraphs and repaired conditionals.
3. Execute `python "<skill-directory>/scripts/evidence_handoff.py" --candidate
   answer.md --evidence evidence.json --output claim-evidence.json` using the
   host's hidden native launcher on Windows. The output must be new. The helper
   drops commentary, binds quotes and executes every submitted equation. It
   refuses missing explicit English if-markers, failed/unsupported equations or
   malformed evidence. An implicit or non-English conditional still needs
   semantic review: this is not a complete language parser. If a clause cannot
   supply an applicable numerical check, leave this numerical path unavailable;
   do not invent a calculation.
4. Give the full audit the unchanged sources and complete candidate plus the
   compact working. Recheck source mapping, scenario admissibility and the
   implication independently. A passing example is not proof; a counterexample
   does not establish new necessary conditions. Preserve the logical force of
   original claims: absence of an adverse indication does not assert that
   deterioration is ruled out. An unmeasured fact can be a limitation without
   contradicting a narrower statement. Audit the other claims too.
5. Save and inspect the actual final audit. Check closing notes and explanations
   for new unsupported claims. Keep all complete numerical receipts; do not
   truncate output or infer helper success from a shell pipeline. A structural
   or literal pass is not source truth, scenario admissibility, complete claim
   coverage or semantic approval. Retain failures and material gaps.

The schema and generic stage instructions are also exported from
`scripts/evidence_handoff.py` for hosts that already have an authorized model
adapter. They grant no model-call permission and contain no provider client.
