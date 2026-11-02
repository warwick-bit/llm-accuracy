---
name: verify
description: Use before analysing supplied data, calculating figures or explaining numerical changes; before technical diagnoses or claims a fix works; and for requests to check or audit an answer or saved report. Includes 'verify your own previous answer', 'you said' and self-audits. Recompute figures and check all explanations. Apply to first outputs and later verification. Skip creative writing, pure translations and routine code changes without a material factual claim. Also use when someone asks whether a claim, figure or draft is right before it is sent, forwarded or shared.
---

# Verify

Use one workflow for accurate first answers and for checking an existing answer.

1. **Set the basis.** Identify the question, source and requested result. Reuse
   settled definitions, units, population, denominator, dates and source authority.
   If an unresolved choice changes the answer, use the host's interactive question
   tool before choosing; follow explicitly authorized assumptions or alternatives.
   Missing evidence stays unavailable; finish independently supported parts.
2. **Check the claims while working.** Re-derive them from the source. For numbers,
   use available execution to check every reported value and displayed equation,
   including explanatory working. Apply the relevant branch below. A helper checks
   only its declared forms; it does not approve sources or all prose. Resolve helper
   paths against this skill directory. Execute the applicable command below;
   reading this skill is not execution. Retain a check that could not run as a gap.
3. **Give the requested answer.** Include enough working to check it and only
   material limits. Stop when the question is answered. Do not add unrequested
   what-if calculations, speculative explanations, source-correction scenarios or
   generic advice. If asked why something happened, separate the arithmetic
   explanation from an unknown underlying cause.
4. **Reread against the source before sending.** Go sentence by sentence through
   the actual answer and any file saved this turn. Call each quantity by the
   source's own label, not a related metric or broader term. Keep a direction,
   cause, generalisation or every/all claim only if the supplied facts establish
   it; otherwise narrow it or say it is unknown. Judge a statement by its exact
   words, without strengthening or weakening it. A statement that the data does
   not indicate something is supported when the data gives no sign of it or
   explains the observation another way. Recheck each stated figure against the
   source.
   Correct the answer and file before sending.

Before sending, read the actual answer or final saved bytes. Check every material
claim, including explanations, examples, counts, recommendations and claims about
what is missing. Do not call an observed fact unavailable. Preserve correct claims
and valid conditional statements. Test implication separately from evidence that
its condition holds. For numerical conditionals, before the verdict identify
which inputs the exact condition leaves free; execute a calculation holding
the condition true while moving free inputs to permitted boundaries.
State the check's basis in the audit reason. A counterexample refutes the original
implication; classify it unsupported or incorrect. A passing example alone is
not proof: justify the invariant if affirming validity. Do not borrow extra
assumptions or freeze free inputs at historical values. A strengthened conditional
is separate from the original. Missing evidence for a premise alone does not
invalidate a valid implication.
Do not claim a decomposition depends on ordering without calculating both orders
for these source values; omit the caveat if it is unnecessary.
Unavailable evidence is not zero, absence outside the supplied source, or proof
of the opposite. Equal counts do not prove equal membership. An observed pattern
does not establish a cause, recurrence or future accuracy.

## Execute the relevant check

Use the actual absolute skill path supplied when this skill loads. Keep the task
working directory; use Read for references rather than changing into the plugin.
Invoke one direct command with a working `python`, not assumed `python3` or a
compound fallback shell command.

- **Numbers:** execute `python "<skill-directory>/scripts/run_checks.py" calculate
  --check "(2.6/2-1)=30%"`. Supply the equations you will actually report; repeat
  `--check` for more equations. A percentage RHS is a fractional rate, so the
  ratio `2.6/2` is130%, not30%. For rounded output add `--places` with its displayed
  precision. The helper supports literal + - * / and parentheses, not units,
  symbolic inputs or all mathematical forms; use separate executed calculations
  for unsupported forms. Map operands to original sources yourself.
- **Saved files:** after the final write, execute `python
  "<skill-directory>/scripts/run_checks.py" inspect report_v3.md delivery.md`,
  substituting the actual requested paths. Read its returned text and compare
  material claims with sources; repair and inspect again if needed. A Write
  acknowledgement saying the file is current or needs no reread does not perform
  this requested inspection. `inspected` proves byte access, not factual accuracy;
  formula `not_applicable` or a hash is not whole-report verification.

Use actual tool results to distinguish passed, failed and unavailable checks.
Do not label unexecuted checks as verified. These commands add no execution
permission. Follow required native hidden-process launching for this task.

## Apply only the branches the task needs

| Task | Read and apply |
|---|---|
| Figures, rates, averages, comparisons or numerical audits | [Numerical checks](references/numerical-checks.md). Check the reported equations as well as headline figures. |
| Technical incidents, code repairs or claims a fix works | [Technical checks](references/technical-checks.md). Reproduce or inspect the affected path, test competing causes and repeat the original check. |
| Check a previous answer, including your own | [Answer audit](references/answer-audit.md). Give per-claim verdicts, confirm correct claims and recheck the correction. |
| Saved reports, spreadsheets or generated revisions | [Saved-output checks](references/saved-output-checks.md) and [Answer audit](references/answer-audit.md). Inspect the delivered bytes and preserve source/output history. |
| Citations or quotations | [Citation checks](references/citation-verification.md). Check the source, quote and support for the claim. |
| Large consequential reports | [Report inventory](references/report-inventory.md), when useful; the inventory is optional bookkeeping. |

For a numerical-conditional audit needing a separate evidence pass, use the
[two-pass workflow](references/two-pass-audit.md) with the host's authorized
context and execution tools. The offline `scripts/evidence_handoff.py` binds
quotes, checks literal equations and limits the working passed into the full
audit. It never calls a provider or certifies semantic accuracy. Reuse existing
model-call authorization; keep unavailable independent execution as a gap.

For an audit, lead with individual verdicts before any count or overall conclusion.
Provide the corrected answer or file when requested. Deliver files through the
host's supported mechanism; a filename alone is not delivery.

Report tool/test/review execution from actual results, distinguishing attempted,
refused and completed checks. Do not claim a check ran or deny execution that did.
Only a technical incident diagnosis or code-repair handover needs a compact
Checked / Gap / Next footer. Ordinary numerical answers and other factual audits
need no generic footer; include a material limitation where it affects the result.

For a supplied evidence receipt, `scripts/validate_evidence_receipt.py` checks
structure only. Use `--expected-epoch` only with a caller-supplied current epoch.
Never infer evidence truth from a structural pass.

This advisory workflow supplies no source access, execution permission, external
integration or guarantee of correctness.
