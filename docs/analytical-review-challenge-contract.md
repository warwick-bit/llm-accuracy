# Frozen challenge comparison

This follow-up addresses the first rung's narrow cases, ambiguous verdict and
unmeasured explanations. The original results remain unchanged. The user
authorized further research and testing to reach a conclusion.

## Decisions fixed before model calls

- Compare the unchanged analytical-review skill with the same public baseline
  audit text and a plain review request, in fresh context with identical tools.
- All arms receive the same structured claim-review contract. Consequently,
  incremental effects are conditional on that contract; this is not a comparison
  against every everyday freestyle use of Claude.
- Six authored synthetic packets, four claims each, two packets per domain.
  Mixed correct, contradicted and unresolved claims; not every status appears
  in every packet. Authors know the cases. They are not an independent holdout.
- Reference numbers use SQL, Decimal arithmetic or an explicit event simulation.
  Claims distinguish intended metrics from actual implementation behavior.
  `refuted` needs contradictory evidence; mere missing support is `unresolved`.
- Score exact coverage and status/value matches separately. Omitted claim IDs
  are review coverage failures; malformed output or tool/runtime failures are
  process failures. Neither becomes an apparently clean review.
- Explain reasoning in unrestricted prose, then use an arm-blinded model grader
  to assess each explanation and global unsupported additions, fabricated
  execution, ignored conflicts and source-instruction compliance. The grader
  sees source, references, review and actual query/calculation observations;
  no arm, instruction prompt, deterministic score, latency or other run metadata.
  Grading is isolated per answer, so there is no shared arm order or conversation.
- Model-assisted explanation grades are supporting evidence, not independent
  human adjudication. `unjudgeable` remains visible. Never combine these grades
  and numeric matches into an invented universal accuracy score.
- Before review calls, require all fourteen synthetic, author-labeled grader
  controls to match: correct/paraphrased reasoning; plausible wrong reasoning
  despite correct labels/values; unsupported extra assertions; fabricated versus
  genuine execution; and preserved versus ignored conflicting sources. Untouched
  claims must remain sound. Some controls are reserved from rubric tuning, but
  none are hidden from the authors. Record hashes, CLI, model, effort and plugins.

## Run and stopping rule

First run the calibration, then packets a/b/c across all three arms. If runtime
and grading are complete, run the remaining d/e/f as the prespecified coverage
confirmation even if the first half is tied. This bounded continuation tests
distinct false-positive and boundary cases; it is not a search for favorable
examples. Preserve process failures and repair infrastructure before retrying.

Repeat every material between-arm discordance on the same case across all arms;
report first-pass and repeat observations separately. An apparent candidate
advantage requires an equal-length placebo follow-up. Do not tune the candidate
to these cases. A revision would require a separately frozen, fresh evaluation.

If deterministic outcomes and calibrated explanation checks remain comparable,
conclude that the additional reviewer prompt has not justified an accuracy-lift
claim on this suite. Distinguish the convenience of a named, fresh-context
workflow from better reasoning. A persistent regression warrants withholding
promotion. Better-than-default claims additionally need independent real-work
adjudication; a broad claim is not the goal of this small experiment.

## Provenance and scope

Cases are newly authored, not copied from benchmark datasets or external code.
Independent design review checked the packet calculations and exposed a missing
FX basis, calibration false-positive gaps and incomplete grader version binding;
these were fixed before model calls. Raw outputs and tool observations pass
between review and grader in memory only. Receipts retain typed outcomes and
hashes. No plugin release or installed configuration change is part of this run.
