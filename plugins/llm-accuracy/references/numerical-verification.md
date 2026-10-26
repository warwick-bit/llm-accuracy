# Check a numerical report against its sources

This optional local workflow helps an assistant check a report using the supplied
source files. It requires a host that can read files and run Python 3.9 or later.
It is experimental. Use the optional verify-numerical skill on a capable host.
Here `<plugin-root>` means the installed package containing this reference; use
its actual absolute path in commands, not the literal placeholder.

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
3. For a supported monetary growth, every-region increase or declared ratio, use
   `<plugin-root>/scripts/check_numerical_claims.py`. Prepare a derived JSON snapshot only when
   the raw source supplies the required definition and complete population.
   Preserve the raw-source filenames and SHA-256 hashes alongside the derived
   inputs and results. Check the conversion against the source rows; a helper
   result only validates what it was actually given.
4. Execute the helper and inspect each result. `supported`, `contradicted` and
   `not_verified` are different outcomes. Unsupported wording is not necessarily
   false. Identify any separate calculation and its source rather than attributing
   it to the helper. Do not infer causes, source authenticity or complete-report
   correctness from numerical agreement or exit code zero.
5. For requested file deliverables, save the corrected report, concise claim
   audit and execution evidence. Otherwise keep a short audit in the conversation.
   Rerun
   relevant checks on the final text/derived claims and after source changes;
   retain earlier results as historical. Keep unresolved material claims visible.
   Record the working directory for each reproduction command and make every
   relative path resolve from that directory.
   Include postprocessing/finalization steps that change the delivered wording;
   reproducing an earlier output is insufficient if it drops final qualifications.

## Helper input and scope

Run with the working Python executable on the current host:

```text
python "<plugin-root>/scripts/check_numerical_claims.py" source.json claims.txt
```

`source.json` contains an explicit monetary `metric` (for example, `"revenue"`,
`"MRR"` or `"churned MRR"`), one `currency`, a nonempty unique
`population` of regions, and `values_cents` mapping each selected `YYYY-MM` to
exactly those regions and signed integer-cent values. Do not drop missing regions
to make the population appear complete. Incomplete data remains unverified.

`claims.txt` has one complete claim per line. Recognized forms are:

```text
Total revenue growth was 12% from 2026-08 to 2026-09 in AUD.
Revenue increased for every region from 2026-08 to 2026-09 in AUD.
Total MRR growth was 12% from 2026-08 to 2026-09 in AUD.
Gross revenue retention was 92% from 2026-08 to 2026-09 in AUD.
```

The dates, currency and percentage can vary. Case and whitespace variants are
accepted. Growth needs a positive starting total and rounds to the displayed
zero to two decimal places, with ties away from zero. The regional claim requires
every included region to increase strictly. Other forms remain unverified.

The claim must name the declared metric; case and whitespace differences are
accepted, aliases are not. Names use up to 80 ASCII letters, digits, spaces,
hyphens, underscores or slashes, starting with a letter. Values remain monetary
integer cents: counts, mixed currencies and automatic FX conversion are outside
this helper. Do not relabel a different measure as revenue to make it pass.

For the ratio form `<metric> was <percent>% from <period> to <period> in <currency>`,
the source names both series. For example:

```json
{
  "metric": "Gross revenue retention",
  "currency": "AUD",
  "population": ["North", "South"],
  "ratio": {"numerator": "retained MRR", "denominator": "starting MRR"},
  "series_cents": {
    "retained MRR": {"2026-09": {"North": 9000, "South": 18600}},
    "starting MRR": {"2026-08": {"North": 10000, "South": 20000}}
  }
}
```

This checks `100 * sum(numerator at to-period) / sum(denominator at from-period)`:
27,600 / 30,000 is 92%. Both selected series must contain exactly the declared
regions; periods must be chronological and the denominator total positive.
Rounding follows the same displayed-precision rule as growth. The source owner
defines the eligible cohort, retained/churned amounts and treatment of expansion;
the helper does not infer them, decide whether a ratio is economically meaningful,
or enforce a 0–100% range. A zero/negative denominator remains unverified.

The JSON output preserves each line and binds the exact supplied source, claims
and checker bytes. It does not bind a model's interpretation to the raw source
or prove that all material report claims were selected. Those remain explicit
audit responsibilities. Exit 0 means execution completed; exit 2 means an
input/execution error. No whole-report pass or guarantee is provided.

## Direct CSV checking

The same helper accepts a UTF-8 CSV export with an explicit mapping. It reads
all records, adds monetary values by period/region (and named series for ratios),
and attaches the contributing record IDs and physical line ranges to each claim.
This removes manual snapshot transcription; it does not establish source authority
or completeness outside the supplied file. Only the existing three claim forms
are checked. The caller still inventories the whole report's material claims.

```text
python "<plugin-root>/scripts/check_numerical_claims.py" export.csv claims.txt --csv-mapping mapping.json
```

Example `mapping.json`, supplied from the source's documented definitions:

```json
{
  "metric": "revenue",
  "currency": "AUD",
  "population": ["North", "South"],
  "value_unit": "major",
  "columns": {
    "record_id": "transaction_id",
    "period": "month",
    "region": "region",
    "currency": "currency",
    "value": "amount"
  }
}
```

Example CSV (fictional data):

```csv
transaction_id,month,region,currency,amount
n0,2026-08,North,AUD,1000.00
s0,2026-08,South,AUD,2000.00
n1,2026-09,North,AUD,1200.00
s1,2026-09,South,AUD,2160.00
```

These records support 12% total growth and an increase in both declared regions.
`major` means decimal currency amounts with at most two fractional digits;
`cents` means signed integer cents. No rounding of input amounts, exponent notation,
thousands separators or currency conversion is inferred. Zero must be explicit;
a blank amount or absent region is not zero. Use the source's unit convention.

Record IDs must be unique across the entire file. Distinct transactions for the
same period/region are summed; repeated IDs are rejected even if values agree.
Resolve source revisions before checking. Reordering records does not change
the calculation. Extra unused columns are allowed, but duplicate headers,
ragged/blank records, unknown regions and mixed currencies are refused. Use a
comma-delimited CSV with standard quoting; headers and key fields are exact.
The full declared population must be represented in every period selected by
a claim. An incomplete unrelated period does not invalidate complete comparisons.

For a ratio, add the existing `ratio` definition and a `series` column mapping.
Each record then names either the declared numerator or denominator series.
The checker uses denominator records at the from-period and numerator records
at the to-period. It does not infer a cohort or the meaning of retention.

Output includes source, mapping, checker and adapter hashes, the number of CSV
records read, and per-claim `source_records`. Record numbers count CSV records;
`lines` includes physical start/end lines, including quoted multiline fields.
Unknown/malformed input retains every requested claim as `not_verified` with
`source_status: unavailable`. A readable empty export supplies no monetary facts.
The helper writes JSON to stdout and never updates inputs or the report.

## Recheck an earlier and current source

Recheck identical original claim lines against two JSON snapshots:

```text
python "<plugin-root>/scripts/check_numerical_claims.py" current.json claims.txt --previous-source previous.json
```

Or use two CSV exports:

```text
python "<plugin-root>/scripts/check_numerical_claims.py" current.csv claims.txt --csv-mapping mapping.json --previous-source previous.csv
```

Both CSVs use the same mapping unless `--previous-csv-mapping previous-mapping.json`
is supplied. Declare changed definitions explicitly; do not relabel old facts to
make them comparable. This command compares two sources in the same input format.

Each result retains `previous`, `current` and the changed status/interpretation/
evidence fields. Top-level counts describe current results only. Source hashes
can change while all claim results remain the same, for example after reordering.
Missing or malformed current input makes dependent current claims `not_verified`;
the previous result remains labelled historical and is never substituted for it.
An unavailable previous source does not prevent checking the current one.

Inspect final prose and side claims after the recheck. The helper cannot certify
unlisted policy thresholds, causal claims, recommendations, or a whole regenerated
report. Preserve original deliverables; any publication/replacement procedure
belongs to the caller and needs its own failure-preservation checks.
