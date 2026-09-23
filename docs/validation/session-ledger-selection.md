# Session Ledger restore selection: bounded synthetic comparison

Run `python3 scripts/measure_ledger_restore_selection.py` from the repository.
The comparison passes the same synthetic 16-entry history to the shipped
newest-first renderer and a simple alternative reserving one quarter of the
entry budget for the oldest entry. No real transcript, model output, or customer
content is used. Each case declares its required markers before scoring.

```text
Case                 Required  Newest retained  Oldest-quarter retained
Older constraint            1                0                        1
Latest correction           1                1                        1
Recent constraints          4                4                        3
```

Both outputs fit the serialized host limit. The script checks exact marker
presence only: the “latest correction” case marks the newest entry as required;
it does not test semantic correction resolution or model comprehension. Storage
and entry sizes are held constant. No summary is supplied, isolating entry
selection from summary coverage. The cases are constructed counterexamples,
not a representative sample, and must not be aggregated into an accuracy score.

The comparison rejects the claim that always reserving space for the oldest
entry is strictly better. It also demonstrates that newest-first can omit an
older constraint. Keep the production policy unchanged pending broader evidence.

A future policy needs predeclared older-decision, recent-correction, withdrawal,
multiple-constraint, summary-duplication, and escape-heavy cases; equal serialized
budgets; and checks against stale fact promotion. Model recall would require a
separate controlled experiment. Neither this comparison nor the continuity
regressions establish improved LLM accuracy.
