# Analytical reviewer evaluation contract

This is an exploratory, synthetic comparison, not a claim of general accuracy
improvement. Freeze the candidate and case inventory before live evaluation.

## Hypothesis and scope

An explicit method-review workflow may improve detection of data, calculation
and systems defects over default review and the existing accuracy workflows,
without increasing objections to correct work or inventing missing values.
Alternatives: the existing audit is sufficient; prompt length alone explains
any difference; execution access is the limiting factor rather than wording.

The unit is one synthetic review case in a fresh Claude session. This measures
instruction effects in fresh context, not the causal benefit of fresh context
over self-review in an implementation conversation. SQL is SQLite, financial
definitions are supplied, and systems cases are bounded event traces. This does
not validate production databases, accounting policy or an entire architecture.

## Arms and controls

- `default`: a plain request to review the supplied work.
- `audit`: current claim-fidelity and self-audit skill bodies plus evidence doctrine.
- `reviewer`: the proposed analytical-review skill body.
- `placebo`: generic review guidance padded to the candidate's word length;
  used only if the main comparison shows a candidate advantage.

Use the same requested Claude model, effort, evidence, tools and output contract
in every arm. The audit arm is explicit workflow text, not an assertion that
installed hooks fired. Native plugin loading is checked separately; a directory
load is not a marketplace installation or release smoke.
Use local Claude subscription authentication, no API-key fallback, fresh temp
working directories and config isolation. Record requested and observed model
identities where exposed by the runtime. No raw answers or transcripts are
stored by the harness; public cases and aggregate/typed results are synthetic.

## Cases, truth and scoring

Cover SQL joins/NULLs/cohorts, financial weighting/cash/accrual/FX, and systems
identity/retries/completeness. Include defective, supported and underdetermined
work in each domain. Development and untouched evaluation cases are separated.
The latter are author-exposed synthetic cases, not an independent holdout. The reviewer
can access only the public case fixture through a narrow local tool; it cannot
read answer keys, scoring code or other arms' outputs.

Truth comes from executable SQLite queries, Decimal arithmetic, exact set or
event-state computations and explicit missing inputs. A verdict is insufficient:
score required corrected values and evidence-grounded explanations separately.
Scoring structure is not semantic verification. The automated scorer does not
judge explanations; its results must not be called fully correct reviews or
used to claim overall superiority. A later blinded explanation audit is needed
before any such claim. A correct number with a false explanation remains
outside the automated score's coverage.
Run wrong-value, omitted-finding, false-positive, unknown-value and malformed
negative controls through the scorer before a live run. Failed or incomplete
model calls are process failures, excluded from quality denominators and shown
separately. Never treat a timeout as a clean review.

## Run sequence and decision rule

Independent design review precedes model calls. Start with a plumbing smoke,
then a stratified development rung across the domains and verdict classes.
Inspect signal before expanding. Freeze any revised candidate before evaluation;
never tune to evaluation answers. Pair runs by case and alternate arm order.
Repeat paired cases if verdict instability could change the conclusion.

Keep the candidate as an unreleased experiment while material false findings
and explanation quality remain unmeasured. Promote it only after inspection
establishes no new material false finding or unsupported correction.
Claim an observed advantage only on complete paired cases with more fully
correct reviews, no additional clean-control false alarms, and a passing
verbosity-placebo comparison. Report counts and case coverage, not a universal
percentage improvement. A ceiling/null remains a null; do not manufacture lift.
If the candidate regresses, revise on development cases or withhold the feature.
Rollback is removal of the opt-in skill; existing hooks and audits stay intact.

## Work plan

- Inspect current plugin contracts, contribution rules and overlapping work.
- Implement the small optional reviewer and synthetic executable fixtures.
- Independently review the design; prove scorer controls and tool isolation.
- Run paired live comparisons in bounded rungs; reconcile findings to truth.
- Run native skill directory-load smoke, local release gates and a fresh review.
- Publish bounded validation evidence with a draft PR, without releasing or
  changing the user's installed plugin during the experiment.
