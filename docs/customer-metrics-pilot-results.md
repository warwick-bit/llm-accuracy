# Customer-metrics executable-check pilot: results

**The executable checks expose the authored SQL defect. The Claude comparison
is inconclusive.** Deliver the runnable example; do not promote a new reviewer
or claim an accuracy improvement from this pilot.

## Deterministic result

The [public upstream query](../examples/customer-metrics-review/upstream_customers.sql)
and [locally authored alternative](../examples/customer-metrics-review/joined_customers.sql)
were executed against the same fictional staging snapshot. The independent
Python reference, not either model verdict, owns the expected values.

```text
Customer  Reference orders  Alternative orders  Payment value (both, AUD)
100       2                 3                   90
101       1                 1                   70
102       NULL              NULL                NULL
```

Both implementations retain unique customer rows, complete customer membership
and the same payment values. Those checks alone would approve the defective
implementation. The independent per-customer comparison catches its inflated
order count. Splitting one payment while preserving its total changes the
alternative's order count again, violating the stated invariant. The upstream
query passes all checks. The [typed report](validation/customer-metrics-deterministic.json)
and [tests](../tests/test_customer_metrics_example.py) preserve this evidence.

This is an authored mutation of an existing public SQL artifact, not discovery
of an upstream defect. Only the three known dbt refs are replaced for SQLite.
This proves behavior on the supplied fixture, not production correctness, full
SQL dialect compatibility or a finance policy. The Apache-2.0 license and source
revision/hash are included with the example.

## Model comparison outcome

Frozen pilot source: `eec3961`; plugin 0.6.2; requested/observed model
`claude-sonnet-5`, high effort. The first call used existing guidance and the
correct query. Its runtime completed, with exact tool/MCP/plugin counts,
successful UserPromptSubmit fidelity hook and matching final usage model.
Its final answer did not satisfy the required JSON contract (`answer_shape`).

The [incomplete receipt](validation/customer-metrics-control-incomplete.json)
contains one unscored process failure. No paired comparison completed. The
receipt-assisted control and both defective-query arms were not attempted.
There are zero scored quality results; neither a false positive nor a missed
defect may be inferred from the formatting failure. The failure was not retried
or normalized after seeing it, as specified in the [contract](customer-metrics-pilot-contract.md).
Raw model answers were not saved, so no more specific failure cause is claimed.

Both arms were designed to receive the same source snapshot and executed SQL
output. Only the treatment would additionally receive the checker report. This
would measure interpretation of delivered check evidence, not whether an agent
can select/run the checks or perform a natural free-form review. The proposed
constrained fields also do not measure explanation quality or extra findings.

## Decision

Keep the practical investment at the executable-check layer: explicit metric
definitions, independent reference calculations and invariants. Here they
reproducibly reject the faulty implementation while accepting the correct one,
without model calls. This is demonstrable regression-test value, not evidence
that they make Claude more accurate or that this pattern fits every domain.

The example is directly runnable with Python's standard library. It is outside
plugin packaging; no new skill, hook, permission, dependency, provider adapter
or installed configuration is added. [Run it](../examples/customer-metrics-review/README.md).
Use authorised real-work fixtures and independently approved definitions before
applying it to company decisions.

## Review and validation

Independent pre-spend review verified the source counts/payment totals, found
a variant-label cue and identified insufficient hook/model attestation in the
reused launcher. Packets now remove the cue, and a pilot-local sequential
wrapper checks actual successful hook events and final model usage. Regression
tests reject the prior false-pass trace and ensure the wrapper restores the
parser after failure. Distributed launcher code is unchanged.

The 33 focused tests include both SQL checker negatives and model-output scorer
negatives; all pass. The complete local repository suite passes 538 tests.
Ruff, JSON parsing, plugin Python compilation and all three distribution
boundaries pass. These gates do not convert the incomplete live comparison into
quality evidence.
