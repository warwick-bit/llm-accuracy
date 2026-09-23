# Follow-up analytical-review comparison

The frozen first pass shows **no incremental verdict/value or explanation gain
from the candidate prompt**. All arms miss the same underdetermined FX claim.
This is not proof of equivalence or a general accuracy estimate.

A later [free-form comparison](analytical-review-everyday-results.md) removes
the reviewer-facing claim schema and tests 0.6.1 guidance plus native hooks.
Its results are separate and must not be pooled with this study.

## First-pass results

The [first-half receipt](evaluation-results/analytical-review-challenge-first-half.json)
and [second-half receipt](evaluation-results/analytical-review-challenge-second-half.json)
contain eighteen review calls and eighteen separate judge calls. All completed,
with exact claim coverage and no runtime or judge failures. Both halves have
matching prompt, harness, calibration and rubric hashes. Requested and observed
model was `claude-sonnet-5`, high effort, CLI `2.1.280`. The same `telemetry`
host plugin was recorded for every reviewer and judge. The
[calibration receipt](evaluation-results/analytical-review-judge-calibration.json)
records fourteen matching controls.

```text
Arm                  Verdict + value  Sound explanations*  Exact ref IDs
Plain review         23/24            23/24                23/24
Audit text (0.5.3)    23/24            23/24                12/24
Candidate reviewer   23/24            23/24                13/24
```

Each arm matches every required verdict/value in five of six packets. The only
miss is claim b3, the realized-FX evidence gap. Every arm supplies a non-null
value and a non-unresolved status there. All other numeric results and claim
statuses match. These are not counts of fully correct reviews.

*Explanation grades are model-assisted. The judge also flags unsupported
additions in one plain-review answer and ignored conflict in one plain-review
and one candidate answer, all in the FX packet. Other global flags are absent.
These are grader observations, not independently established source-conflict or
false-claim findings. In particular, the packet contains a missing accounting
basis, not a simple pair of contradictory ledger totals.

Exact reference-ID checks fail on at least one claim in packets a/d/e, with
between-arm differences. They enforce the requested source-key naming contract;
they do not distinguish a harmless path/alias from a nonexistent source. Raw
reference strings were not retained, so these failures are not retrospectively
normalized or called fabricated citations. Treat them separately from correctness.

```text
Arm                  Review seconds  Judge seconds
Plain review         268.1           75.5
Audit text (0.5.3)    305.7           108.4
Candidate reviewer   311.5           112.7
```

These are summed observed elapsed times for six calls per arm, not stable speed
estimates. No monetary cost or confidence interval was measured.

## Repeats and stability

An [unchanged FX repeat](evaluation-results/analytical-review-challenge-fx-repeat.json)
across all three arms returned every required verdict/value correctly, with
all four explanations per arm graded sound and all global flags absent.
Each arm failed the missing-basis claim once and handled it correctly once.
Prompt/harness/rubric/calibration hashes and recorded runtime settings match the
first pass. This is observed run-to-run variation, not evidence of a prompt fix.
The original failures remain in the record; repeat outcomes are not substituted
for them or pooled into a general accuracy percentage.

The finance repeat and the source-reference repeat ran as separate overlapping
case groups. Their elapsed times are not used for comparative latency claims.

The [source-reference repeat](evaluation-results/analytical-review-challenge-reference-repeat.json)
reruns packets a/d/e across all arms, with unchanged prompts and fixtures:

```text
Arm                  Verdict + value  Sound explanations*  Exact ref IDs
Plain review         12/12            12/12                5/12
Audit text (0.5.3)    12/12            12/12                4/12
Candidate reviewer   11/12            11/12                0/12
```

All nine review/judge pairs completed. Reference naming remains unreliable in
all arms; the saved observations do not establish a semantic citation defect.
The candidate additionally misclassifies claim d4, an unsupported causal claim,
while returning its required null value. Its explanation is graded unsound.
It handled this claim correctly in the first pass. The other two arms handle
it correctly in both completed runs. This is an observed candidate failure and
variation, not an estimated persistent regression rate.

An attempted further all-arm replication of packet d was stopped after the
first call exposed an unexpected `agents-md` host plugin alongside `telemetry`.
The [rejected run fragment](evaluation-results/analytical-review-challenge-rejected-causal-repeat.json)
records that call as an inventory/process failure, not a scored answer. The
following in-flight audit call was interrupted and the candidate call was not
attempted. No quality denominator includes any of these calls, and no retry
with a widened plugin allowance was treated as equivalent. Consequently, the
candidate's new causal-claim error remains unreplicated after its discovery.
The thirty completed review/judge pairs used only the originally allowed host
plugin; fourteen separate calibration calls preceded them.

## Conclusion and release position

Keep the reviewer experimental. The extra instructions have not earned an
accuracy-upgrade claim over plain review with the same evidence, tools and
claim contract. The first pass ties; the missing-input error varies across
runs; a later candidate-only causal-classification failure and reference-name
noncompliance provide additional reasons to withhold promotion. No candidate
advantage remained to validate with the verbosity placebo, so it was not run.

The prototype provides a named, separate-context interface for supplying
artifacts, requirements and authorized checks. Native invocation was observed
in the earlier 0.5.3 smoke; model integration was not rerun after incorporating
0.6.0 because the host inventory had drifted. Convenience and context separation are not measured
accuracy improvements. The [usage guide](analytical-review-usage.md) explains
its purpose alongside claim fidelity and self-audit.

The practical direction is explicit definitions, counterexamples and executable
reconciliations around material claims. This study holds those facilities equal
and therefore does not estimate their independent benefit. It also does not
validate real-company work, every SQL dialect, accounting-policy selection or
production-system correctness. Further superiority claims require independently
adjudicated work and a stable, attested host; simply adding more review prose
has not justified them here. No release or installed-plugin change is proposed.

## What this comparison measures

The [frozen contract](analytical-review-challenge-contract.md) compares the
unchanged reviewer prompt, the base plugin's existing audit instruction bodies
and a plain review request. Every arm receives the same explicit claim-review
contract, fresh context and synthetic evidence/query/calculator tools. This
isolates incremental prompt effects within that setup. It does not compare
native installed hooks, Anthropic's GitHub Code Review product, or an everyday
freestyle conversation without those facilities.

The audit arm uses version 0.5.3's instruction bodies. PR #31 merged version
0.6.0's broader technical guidance while this frozen experiment was running.
It is not silently substituted into these comparisons. Reproduce the historical
experiment from [source snapshot 2afd89f](https://github.com/warwick-bit/llm-accuracy/tree/2afd89f),
which contains the tested prompts, cases and harness. Running the same commands
on newer source may measure a different audit arm. Neither the native 0.6.0
hooks nor the user's installed configuration were compared here.

There are six newly authored packets, four claims each: offsetting join errors,
cash/revenue/run-rate and FX distinctions, stale event ordering, cohort boundaries,
retention denominators, and a correct concurrent-update trace. References use
SQLite, Decimal arithmetic, explicit event simulation and supplied definitions.
Mixed correct and unresolved claims test over-application as well as detection.
These small, author-exposed cases are not a representative workplace sample or
an independent holdout. Claim outcomes within one packet are correlated.

Status/value matches and review coverage are deterministic measurements.
Explanation grades and global flags come from a separate, arm-blinded Claude
call. They are model-assisted supporting evidence, not human-established truth.
The judge passed all fourteen authored calibration controls before review calls,
including wrong reasoning with correct numbers, equivalent paraphrases,
unsupported assertions, execution claims and source conflicts. That does not
establish its real-work precision. Raw reviews and observations pass to the
judge in memory only; saved receipts contain typed outcomes and hashes.

The reused runner also emits legacy top-level `observed_verdict` and
`reason_bytes` fields. Multi-claim answers have no top-level verdict or reason,
so these are null/zero and are not measurements of the nested explanations.
Use `claim_results` and the separate `explanation_grades` fields here. Reference
ID validity checks names only; it does not prove that a citation supports a claim.

## Interpreting the FX case

The packet supplies a revenue/run-rate translation rate and a bank conversion
rate, but does not establish the receipt's transaction or carrying basis.
Those two rates alone cannot establish its realized FX gain. A returned numeric
value therefore fails the required unresolved/null reference, independently of
how persuasive its explanation sounds.

After the first failures, an independent oracle review, without access to live
receipts, confirmed non-uniqueness: hypothetical carrying rates of 1.10 and 1.20
produce different outcomes. Neither is supplied. “No other entries” does not
establish which basis applies, or whether a receivable existed. An acceptable
explanation may describe missing transaction/settlement basis without using the
gold rationale's receivable wording. The fixture and reference stayed frozen.
The [research notes](analytical-review-research.md) record the subsequent source
check and its limits; the fixture is not an accounting-standard compliance test.

## Reproduction

Run the offline tests before spending subscription capacity:

```bash
python3 -m pytest tests/test_review_challenge.py tests/test_review_eval.py -q
python3 scripts/calibrate_review_judge.py --judge-model claude-sonnet-5 \
  --allow-host-plugin telemetry --output /tmp/review-calibration.json
python3 scripts/run_review_challenge.py --model claude-sonnet-5 \
  --judge-model claude-sonnet-5 --allow-host-plugin telemetry \
  --calibration /tmp/review-calibration.json --cases packet-a,packet-b,packet-c \
  --output /tmp/review-first-half.json
python3 scripts/run_review_challenge.py --model claude-sonnet-5 \
  --judge-model claude-sonnet-5 --allow-host-plugin telemetry \
  --calibration /tmp/review-calibration.json --cases packet-d,packet-e,packet-f \
  --output /tmp/review-second-half.json
```

The live harness requires Linux/WSL, the local Claude executable and file-based
subscription authentication. It provides no API fallback and does not run in
CI. Verify receipt model identities, binary, prompt/case/harness hashes and
runtime inventories before pooling runs. The recorded host telemetry allowance
does not establish a completely plugin-free baseline. Review and judge time are
separate; elapsed observations are not stable latency or monetary-cost estimates.
