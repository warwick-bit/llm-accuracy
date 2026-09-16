---
name: data-routing
description: Use when answering a data or metric question through a user-owned deterministic-data catalogue, resolving definition ambiguity, checking catalogue status, or producing a source-bound evidence receipt.
argument-hint: "[data question and catalogue path]"
skill: data-routing
plugin: deterministic-data
fully_qualified: deterministic-data:data-routing
version: "0.1.0"
triggers:
  - pattern: "\\b(deterministic data|data catalogue|metric catalogue|catalogue route|definition ambiguity)\\b"
    confidence: 0.85
  - explicit_invocation: true
priority: 60
---

# Deterministic Data Routing

Route a data question through the user's reviewed catalogue. The bundled
example is synthetic and cannot answer a real question.

## Before use

1. Locate the user-owned catalogue. Do not treat the installed example as a
   source of truth.
2. Validate it with
   `${CLAUDE_PLUGIN_ROOT}/scripts/validate_catalogue.py <catalogue>`.
3. Confirm the declared source adapter is available and read-only for this task.

## Route

1. Decide whether the request asks for measured data, a definition, or a
   fictional example. Only measured-data requests can execute a source binding.
2. Match explicit aliases exactly after lower-case whitespace normalization.
   Do not use fuzzy matching to select a nearby definition.
3. If zero definitions match, state the catalogue gap and stop.
4. If several definitions match, present their labels, definitions, statuses,
   units, grains and supported windows, then ask the user to choose.
5. A `candidate` or `gap` entry may explain the boundary but cannot produce a
   canonical value.
6. For one `approved` definition, check the requested window against
   `supported_windows`, then call only its declared source binding.
7. Preserve failed, unavailable, partial, stale, conflicting and scope-mismatch
   outcomes. Never substitute memory, another source, or a provisional method.
8. Return one evidence receipt inline using
   `${CLAUDE_PLUGIN_ROOT}/references/evidence-receipt.schema.json`. Read that
   schema before constructing the receipt. The receipt must contain exactly
   these root fields: `schema_version`, `prompt_epoch`, `claim_id`, `route_id`,
   `definition_id`, `source_refs`, `scope`, `freshness`, `completeness`,
   `conflict`, `caveats`, and `claim_status`. A routing summary or a different
   JSON object is not an evidence receipt. Include the receipt for every
   terminal route: matched, gap, ambiguous, candidate, unavailable, failed or
   successful. Return it and its validation status in the same response before
   any canonical value. Do not write the receipt to a file, including a
   temporary or scratchpad file, unless the user explicitly asks.
   Create a fresh route ID for this answer using only letters, digits, `.`, `_`,
   `:` and `-`. Set `prompt_epoch` to that exact route ID for this one-route
   answer. A calendar date alone is not a prompt epoch and must not be reused
   across answers.
9. If execution tools are permitted and the validator exists, attempt the
   bundled validator once. Pass the exact `prompt_epoch` through
   `--expected-epoch "<prompt_epoch>"` as one quoted argument, invoke the
   validator without a receipt path, and pass the JSON through standard input
   with a quoted heredoc delimiter (`<<'RECEIPT_JSON'`). Never create a file
   just to validate it. Exit code 0 means `passed`; any completed nonzero exit
   means `failed`, including a validator runtime error. Use `not run` only when
   the validator could not be launched because execution was denied or the tool
   or script was unavailable. Visual inspection can identify a caveat, but
   cannot produce either a `passed` or `failed` validation status.

For an unexecuted or unavailable source, use a source status of `unavailable`,
mark freshness and completeness `unknown`, and set `claim_status` to `withheld`.
Do not replace the receipt schema with catalogue fields such as `route_status`,
`definition_status`, `supported`, or `source_binding_executed`.

The required nested shapes are:

- `source_refs`: a non-empty list of objects containing only `source_id`,
  `status`, `observed_at`, and `scope_match`; use the catalogue or declared
  adapter as an unavailable source when no query ran;
- `scope`: an object containing only non-empty `population`, `measure`,
  `time_window`, and `grain` strings; use explicit `unknown` text where needed;
- `freshness`, `completeness`, and `conflict`: objects containing only `status`
  and a non-empty `basis`; and
- `caveats`: a list of strings, with `claim_status` set to `supported`,
  `qualified`, `withheld`, or `unchecked`.

An evidence-receipt structural pass never means the data or conclusion is
factually correct. Before presenting a consequential conclusion, independently
check it against the observed source, population, definition, time window,
freshness and completeness. This plugin must remain usable when LLM Accuracy is
not installed.

## Output

- **Matched definition:** exact definition ID, or the gap/ambiguity.
- **Route status:** whether a declared source binding was executed.
- **Evidence receipt:** one inline receipt for this route.
- **Structural validation:** `passed`, `failed`, or `not run`.
- **Canonical value:** returned or withheld, with the reason; always last.
