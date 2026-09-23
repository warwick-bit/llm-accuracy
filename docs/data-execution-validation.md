# Data Execution synthetic validation

## Conclusion

Useful for a completed large export when the task needs aggregate results and a small
amount of detail. Not a general compression layer: small inputs and all-row follow-ups
increase output. The retained bytes enable consistent fresh-process follow-ups after
the original export is deleted. They do not themselves reduce context.

## Measured output bytes

Baseline: one complete raw response, reused in context for follow-ups. Candidate:
capture receipt, grouped total receipt, then requested full-row detail packets.
All cases use synthetic JSON exports; this is not a model token/billing benchmark.

```text
Rows    Detail rows    Raw bytes    Candidate bytes    Reduction
1       1              365          1630               -346.6%
1000    1              336920       1686               99.5%
1000    1000           336920       359360             -6.7%
```

Reproduce with `python3 scripts/eval_data_execution.py`. The checked-in
[metadata receipt](validation/data-execution-synthetic.json) records the measurement
boundary, exact oracle results and disk sizes. No source bodies are persisted by the
experiment after its temporary directories are removed.

The already-captured control omits only the new capture receipt. Saving an existing
snapshot again adds output. No incremental token advantage over an equivalent
existing local-file calculation workflow has been demonstrated. Claude native
large-output spill behavior, provider fetch costs and skill/tool-call overhead are
not included; these results must not be presented as a measured saving over native
Claude Code or an existing optimized finance workflow.

## Lifecycle and fidelity

The tests exercise fresh-process JSON/CSV retrieval, an alternate structured JSON
envelope, exact integer/decimal oracles, partial data, scope mismatch, tampering,
deleted/changed original files, expiry boundaries, configurable retention, cleanup,
concurrent capture, interrupted publication, malformed inputs, permissions, symlinks,
input/storage/output limits and a producer that emits valid data then fails.
Source numeric values become strings before detail transport; raw bytes are retained.

The [installation receipt](validation/data-execution-install.json) separates local
marketplace installation/manifest checks from untested model skill execution.

## Limits

Synthetic coverage does not establish live provider completeness, model reasoning
accuracy, legal retention compliance or measured token savings. User adapters and
exporters must be reviewed; the plugin does not verify their source assertions.
Native MCP interception, Windows and Cowork are outside this pilot.

## Native host follow-up

The [native workflow pilot](data-execution-native-validation.md) measures actual
reported tokens and preserves failed host/format checks. It confirms snapshot
usefulness, finds overhead versus the existing compact file control, and keeps
this plugin experimental. The installation instructions now require explicit enable.
