# Deterministic Data

Use this plugin to route data questions through user-owned definitions and
source bindings. Never treat the bundled synthetic catalogue as real data or a
source of truth.

The catalogue contains definitions and source-binding metadata only. Never put
credentials, provider payloads, customer records, query results, or raw private
data in the plugin.

An `approved` definition is approved only by the catalogue owner. A successful
structural receipt does not verify source truth, arithmetic, domain correctness,
or factual accuracy.
