# Security Policy

Do not open a public issue with a suspected security or privacy problem. Use a
private GitHub security advisory for this repository, or contact the repository
owner directly through GitHub.

Include only a sanitized reproduction. Never include credentials, private
prompts, customer data, raw provider payloads, or session-ledger contents.

LLM Accuracy has no telemetry, server-side data store, persisted prompt capture,
or persisted tool-output capture. The separately installed Session Ledger stores
only the participant's local compact summary in Claude plugin data; it has no
telemetry or server-side store. Hooks operate in the participant's local runtime
and are advisory and non-blocking.
