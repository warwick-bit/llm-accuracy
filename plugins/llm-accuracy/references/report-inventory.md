# Check the final report's assertion inventory

Use this for a consequential report with supplied evidence, especially after
shortening, regeneration or source changes. Check the actual final UTF-8 text or
Markdown file. A calculation checked earlier does not establish that the delivered
prose retained its population, threshold, period or qualification.

1. Read the final report and enumerate material assertions, including side claims,
   policy thresholds, population labels and necessary qualifications. Split compound
   assertions in the report when practical. Keep each inventory text equal to one
   complete nonblank report line; do not substitute a convenient substring.
2. Attach a bounded numerical check or record a separate manual assessment against
   the source. Include the source's SHA-256 at the time of that assessment. Do not
   refresh that hash after a source change until the meaning has been reassessed.
3. Run the helper against the final file. Inspect every unlisted line and missing
   assertion, then the per-assertion results. Headings and nonfactual text also appear;
   they can have inventory entries with explanatory notes and no evidence check.
   Do not omit prose merely because the main calculation passed.
4. Reassess changed sources and rewritten text. Rerun after the final edit. Preserve
   unsupported claims and material gaps in the delivered answer, not just this output.

Resolve a working Python 3.9+ executable through the host, then run:

```text
python "${CLAUDE_PLUGIN_ROOT}/scripts/check_report_inventory.py" final.md inventory.json
```

On Codex, resolve the package root two directories above the skill directory;
`${CLAUDE_PLUGIN_ROOT}` is a placeholder, not a guaranteed environment variable.
On hosts without local execution, apply the workflow with available tools and
explicitly state that this helper did not run. No extra integration is required.

The JSON inventory has exactly one top-level `assertions` list. For example:

```json
{
  "assertions": [
    {
      "id": "growth",
      "text": "Total revenue growth was 12% from 2026-08 to 2026-09 in AUD.",
      "numerical": {"source": "numbers.json"}
    },
    {
      "id": "policy",
      "text": "The minimum balance is AUD 150,000.",
      "note": "Policy source has not yet been supplied; this remains unchecked."
    }
  ]
}
```

`numerical` accepts a `source` path and optional `csv_mapping` path using the
[existing monetary checker](numerical-verification.md). It reruns that checker,
including its supplied metric, currency and population boundaries; it does not
load an earlier result as a pass. Unsupported sentence forms remain `not_verified`.

Alternatively, an assertion may have a `review` object with exactly these fields:

- `source`: path to the local evidence file actually assessed.
- `sha256`: its 64-character lowercase SHA-256, obtained from the file bytes.
- `assessment`: `supported`, `qualified`, `contradicted` or `unchecked`.
- `reason`: the observed support, limits or conflict, including relevant locations.

An assertion cannot have both `review` and `numerical`. Paths resolve beside the
inventory, irrespective of the working directory. A manual review reports its
`declared_assessment` separately from `source_binding` (`current`, `stale` or
`unavailable`). Its machine `status` always remains `not_verified`: matching file
bytes do not prove the assessment is correct, the source is authentic or that a
newer source does not exist. Use host retrieval and claim-fidelity checks as needed.

The helper retains every nonblank report line with its original line number,
lists unlisted lines and missing assertions, and hashes the report and inventory.
It accepts changes to line endings, outer whitespace and line ordering; punctuation
and internal text must match. All repeated occurrences are shown. Assertion IDs and
stripped texts must be unique, so conflicting inventories cannot silently overwrite
one another. Sources and reports are read only; output goes to stdout.

Exit 0 means execution completed, not that the report passed. Unreadable or invalid
report/inventory inputs return structured error JSON and exit 2. Missing evidence
affects its dependent assertion while independently checkable assertions remain.

Zero unlisted lines is only line coverage. A listed line may contain multiple
assertions, a missing qualification or an incorrect manual assessment. Semantic
completeness stays `not_verified`, even for an empty report or a fully listed one.
This deliberately avoids an automatic extractor whose omissions could be mistaken
for complete verification. It is not a publication gate or a model-efficacy study.
