# Check refreshes and preserve prior outputs

Use this when a saved analysis program or report generator will be rerun. Correct
original figures do not establish safe behavior on empty inputs or a failed refresh.
Work in an isolated copy with synthetic or authorized inputs. Never inject failure
into the owner's production output directory.

1. Declare all input files and required delivered files, including prose and tables.
   Confirm the baseline set is complete and correct with numerical and final-report
   checks. An omitted deliverable is outside this helper's coverage.
2. Stop writers and capture a baseline; save stdout outside the declared files.
3. Change inputs in the isolated workspace, explicitly run the producer and retain
   its actual outcome. Check both a successful changed-input case and a realistic
   failure/empty-input case. A nonzero exit does not undo prior writes.
4. Stop writers and compare against the baseline using the observed outcome.
   Inspect changed/missing files and input-change evidence. After success, check
   content against changed inputs; byte differences do not prove semantic freshness
   or correctness. Unchanged output can be valid for different inputs.
5. At the consuming application's publication boundary, generate into staging,
   validate the complete set, then use that application's supported transaction or
   publication mechanism. On failure keep the previous complete set. Sequential
   file replacements are not an atomic multi-file update. Exercise the actual
   failure path; this helper never runs, publishes, repairs or rolls back a producer.

Resolve a working Python 3.9+ executable through the host. Given `files.json`:

```json
{"inputs": ["data/input.csv"], "outputs": ["results/totals.csv", "results/report.md"]}
```

Capture stdout as `before.json` using the host's file-output mechanism:

```text
python "${CLAUDE_PLUGIN_ROOT}/scripts/check_output_refresh.py" capture workspace files.json
```

After the explicitly authorized producer run:

```text
python "${CLAUDE_PLUGIN_ROOT}/scripts/check_output_refresh.py" check workspace files.json --before before.json --outcome failed
```

Use `--outcome succeeded` for a successful run. The helper does not infer or verify
that declaration or execute producer code. On Codex, resolve the package root two
directories above the skill directory instead of assuming `${CLAUDE_PLUGIN_ROOT}`
exists as an environment variable. Hosts without execution may apply the workflow
but must not claim the helper ran.

Paths are relative to the workspace, slash-separated, unique and disjoint across
inputs/outputs. Absolute paths, traversal and case-insensitive aliases are refused;
resolved paths outside the workspace are unavailable. Only regular files are read.
Hashes and byte counts are recorded, not content. Reordered manifest lists are
equivalent. Duplicate JSON keys and snapshots omitting declared files are rejected.
Snapshots are supplied evidence, not authenticated proof of history; preserve the
original baseline rather than editing it.

For failure, `output_preservation: preserved` requires every declared output readable
before and after with identical bytes. Known overwrites/deletions report `changed`;
missing/inaccessible evidence cannot become a preservation pass. `required_outputs:
all_readable` establishes presence/readability only and can coexist with mixed old/new
content. Empty files are listed explicitly; validity depends on the output contract.

`input_change` describes observed bytes across declared inputs; reads with gaps are
`not_verified`. `changed_paths` includes availability changes as well as bytes.
Reads are sequential: use quiescent files. The helper cannot prove atomicity, detect
reverted transient writes or guarantee power-loss/crash durability. Check successful
final outputs with the report inventory and domain checks. No overall accuracy,
semantic-freshness or safety verdict is emitted. Exit 0 means execution completed;
invalid manifest/baseline/root produces structured error JSON and exit 2.
