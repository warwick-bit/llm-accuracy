# Security Policy

Do not open a public issue with a suspected security or privacy problem. Use a
private GitHub security advisory for this repository, or contact the repository
owner directly through GitHub.

Include only a sanitized reproduction. Never include credentials, private
prompts, customer data, raw provider payloads, or session-ledger contents.

LLM Accuracy has no telemetry, server-side data store, persisted prompt capture,
or persisted tool-output capture. The separately installed Session Ledger stores
only the participant's local compact summary and bounded rolling user/assistant
session record in Claude plugin data; it has no telemetry or server-side store.
Hooks operate in the participant's local runtime and are advisory and non-blocking.
The LLM Accuracy evidence-receipt validator and Deterministic Data catalogue
validator run locally, make no network calls, retain no inputs and emit no
receipt- or catalogue-supplied values.

The separately installed experimental Data Execution plugin explicitly copies
completed JSON/CSV tool exports into private local snapshots. These can contain
sensitive source data; base64 is not encryption. Retention defaults to 30 days
and is configurable per capture. Expired reads are refused; deletion occurs on
capture or explicit purge, with no background cleanup or secure-erasure promise.
It has no hooks, network, credentials or automatic tool interception. Users must
keep storage outside public repos and review source adapters and permissions.
The core accuracy plugin and Session Ledger boundaries remain unchanged.
