# Free-form analytical review comparison

This separately frozen development experiment addresses the structured-baseline
limitation of the earlier comparison. It does not replace historical receipts.

## Hypothesis and scope

Adding the analytical-review instructions to current LLM Accuracy guidance may
improve material claim detection/correction without rejecting correct work.
The population is six newly authored synthetic artifacts, two per domain: data,
finance and systems. An independent case author did not inspect the candidate
or earlier cases. The parent inspected the references for correctness; this is
development evidence, not a hidden holdout or real-work accuracy estimate.

The product change only gives user-requested output formats precedence over
the skill's default verdict wording. No domain advice is tuned to these cases.

## Arms and environment

- Default: a short ordinary correctness-review request.
- Plugin: the current 0.6.1 claim-fidelity, verify-technical and evidence-discipline
  bodies explicitly supplied, plus real directory-loaded plugin hooks.
- Reviewer: the same plugin arm plus the analytical-review body.
- Placebo, only if a candidate advantage survives repeats: plugin plus generic
  review wording matched to the candidate's word count.

Every reviewer gets fresh context, the same source artifacts and minimal
read-only SQLite/Decimal tools, and no output schema or claim inventory. Neither
gold nor evaluator files are in the child workspace. Plugin source is copied
only into plugin-arm workspaces. Built-in tools and skill auto-discovery are
disabled; this measures explicit guidance plus native hooks, not all installed
skill selection, native fork behavior or an unrestricted everyday workstation.
The self-audit skill is not injected: this task reviews supplied work, not the
reviewer's own previous answer.

Requested review and extractor model: claude-sonnet-5, high effort. CLI binary,
all prompts, source and plugin bytes are hashed. The new frozen host allowance
is exactly telemetry, plus llm-accuracy for plugin arms. This is
not a plugin-free default; it does not rehabilitate the rejected historical
run. Exact tool/plugin/model inventories must match on every call. Real claim
fidelity hook output must occur once per plugin review and never in default or
extractor calls. Any drift is infrastructure failure and stops the rung.

## Measurement

A separate extractor receives only free-form review text, hidden claim topics
and whether a numeric target exists. It sees no source, gold answer, arm label,
prompt, scores or timing. It reports supported/refuted/unresolved/omitted/ambiguous,
a stated or explicitly endorsed number where applicable, and supporting numbered
answer-line references. Line IDs must exist and identify nonblank answer lines;
raw text is validated in memory and discarded.
Numeric targets specify units. The extractor labels explicit fractions, loss
magnitudes and counts of extra charges; the scorer converts only the compatible
target (percentage, signed profit or total charges). It never accepts both signs
indiscriminately. Calibration uses the same Decimal equality as scoring and
includes each representation, multi-claim attribution and omitted/established
topic controls to detect guessing from claim grammar.
This checks line existence mechanically, not attribution or semantic entailment. Extraction remains
model-assisted, not independent human adjudication.

Primary per-claim match: correct extracted status and, for a refuted numeric
claim, the correct explicitly stated correction. A supported number need not be
restated, but a stated wrong number fails. Record status, explicit-value coverage
and value checks separately. An omission is a coverage miss, not a process error.
Malformed extraction, invalid line references and host failures are process errors;
exclude the whole paired case from quality comparisons and report the failure.
Claims within an artifact are correlated; also report whole-artifact matches.

No root-cause/explanation-quality, extra-finding precision, semantic citation
support, monetary cost or generalized accuracy metric is claimed. Unsupported
objections against listed correct claims are visible as status failures; extra
objections outside that inventory are not fully measured. A candidate advantage
therefore warrants follow-up, not release promotion.

Before review calls, require every authored extraction control to match,
including wrong corrections, endorsement of wrong values, omission, negation,
paraphrase, formula without computed value, contradiction, injected instructions,
scoped approval, missing-data topics and categorical support. Local negative
tests must reject wrong values/statuses, missing IDs, invalid line references and
runtime inventory drift. Calibration is bound to the complete source/config hash.

## Rungs and stopping rule

1. Pass local oracles, scorer negatives and independent design review.
2. Calibrate the extractor; stop at the first mismatch or runtime failure.
3. Run all arms on the SQL defect case as the activation smoke. Stop on any
   process failure; inspect typed observations before proceeding.
4. Run the finance and systems defect cases (three-domain rung). If complete,
   run the three prespecified correct-work controls even if tied, because a
   defect-only comparison cannot measure false accusations.
5. Repeat each case with a between-arm primary discordance once across all arms,
   with rotated order. Report repetitions separately. Do not replace first
   outcomes, select favorable cases or tune to these results.
6. Only if reviewer beats both other arms on at least two distinct cases and
   retains those advantages on repeats with no new clean-control regression,
   run a paired placebo comparison on those cases. Otherwise stop the live
   comparison and report no demonstrated incremental advantage.

Maximum initial size is six cases by three arms. Each review has one extractor call, with at most one identical-prompt retry for
malformed shape, claim coverage or line references. Valid wrong extractions and
runtime failures are never retried within a call. Calibration and independent reviews are counted separately. Repeat/optional
placebo calls are bounded by the rules above. A failed infrastructure call may
be diagnosed and retried only as a new, documented configuration; never widen
allowances silently or pool unlike runs. No merge, release or installed-runtime
change is part of this experiment.

The runner aborts immediately on a process failure, preserving an incomplete
receipt. Earlier complete pairs remain descriptive observations; a case with a
missing arm is excluded. A repaired configuration requires fresh calibration
and a separately named rung, not rewriting the old receipt. The optional placebo
is provisional until independently reviewed; repeated filler alone cannot
establish content-specific benefit and must not support a promotion claim.

## Independent design review

The case author reviewed scorer semantics and identified numeric-restatement
bias and missing clean-control calibration. Fable then identified numeric
representation ambiguity, inconsistent calibration equality and absent
multi-claim controls. These were resolved before comparison calls. Fable's
claim that every unresolved item was a topic fragment was too broad (durability
was a proposition); additional topic-negative controls address the real cue risk.
Remaining limits include model-assisted extraction and unmeasured extra findings.

## Preflight corrections

Rejected and incomplete preflights remain separate from the final comparison.
They exposed a host inventory assumption, ambiguous calibration controls, copied
excerpt fragility and an assumed hook display name. The final protocol checks
successful UserPromptSubmit event/outcome/exit and fidelity marker, without an
invented name prefix. It uses line references instead of copied excerpts. These
are measurement/runtime changes; candidate advice and case evidence are unchanged.
Each source change requires a new calibration; unlike configurations are not pooled.
