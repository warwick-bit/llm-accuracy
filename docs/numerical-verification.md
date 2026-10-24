# Check a numerical report against its sources

This optional local workflow helps an assistant check a report using the supplied
source files. It requires a host that can read files and run Python 3.9 or later.
It is experimental and is not an installed Claude plugin.

Ask the assistant:

> Check this report against these sources using this workflow. Correct supported
> errors, keep useful valid wording, and explain what remains unchecked.

## Workflow for the assistant

1. Establish the authoritative source, metric, currency, periods and included
   population. Preserve original files. Missing values are unknown unless the
   source defines another treatment. If definitions conflict, describe the
   conflict instead of choosing silently.
2. Read the whole report. Retain each material original claim in a short audit,
   including side claims and non-numerical conclusions. Explain its disposition.
   When translating prose to a checkable statement, record the original and the
   interpreted meaning together. Splitting a compound sentence does not verify
   its unchecked clauses.
3. For total revenue growth or an every-region increase, use
   `scripts/numerical_claims_demo.py`. Prepare a derived JSON snapshot only when
   the raw source supplies the required definition and complete population.
   Preserve the raw-source filenames and SHA-256 hashes alongside the derived
   inputs and results. Check the conversion against the source rows; a helper
   result only validates what it was actually given.
4. Execute the helper and inspect each result. `supported`, `contradicted` and
   `not_verified` are different outcomes. Unsupported wording is not necessarily
   false. Identify any separate calculation and its source rather than attributing
   it to the helper. Do not infer causes, source authenticity or complete-report
   correctness from numerical agreement or exit code zero.
5. Save the corrected report, concise claim audit and execution evidence. Rerun
   relevant checks on the final text/derived claims and after source changes;
   retain earlier results as historical. Keep unresolved material claims visible.
   Record the working directory for each reproduction command and make every
   relative path resolve from that directory.

## Helper input and scope

Run with the working Python executable on the current host:

```text
python scripts/numerical_claims_demo.py source.json claims.txt
```

`source.json` contains `metric: "revenue"`, one `currency`, a nonempty unique
`population` of regions, and `values_cents` mapping each selected `YYYY-MM` to
exactly those regions and signed integer-cent values. Do not drop missing regions
to make the population appear complete. Incomplete data remains unverified.

`claims.txt` has one complete claim per line. Recognized forms are:

```text
Total revenue growth was 12% from 2026-08 to 2026-09 in AUD.
Revenue increased for every region from 2026-08 to 2026-09 in AUD.
```

The dates, currency and percentage can vary. Case and whitespace variants are
accepted. Growth needs a positive starting total and rounds to the displayed
zero to two decimal places, with ties away from zero. The regional claim requires
every included region to increase strictly. Other forms remain unverified.

The JSON output preserves each line and binds the exact supplied source, claims
and checker bytes. It does not bind a model's interpretation to the raw source
or prove that all material report claims were selected. Those remain explicit
audit responsibilities. Exit 0 means execution completed; exit 2 means an
input/execution error. No whole-report pass or guarantee is provided.
