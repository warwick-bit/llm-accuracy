# Data Execution pilot contract

Problem: full tool results and repeated reads can occupy model context even
when calculations need only grouped totals and selected follow-up records.
Surface: a new separately installed Claude Code plugin in this marketplace.

Chosen approach: capture a successful source export to a private immutable local
snapshot, compute exact grouped totals, return bounded receipts, retrieve detail
in a fresh process. JSON and CSV adapters are user-owned. MCP clients can export
structured JSON; no automatic native-MCP interception is claimed.

Rejected: a post-tool summarization hook (the raw content may already have entered
context and semantic omission would be hard to audit). Deferred: a universal MCP
proxy or configurable subprocess runner (additional credentials/process lifecycle
surface before the local-storage usefulness question is established).

Competing explanations to test:
- Savings come from source-side projection, not persistence itself.
- Persistence helps follow-up consistency after upstream files change or vanish.
- Small inputs lose to receipt overhead.
- Detail-heavy requests remove aggregate savings.
- Numeric transport can corrupt otherwise exact arithmetic.
- Storage failures or incomplete sources can create false confidence.

Acceptance: exact independent arithmetic oracles and raw byte recovery; new-process
follow-up; refusal of missing, expired, changed and wrong-scope snapshots; explicit
partial totals withholding; configurable retention defaulting to 30 days; bounded
output and storage; no source body in capture/error output; synthetic raw-versus-
receipt accounting including adverse cases. Bytes are not model tokens or billing.

Plan: implement local core and adapters; run lifecycle and boundary tests; run the
synthetic usefulness experiment; independently review with Claude; reconcile real
findings; run repo gates and prepare a draft PR. Release and production provider
validation are separate from these local checks.

Privacy review: all new examples/tests are authored from fictional fields and
values. No source data, private session content or existing private test fixtures
are copied into the distribution. Source commands and credentials remain outside
the plugin. Runtime snapshots must never be committed or attached to public PRs.

Design review reconciliation: custom object-pairs parsing rejects duplicate JSON
keys; the entire envelope (including policy and caveats) is hashed, with identity
only in the filename. Temporary publication files live inside the destination
directory. All store-path components are checked for symlinks. Partial detail
retains an explicit withheld marker. Stdin capture was removed because a consumer
cannot establish its producer's eventual exit status. Producer success remains
a source workflow responsibility for staged-file imports.
