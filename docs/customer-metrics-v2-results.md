# Customer-metrics follow-up: no incremental gain on this example

The revised, constrained-output comparison completed. Existing guidance and
existing guidance plus executed checks each correctly accepted the valid SQL,
rejected the authored defect and returned every requested reference value.

```text
Arm                        Correct query  Faulty query  Fully correct calls
Existing plugin            Pass           Pass          2 / 2
Plugin + executed checks   Pass           Pass          2 / 2
```

Four scored calls, two complete paired cases, one public SQL artifact and one
synthetic snapshot. The [typed receipt](validation/customer-metrics-v2.json)
records the complete population. Source was frozen at `a867541`; all recorded
source hashes were verified unchanged after the run. Requested and attested
model: `claude-sonnet-5`, high effort; plugin version 0.6.2.

## What changed in measurement

The [separate v2 contract](customer-metrics-v2-contract.md) adds a shared explicit
JSON structure example, accepts exactly one whole-answer JSON code fence and
records specific structural failure categories. It preserves the same expected
values, SQL, semantic score, treatment and runtime attestation. All four new
answers used a single fence. The [first pilot](customer-metrics-pilot-results.md)
stays unscored and separate: its original answer was not retained, so we cannot
identify its formatting fault or retroactively claim it would pass this parser.
No retries, model extraction or tuning occurred during this follow-up.

Scorer controls reject wrong verdicts, counts, payments, missing/duplicate
customers, incorrect NULLs, ambiguous/multiple JSON, duplicate keys and nonfinite
JSON constants. The independent design review found no concrete pre-spend
blocker. Its advisory remains: the illustrative verdict is a shared cue, and
this constrained format is not a natural review workflow.

## Decision and limits

Stop this example's model comparison at the observed tie. Executable checks
provide a repeatable regression guard, but they did not improve the scored model
answers here. The baseline was already at ceiling. This does not establish
universal equivalence or a stable failure rate; repeated-run variance, prose
explanation quality and additional unsupported claims were not measured.

The SQL fault is locally authored, not an upstream bug. Both arms receive the
executed SQL output; only treatment receives the check report. The study does
not test an agent choosing/running checks, real company data or general finance
and systems work. Do not pool it with the stopped pilot or earlier reviewer
experiments, and do not promote a new reviewer on this evidence.

The practical deliverable remains the standard-library executable example.
Any broader benefit claim needs different, independently grounded tasks with
headroom; repeating or tuning this all-pass example would not establish it.
No plugin implementation, installed configuration, release or permission changed.

## Validation

All 57 focused tests and 562 full local tests pass, as do Ruff, JSON parsing,
plugin Python compilation and all three distribution-boundary profiles.
These gates verify the implementation, not a model-quality improvement.
