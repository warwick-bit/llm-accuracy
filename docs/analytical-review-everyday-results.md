# Free-form analytical review comparison

**No demonstrated incremental accuracy gain.** Five fully paired first-pass
cases yielded 17/17 expected-claim matches for plain review and existing plugin
guidance, versus 15/17 for the candidate. The sixth case failed extraction twice,
including an unchanged recovery; planned quality repeats were not reached.
This incomplete development experiment does not establish equivalence or a
persistent candidate regression. Keep the skill experimental.

This study measures a plain Claude review, LLM Accuracy guidance plus native
hooks, and that same configuration plus the optional analytical reviewer.
Read the [frozen contract](analytical-review-everyday-contract.md) for scope and
the [earlier study](analytical-review-challenge-results.md) for separate history.

## Configuration and evidence boundary

Frozen source: `3656acd`; LLM Accuracy 0.6.1; requested and observed reviewer
and extractor model `claude-sonnet-5`, high effort. Six independently authored
synthetic artifacts span SQL/data, finance and systems, including three correct
work controls with explicit unresolved topics. Reviewers see natural artifacts,
not claim inventories, gold answers or an output schema.

The plugin arm explicitly receives claim-fidelity, verify-technical and evidence
discipline instructions, plus directory-loaded native hooks. The candidate adds
analytical-review instructions. This does not test automatic skill selection,
native subagent invocation, marketplace installation or the user's workstation.
The attested host plugin allowance is telemetry in every arm, plus llm-accuracy
in the two plugin arms; the default is not plugin-free.

[Calibration](evaluation-results/analytical-review-everyday-calibration.json)
passed all 19 authored controls. A separate arm-blinded model extracts claim
positions and numbers using numbered answer lines. Line existence and arithmetic
matching are checked in code; semantic interpretation remains model-assisted.
These are expected-claim matches, not counts of wholly correct reviews.
Extra findings, explanation quality and semantic citation entailment are not
measured. No human-adjudicated accuracy, confidence interval or cost estimate is
claimed. Cases are a small development set, not a hidden holdout.

## Measurement preflights

[Superseded typed receipts](evaluation-results/analytical-review-everyday-preflights.json)
preserve rejected and incomplete attempts. Initial host inventory and hook-name
assumptions were wrong. Calibration exposed ambiguous contradiction/scoped
approval controls; natural answers exposed fragile copied-excerpt checks.
The final configuration uses validated line references and at most one identical
retry for malformed extraction shape/coverage/references. Valid wrong grades and
runtime drift are never retried inside a call.

Earlier complete SQL and finance cases are descriptive only and are not pooled
with this protocol. No candidate domain advice or source evidence was tuned
after the initial freeze. Every measurement change required fresh calibration.

## Independent review

An independent case author reviewed case truth, scoring and the final data path.
Fable reviewed the design before spend; numeric representation and calibration
findings were fixed. The final line-reference change received a bounded
independent code review and offline integration checks. Model agreement does
not certify the scorer or the reviewer.

## Process failure and bounded recovery

The first pass stopped on the fencing control: plugin review completed, but its
extractor returned an invalid numeric field (`extract_value`). The remaining
two arms were not attempted, and this entire first-pass case is excluded from
quality comparisons. The [incomplete receipt](evaluation-results/analytical-review-everyday-clean-incomplete.json)
retains the failure. It is not scored as a plugin failure to review correctly.

After this failure, a single unchanged all-arm recovery was declared before
execution, alongside the prespecified repeats for between-arm differences.
This is a disclosed extension of the process-recovery rule, not a source fix or
new calibration. Configuration and prompts are identical; arm order rotates.
The recovery is reported separately and never substitutes for the first pass.
A further process failure ends this bounded run; no additional tuning or retry
loop is justified by the current lack of candidate advantage.

## Observed results

The [SQL smoke](evaluation-results/analytical-review-everyday-sql.json),
[defect rung](evaluation-results/analytical-review-everyday-defects.json) and
[incomplete clean-control rung](evaluation-results/analytical-review-everyday-clean-incomplete.json)
share exact source/configuration and calibration hashes. Five cases contain
all three successfully scored arms. Claims within a case are correlated.

```text
First pass: paired cases only  Claim matches  All expected claims matched
Plain Claude review            17/17          5/5 cases
LLM Accuracy 0.6.1              17/17          5/5 cases
Plugin + analytical reviewer   15/17          3/5 cases
```

The candidate's systems retry answer was extracted as correctly rejecting the
one-charge claim, but its extracted numeric correction did not match the
three-charge oracle after normalization. Its cohort answer was extracted as
omitting the mobile-only evidence gap while accepting the correct conversion
and boundary. These are observed scorer mismatches: raw answers were not
retained, so reviewer error cannot be separated retrospectively from semantic
extraction error. No first-pass scored arm rejected a listed correct claim.
That does not measure all possible false accusations outside the inventory.

The [recovery receipt](evaluation-results/analytical-review-everyday-recovery-incomplete.json)
records the same `extract_value` failure on the default fencing review. The
recovery stopped after that first arm; the other two arms and the prespecified
systems/cohort repeats were not attempted. All completed reviews remain counted
as runtime observations, but neither incomplete fencing case contributes to
quality denominators. There is no successful recovery to substitute or pool.

The final protocol completed 17 review calls: 15 scored pairs across five
complete cases, plus two fencing reviews with extraction process failures.
Nineteen authored calibration calls preceded them. Superseded preflights and
independent review calls are separate. All final-protocol extraction calls used
one attempt; the malformed-value category is intentionally not auto-retried.
The optional placebo was not triggered because no candidate advantage emerged.

## Conclusion and remaining work

The candidate supplies a named, separate-context review workflow, but has not
earned an accuracy-upgrade claim over plain Claude or existing plugin guidance.
The earlier structured study also found no gain; these studies use different
configurations and must not be pooled. The two candidate mismatches here are
unreplicated, and this run cannot establish their stability.

Automatic testing and packaging are feasible, but the evaluator is not robust
enough to serve as a promotion gate: one categorical systems case repeatedly
failed the numeric extraction contract. The typed receipts identify the failure
category, not which raw value caused it. Future evaluator work should validate
non-numeric claim handling and semantic extraction on separately adjudicated
examples before any new comparison. This is a future work item, not evidence
that the candidate would then improve.

No merge, release or installed-plugin change follows from this result.
Real-work benefit still needs authorized representative artifacts, independent
reference checks and an evaluator that handles the full prespecified set.

Main advanced to 0.6.2 (`66af41f`) during testing and was integrated after the
frozen comparison, without changing the experimental skill. The measurements
above apply to 0.6.1, not the newer plugin guidance or hooks. Reproduce them
from the frozen source commit; rerunning on current main changes the treatment.
Native subagent invocation with the integrated 0.6.2 build remains untested.

## Final adjudication and integration checks

The final independent review completed successfully using requested alias
`fable`, medium effort, with the full 62,919-byte evidence packet and no
truncation. Resolved underlying model identity was unavailable. It found no
blocking issue in the bounded conclusion, reconciled the case denominators,
and emphasized the uncompleted repeats and semantic-extraction limits.
Its examples of possible malformed categorical values or count representations
are hypotheses, not recovered facts about the raw answers.

The reviewer did not receive receipt JSON. The parent separately verified
telemetry-only host allowances, identical configuration/calibration hashes and
rung rotations against those receipts. This was conclusion/design adjudication,
not an independent review of every original answer or the complete PR.

After integrating 0.6.2, all 585 local tests passed; Ruff, JSON parsing, plugin
Python compilation, all three distribution boundaries and Claude plugin
manifest validation passed. These establish local packaging/test behavior,
not comparative performance or a clean native release installation.
