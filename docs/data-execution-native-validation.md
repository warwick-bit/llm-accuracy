# Native Data Execution workflow pilot

Keep this plugin experimental. It preserves exact local source bytes and supports
fresh-session retrieval, but has no demonstrated token advantage over an already
compact file-backed calculation. Strict model output formatting remains unreliable.

## Completed transport comparison

Claude Code 2.1.280, requested and observed claude-sonnet-5, low effort. One
400-row synthetic mixed-currency workflow per arm: aggregate, then selected detail
in a fresh session after staging-export deletion. Independent integer oracle;
all requested fields exact, including types, scope, completeness and reference.
The plugin snapshot's raw bytes and content hash were independently verified.

```text
Workflow                      Reported total tokens
Native raw fetch + follow-up                236331
Existing file helper + follow-up             90383
Plugin capture + follow-up                  183275
```

Plugin versus raw: 22.4% fewer tokens. Plugin versus file helper: 102.8% more.
These sum input, cache creation, cache reads and output across requests. They are
neither unique context size nor billed dollars. Native raw output spilled to a
file; this is a native raw-fetch comparison, not full raw content in context.
One observation per arm gives no variance estimate or generalizable saving.
The raw arm was instructed to fetch raw; it does not estimate unaided Claude.
This comparison predates the subsequent skill output-format clarification.

## Failures and iteration

Initial setup probes exposed a real documentation defect: installation leaves
this opt-in plugin disabled. Installation instructions now include explicit enable.
The harness also needed fresh auth-only profiles and scoped permission rules for
both quoted and unquoted script paths. All failed attempts remain in the
[metadata receipt](validation/data-execution-native.json); no incomplete comparison
contributes a token-saving ratio. No blanket permission bypass was used.

The successful plumbing smoke captured and calculated, then retrieved exact detail
in a fresh session after original-export deletion. The large comparison passed
all three arms. Subsequent precision and partial-source tests failed the strict
final-output contract: the answers did not parse as a lone JSON object.
No raw model responses were retained. A separate partial diagnostic found its
embedded JSON exactly matched the independent oracle, including withheld totals.
That diagnostic does not turn the original failure into a pass or establish the
original precision failure's numerical correctness.

A new candidate clarified JSON-only output in the skill. Its precision aggregate
and follow-up passed; partial-source initial output still failed because extra
presentation surrounded an otherwise exact embedded JSON object. Partial follow-up
was not run after the failed initial gate. No model-completion or universal
financial-fidelity claim is warranted. The clarification is guidance, not enforced
structured output. All original failures remain visible.

## Method and boundary

New synthetic source, no live provider data. Strict scorer rejects duplicate keys,
wrong types/values, extra or missing fields, nonfinite constants and commentary;
two positive and eight negative controls pass. Each workflow uses an isolated
profile, explicit plugin inventory, empty MCP configuration, disabled hooks and
bounded subprocesses. Built-in telemetry is present equally across arms. Fresh
sessions are not a compaction/resumed-context benchmark. Raw and file controls
retain a hashed working file; the plugin retains its own snapshot.

The local harness was exploratory and is not a shipped/public benchmark runner.
The checked-in receipt contains only fixed-label outcomes, usage and setup counts,
not answers, source bodies, credentials or transcripts. Runtime deterministic
coverage remains in tests/test_data_execution.py; byte experiments remain
reproducible with scripts/eval_data_execution.py.

Prior local session methods informed the design: neutral task wording, independent
oracles and retaining incomplete pairs. No private session content was copied.

## Decision

Use the existing compact file workflow for token efficiency. Consider this opt-in
plugin when durable snapshots, scope checks and explicit retention add value.
Do not promote it as a token optimizer or strict machine-readable reporting layer.
A future automated consumer should consume validated CLI receipts directly rather
than rely on a model to reproduce JSON. Live provider completeness remains untested.
