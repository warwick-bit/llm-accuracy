# Deterministic Data

Deterministic Data is an editable Claude Code and Cowork plugin template for
routing data questions through explicit definitions and source bindings. It is
not a database, connector, analytics engine, or bundled source of truth.

## Customise your own copy

Do not edit an installed marketplace cache. Updates can replace it. Instead:

1. Fork or copy this repository.
2. Copy `catalogues/example.catalogue.json` to a clearly named catalogue.
3. Replace the synthetic definitions, aliases, windows and source-binding IDs.
4. Add your own separately reviewed read-only adapters or connector tools.
5. Run `python3 scripts/validate_catalogue.py <your-catalogue.json>`.
6. Test ambiguous, candidate, unavailable and successful routes with synthetic
   fixtures before using real sources.
7. Install the customised repository in Claude Code, or build and upload its
   plugin ZIP to Cowork.

Catalogue files contain metadata, not data. Never put credentials, query
results, provider payloads, customer records, private prompts, or secrets in a
catalogue or test fixture.

## Routing boundary

- Exact aliases may identify one definition.
- Multiple matches require an explicit user choice.
- `approved` means the catalogue owner approved the definition; it does not
  prove that a source is available or correct.
- `candidate` and `gap` entries cannot produce a canonical value.
- An approved route executes only through its declared source binding.
- Failed, unavailable, partial or mismatched reads cannot be replaced with a
  remembered, estimated or nearby value.
- Every answer route emits an evidence receipt using the bundled versioned
  schema. The receipt is a structural boundary, not a correctness certificate.

The bundled example is fictional and intentionally has no working provider
adapter.
