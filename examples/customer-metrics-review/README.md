# Executable customer-metrics review example

A small, runnable example of testing a SQL analysis before trusting its result.
It is developer tooling and is not installed as part of any plugin.

The upstream customer model comes from [dbt Labs Jaffle Shop DuckDB](https://github.com/dbt-labs/jaffle_shop_duckdb/blob/36bde6cba69d962b83be1d52fc65a0dce1cb4ebb/models/customers.sql),
pinned in `provenance.json`. The original SQL is unchanged and its Apache-2.0
license is retained in `UPSTREAM_LICENSE`. The local renderer replaces only
three known dbt `ref` calls; this is a SQLite compatibility example, not a dbt
or DuckDB engine certification. The fixture and alternative joined query are
locally authored. **The alternative defect is not an upstream bug.**

## Run without an LLM or dependencies

From the repository root:

```bash
python3 scripts/check_customer_metrics.py --query examples/customer-metrics-review/upstream_customers.sql
python3 scripts/check_customer_metrics.py --query examples/customer-metrics-review/joined_customers.sql
```

The first command exits 0; the second exits 1 with failed reference and
payment-split checks. Exit 2 means a check could not run; never treat that as a
quality verdict. No model, provider account or warehouse connection is needed.
Queries run read-only on an in-memory synthetic database, with bounded execution.

## What it proves

The alternative query joins orders to payments before counting orders. One
customer has two orders but three payment rows. Its output retains one row per
customer and correct payment totals, yet reports three orders instead of two.
Uniqueness and total-money checks alone miss this error.

Two independent checks expose it:

1. Compute customer metrics directly from source entities in Python.
2. Split one payment into two with the same combined amount; customer metrics
   must remain unchanged.

Tests also reject duplicated/missing customers, wrong money, altered NULL
semantics and invalid source keys/relationships. The checker never promotes a
source-contract error to a pass. These checks cover this fixture and definition,
not arbitrary SQL, full production coverage or accounting policy.

## Applying the pattern to your own work

Write down the metric, grain, population, period, currency and NULL policy.
Create a small authorised fixture including the important edge case. Compute
expected results independently of the query. Add a change that should preserve
the answer, such as splitting a payment, and verify it does. Keep a correct
control and a deliberately broken implementation so the tests can demonstrate
that they discriminate. Ask Claude to explain failed checks and their limits.
Do not infer that passing a schema/uniqueness check validates the business metric.

## Optional receipt-assisted comparison

See [the pilot contract](../../docs/customer-metrics-pilot-contract.md). Both arms
receive existing LLM Accuracy guidance, the same SQL, contract, synthetic source
rows and observed query output. One also gets the executed checker report.
This is a constrained packet review, not a natural tool-enabled workflow.
