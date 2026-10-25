# Mathematics and proof boundaries

For supplied datasets, use a small reproducible Python or SQL calculation that
matches the requested metric. The packaged revenue helper covers only its two
documented forms. Do not rename churn, retention or other measures as revenue
to obtain a checker result. No solver installation is needed for ordinary data
analysis.

## Check the metric actually being reported

- Bind a consequential rate to its numerator, denominator, population, period
  and definition. Count sessions, accounts or people according to that definition.
  A same-sized cohort is not necessarily the same set of subjects.
- Check the load-bearing aggregation or join against source rows: key uniqueness,
  expected join cardinality, excluded/missing records and observation coverage.
  Choose the checks relevant to this query; do not generate a universal battery.
- Compute ratios from totals where the metric requires that; an unweighted mean
  of subgroup percentages can answer a different question. A zero denominator is
  undefined unless an agreed convention applies. Missing data is not zero.
- Use integer counts/cents or exact rational/decimal arithmetic when appropriate.
  Retain unrounded values and apply the declared display rounding at the end.
  Numerical tolerances for approximate algorithms need a justified scale; avoid
  treating rounding differences as substantive failures.
- Check a consequential result through an independent calculation or invariant
  where useful: a separate grouped query, a hand-checkable subset, or a reconciliation.
  Reprinting an existing result or asserting it against itself is not independent.
  State when a spot check covers only a subset.

For example, an earlier rate of 24/120 = 1/5 and a later rate of 15/150 = 1/10
give a change of -10 percentage points and -50% relative to the earlier rate.
This proves the arithmetic of those
given counts; it does not prove their completeness, source truth, causation or
applicability to another population. Python's standard-library `fractions.Fraction`
can check those equalities without binary-float rounding.

Check the final table, chart labels, narrative and closing chat against the
verified result. A short caption or handover must preserve material scope and
uncertainty. An observed improvement after two changes does not establish that
either change, or their combination, caused it. Keep proposed, approved and
executed actions distinct when summarising a decision.

Keep the visible result easy to read: lead with the answer, use a small comparison
table when useful, and state only material gaps and the next action. Save detailed
calculations/evidence when requested or needed for reproduction; do not turn
every reply into an audit report.

## Temporal data and predictive claims

Use these checks when the question depends on historical coverage or prediction:

- Test observability against the metric's actual measurement window. Missing
  early history does not invalidate a later retention window that is fully
  observed; conversely, a few observed days do not establish a complete window.
- For an as-of feature, distinguish event date, record availability and mutable
  profile state. An old event date alone does not prove the feature was knowable
  then. Exclude or qualify future registrations/profile attributes; label
  historical replay as retrospective when arrival-time evidence is absent.
- Keep training, model/threshold selection and held-out evaluation distinct;
  training labels must have matured by the simulated fitting date. Selecting a
  policy on the test set makes its result retrospective selection evidence,
  not an independent estimate of future performance. State the actual lead-time
  range and retain material calibration or validation-to-test deterioration.
- Compare models only on aligned populations, labels and evaluation protocols.
  Report an appropriate simple baseline; accuracy alone can reward predicting
  the majority class while finding none of the events of interest.

Reuse existing calculations and evidence. These checks neither require retraining
a model nor establish future performance or causal business impact.

## Explore plausible failures with tools

For a consequential result, actively look for cases that could change it. Use the
model to design alternatives and interpret counterexamples; use code or queries
for repeated calculations. Start with the few uncertainties that matter most.

- State the property or decision being checked and the assumed domain. Explore
  relevant join multiplicities, missing or duplicate records, time boundaries,
  zero/negative values, rounding, or competing definitions; this is a menu, not
  a required checklist. Keep alternative definitions labelled as scenarios.
- Reuse the actual calculation and existing tools. Compare with an independent
  calculation, invariant or reference where useful. Multiple versions that share
  the same unsupported assumption do not establish correctness.
- For a small finite domain, enumerate it when practical. Otherwise choose
  targeted boundaries or reproducible generated cases, recording the seed when
  randomness is used. Keep synthetic defects in disposable inputs, never sources.
- Reuse aggregates and decisive counterexamples. Set a time or compute bound
  before expensive exploration; stop when the important uncertainty is resolved
  and essential checks pass, or the bound is reached. Explain any remaining gap.
  Retain a small regression check only when a verified failure warrants it.

Report the result, any decision-changing sensitivity, and what was actually
checked. Sampled/generated cases are empirical evidence; exhaustive enumeration
covers only its declared finite domain. A formal claim needs a checked proof
under explicit assumptions. None of these establishes source truth or causation
by itself. Avoid a new framework or a large permanent test suite for exploration.

## Small example: a check that catches a broken join

For a consequential check, confirm that it runs on a valid case and rejects a
small, deliberately broken case for the intended reason. This example's contract
is narrow: enriching payments with customer attributes must retain every payment
exactly once, with its original amount. It assumes one matching customer row per
payment and no intentional filtering. Other joins need their own contract.

Run this fictional example with Python's standard-library SQLite. It creates only
an in-memory database; never introduce the deliberate defect into real sources.

```python
import sqlite3

db = sqlite3.connect(":memory:")
db.executescript("""
CREATE TABLE payments (payment_id INTEGER PRIMARY KEY, customer_id TEXT, cents INTEGER);
CREATE TABLE customers (customer_id TEXT, region TEXT);
INSERT INTO payments VALUES (1, 'A', 1000), (2, 'B', 2000);
INSERT INTO customers VALUES ('A', 'North'), ('B', 'South');
""")

def checked_total():
    source = db.execute("SELECT payment_id, cents FROM payments").fetchall()
    joined = db.execute("""
        SELECT p.payment_id, p.cents
        FROM payments AS p JOIN customers AS c
        ON p.customer_id = c.customer_id
    """).fetchall()
    expected = sum(cents for _, cents in source)
    actual = sum(cents for _, cents in joined)
    if sorted(joined) != sorted(source):
        raise ValueError(
            f"Payment rows changed: joined total {actual}; source total {expected}"
        )
    return actual

print("Valid join:", checked_total())  # 3000
db.execute("INSERT INTO customers VALUES ('A', 'North')")
try:
    checked_total()
except ValueError as error:
    print("Broken join detected:", error)  # joined 4000; source 3000
else:
    raise RuntimeError("The check missed the deliberate duplicate")
db.close()
```

Comparing payment IDs, amounts and multiplicity also avoids accepting offsetting
omissions and duplications merely because totals agree. This tiny example loads
rows into memory; use suitable SQL cardinality/reconciliation checks for large
data. It does not validate customer attributes, source truth or a business metric.
It demonstrates two executed cases, not a formal proof or complete join coverage.
For real work, run the relevant check against the actual reporting query and bind
its result to the input and code versions used. Do not create a separate test
framework or repeat this demonstration for every routine calculation.

The check-execution and deliberate-defect approach is informed by
[OSS Verify's coverage and mutation guidance](https://github.com/theorem-labs/oss-verify/blob/main/.claude/skills/add-project/SKILL.md#33-show-that-each-check-runs).
This example is standalone and does not enroll a project or invoke that service.

## What a proof establishes

Separate four questions: are the source and definition appropriate; is the
calculation correct; do the outputs faithfully present it; does a reader receive
one coherent output version? Success at one layer does not establish the others.

A formal proof needs a precise property, model and assumptions, plus a checked
argument or actual proof-tool result. Report the tool run and its scope when one
is used. Generated proof-looking prose, a structural receipt, a passing assertion
or a solver result for a different model does not prove a real-world claim.
Use a solver only when a general property warrants it and the environment allows
it; do not add one just to compute a dataset's percentages.

## Optional publication example

`../examples/publication_demo.py` is an explicitly invoked, standard-library
demonstration, copied from the repository's reviewed publication experiment.
It writes only to the output directory supplied by the caller. It is not a hook,
automatic report publisher or general-purpose storage service. Run it only when
the user wants to explore this publication contract, in a fresh disposable folder.

Its invariant is: a supported reader pins one generation identifier once, then
reads both validated documents from that immutable generation. Given immutable
generations and an atomic pointer switch, the reader cannot mix generations.
The earlier formal model checked this abstract publication property. That model
does not prove this Python implementation, financial truth, or arbitrary reports.

Assumptions: one writer, fresh generations, atomic local pointer replacement and
no mutation/deletion of generations still in use. Before a switch, an application
failure leaves the old coherent result; after a switch it may leave the new one.
A first-run failure may leave no result. Loose-file readers, concurrent writers,
power-loss durability and hostile edits are outside this contract. Consistent
output may still be stale or mathematically wrong.

Example input `invoices.json`:

```json
{"invoices":[{"customer":"C-10","cents":10000,"status":"issued"}]}
```

Using the actual installed example path:

```text
python "<plugin-root>/examples/publication_demo.py" refresh invoices.json demo-output
python "<plugin-root>/examples/publication_demo.py" read demo-output
```

The supported data is fictional issued/cancelled invoices, signed integer AUD
cents and a customer-labelled CSV table. The reader checks staged bindings and
hashes. It does not validate general narrative or a Kaggle analysis. Historical
private solver receipts are not distributed as proof of this installed package.
