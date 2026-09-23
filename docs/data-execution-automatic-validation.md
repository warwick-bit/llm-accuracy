# Everyday automatic context reduction: decision

Do not enable or promote a blanket automatic compressor for everyday Claude Code
sessions on this evidence. Automatic interception is feasible; reliable net benefit
across the tested workflows is not established. Keep the adapter/snapshot plugin
experimental: it does not meet the install-once everyday requirement.

## What was tested

An isolated PostToolUse hook, no per-task invocation, adapters or domain mappings.
No live user configuration or provider was changed. Claude Code 2.1.280 with
claude-sonnet-5 low; model identity, tool inventories, permission failures and
reported token usage checked in memory. Raw answers/transcripts not retained.
All sources newly synthetic. Parent oracle uses integer arithmetic; the strict
value/type scorer allows prose surrounding one unambiguous JSON object. This
measures everyday answer values, not the previous pilot's JSON-only API contract.

Native controls have the same task and tools. Request tokens include input,
cache creation, cache reads and output; they are not unique context or billed
cost. One observation per case/version, no variance estimate. Failed/incomplete
pairs are retained and excluded from ratios.

## Results

```text
Candidate / task                 Native tokens  Candidate tokens  Change
File pointer v1 / medium Bash            70062            144815  +106.7%
File pointer v1 / medium MCP             72097            177597  +146.3%
File pointer v2 / medium Bash            70790            103340   +46.0%
File pointer v2 / medium MCP             71944             81736   +13.6%
Lossless columns / table-heavy Bash      61773             49895   -19.2%
```

All completed comparisons above returned exact requested values, including very
large integer amounts, currency grouping, source qualifications and tail details.
The medium MCP task withheld totals for incomplete data. These are bounded
synthetic correctness observations, not a universal finance-accuracy guarantee.

V1 saved large text and returned a file reference. Claude often read the full
file back, increasing calls and context. V2 added calculate-over-file guidance;
the medium cases still used more tokens. Small/native-saved cases passed through
unchanged; token variation in those cases is not a hook benefit.

The final candidate keeps every value visible but replaces repeated JSON object
keys with a shared column list. It is reversible, rejects duplicate-key/tag
collisions and preserves numeric lexemes. A final size gate leaves unhelpful or
unsupported text unchanged. The favorable table-heavy Bash case improved; this
stratum was intentionally favorable, not representative of session frequency.
The table-heavy MCP comparison is inconclusive: three native attempts hit the
test harness's Bash permission policy (cat/compound calculation construction),
so no candidate arm or paired saving is reported. Adding a cat allow rule did
not resolve the final denial; no blanket bypass or further retries were used.
MCP text replacement itself was demonstrated by the earlier pointer tests.

## Fidelity trap found and fixed in the prototype

For a 152453-byte Bash source, the hook received a 30000-character prefix with
no truncation marker inside stdout. Separate persistedOutputPath and
persistedOutputSize fields pointed to native full-output storage. V1 incorrectly
saved that preview while describing it as the source. An exact hash of a saved
file did not prove source completeness. The failure remains in the receipt.

V2 skips native-persisted output entirely. Its large Bash pair made no replacement
and passed. A large MCP probe delivered a string-shaped result to the hook rather
than the full text block; the candidate correctly left that unsupported shape
unchanged. The one-call probe establishes boundary behavior, not answer recovery.
Bash also strips the producer's final newline before the hook. Tested medium
captures match the hook-boundary text, not the original producer's byte stream.
MCP medium text matched the source bytes exactly. No upstream precision-repair
claim; numeric structured transport outside these text paths was not host-tested.

## Real-session opportunity check

Read all 144 available top-level Claude transcript files modified within the
30-day discovery window, including the largest file. This is a file-mtime-selected
corpus; its records are not restricted to a strict 30-day message timestamp window.
No session paths, tool names, provider bodies, answers or private values were
persisted in the report. Parse bodies only in memory and emit aggregate counts.

```text
Bash/MCP tool results examined                  3575
Error results excluded                          251
Successful text results4096–30000bytes            347
Strict supported JSON within that band           78
Results meeting final candidate's size gate        5
Eligible source bytes                         36589
Candidate bytes with750-byte receipt allowance 26384
```

All five qualifying results were MCP outputs. This is a conservative transcript-
visible applicability estimate, not actual pre-hook coverage, billed savings or
estimated token savings. Embedded JSON strings, unsupported shapes, tiny outputs
and already-large results fall outside this candidate. It supports a narrow
opportunity, not a claim that only five possible optimizations exist.

## Validation and stopping rule

Seventeen file-hook boundary checks passed. Thirty-six independent codec wire
round-trips and five malformed-input rejections passed; eight wiring checks
covered actual packet size, byte-preserved originals, MCP list/object shapes and
native/small/structured passthrough. Scorer controls: two valid representations
pass and six deliberately wrong/ambiguous answers fail. Design and wiring received
independent Claude review; reviewer gaps were reconciled locally. These checks
cover an exploratory prototype, not concurrent production storage, expiry or
interaction with other installed hooks.

The user asked for everyday automatic usefulness. Two offload iterations increased
usage, native storage already handles large outputs, and the only promising final
representation matched very few observed results. That is enough to stop this
investigation without installing or shipping a broad plugin. Preserve the narrow
lossless-format experiment for a future workload that demonstrates frequent eligible
outputs; do not require the user to adopt a manual finance workflow instead.

The exploratory runner remains local, not a shipped/public benchmark package.
The checked-in summary records sanitized outcomes; no runtime hook is registered.

## Primary reference

Claude's [hook reference](https://code.claude.com/docs/en/hooks#posttooluse-decision-control)
documents updatedToolOutput and output-shape requirements. Its
[MCP output documentation](https://code.claude.com/docs/en/mcp#tool-output-limits)
describes native persistence. The ordering/truncation conclusions above come from
actual installed-host probes, not assumptions based on documentation.

Independent Claude report review found no blocking inference issue; it reviewed
the narrative, not raw receipts. Parent checks verified ratios and corpus counts.
Local repository gates:617 tests, Ruff, manifests/new receipt parsing, hook
compilation and whitespace checks passed. The no-go decision remains unchanged.
