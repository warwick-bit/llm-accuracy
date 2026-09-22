# Exploratory analytical-review results

The candidate has **not demonstrated an advantage over default Claude review**.
Keep it experimental. This is an instruction comparison on synthetic artifacts,
not a production accuracy benchmark or a release recommendation.

The [follow-up comparison](analytical-review-challenge-results.md) uses explicit
claim semantics, harder multi-claim packets and separately calibrated
explanation grading. This page preserves the original exploration and its
limitations; its scores are not retrospectively relabeled.

## Paired development rung

The [typed receipt](evaluation-results/analytical-review-development.json)
records three cases, one call per arm per case, using requested and observed
`claude-sonnet-5`, high effort, and Claude Code binary `2.1.280`.

```text
Arm                  Completed  Exact verdict + value  Elapsed total
Default              3          3                      47.5 s
Existing audit text  3          2                      68.1 s
Candidate reviewer   3          2                      93.2 s
```

All nine calls completed. All arms returned the correct total on the SQL join
case and the correct balance on the clean transactional retry case. All
withheld the unknown USD total when an approved exchange rate was absent.
The audit and candidate disagreed with the gold verdict on that missing-rate
case. Scores measure only the verdict and required value; explanations and
unsupported subsidiary claims were not adjudicated. These are not counts of
fully correct reviews.

The baseline was already at this narrow scorer's ceiling. Broader comparative
runs and the verbosity placebo were stopped: there was no advantage to validate.
Elapsed totals are descriptive observations, not stable latency estimates.

## Verdict ambiguity diagnostic

The original case asks to review a reported total but does not define whether
the verdict concerns numerical truth or the defensibility of presenting the
report as established. “Insufficient evidence” fits the first interpretation;
“needs correction” can fit the second. Independent design review identified
this ambiguity after the rung. The original gold and scores are retained.

An [unchanged repeat across all arms](evaluation-results/analytical-review-fx-diagnostic.json)
recorded the returned verdict enum: default returned `insufficient_evidence`;
audit and candidate returned `needs_correction`. All returned the expected null
value. This establishes a repeated classification difference, not its reasoning
or material severity. Raw explanations were not retained, and no retrospective
semantic pass was awarded. Future comparisons must define verdict semantics
equally for all arms and audit explanations before interpreting differences.

## Native integration smoke

The [positive directory-load smoke](evaluation-results/analytical-review-native-positive.json)
observed a successful invocation of `llm-accuracy:analytical-review`, a subagent
start and stop, evidence/query calls, and a correct final join-case verdict and
value. The [missing-skill negative control](evaluation-results/analytical-review-native-negative.json)
attempted the same invocation but did not succeed; it recorded no subagent
lifecycle or evidence calls and failed the integration criterion as expected.

This verifies successful skill invocation plus an observed subagent lifecycle.
The receipt does not causally bind individual child tools or the final parent
answer to the skill. An earlier direct-slash probe also observed a subagent and
queries, but did not satisfy the output parser; it is excluded from comparison.
No marketplace installation, Windows/Cowork host behavior, release or change to
an installed plugin is claimed.

## Boundaries and reproduction

Every comparison arm used fresh temporary context and the same synthetic
evidence, read-only SQLite and Decimal calculator tools. Runtime inventories
were checked: only those MCP tools and structured output were exposed. A
host-provided `telemetry` plugin appeared in all arms and was explicitly
allowlisted and recorded. This is not a verified plugin-free vanilla Claude
environment. The audit arm loaded the existing instruction bodies explicitly;
it did not measure native audit-hook behavior or the newer changes in PR #31.

Only three of the twelve authored fixtures entered the paired comparison; the
missing-rate repeat adds no new case coverage. The remaining fixtures were
checked by executable oracle tests, not live review calls. They are author-exposed
synthetic cases, not an independent holdout. No financial policy, production SQL
dialect, real data, large system or explanation-quality coverage is established.

The skill body and cases stayed unchanged between the paired rung and diagnostic.
Receipts preserve their hashes. Later harness changes added stricter parsing,
case selection validation and SQL allocation guards; the historic receipts are
not relabeled as runs of those later changes.

Run the offline controls first:

```bash
python3 -m pytest tests/test_review_eval.py -q
```

Live runs require a local Claude Code executable and file-based subscription
authentication. They consume subscription capacity and send the synthetic
fixture to Claude. The opt-in harness is Linux/WSL-oriented; it uses POSIX
process groups and an auth-only temporary profile. It does not run in CI and
is not bundled inside the plugin. No API-key fallback is provided.

```bash
python3 scripts/run_review_eval.py --model claude-sonnet-5 \
  --cases join-total,missing-fx,retry-safe --allow-host-plugin telemetry \
  --output /tmp/analytical-review.json
python3 scripts/smoke_analytical_review.py --model claude-sonnet-5 \
  --output /tmp/analytical-review-native.json
python3 scripts/smoke_analytical_review.py --model claude-sonnet-5 \
  --without-skill --output /tmp/analytical-review-negative.json
```

The negative-control command succeeds only when the integration criterion fails;
inspect its process status separately from its expected missing-skill result.
Choose a model available to your account. Model aliases and host versions can
change; compare the actual receipt identities before pooling results.
