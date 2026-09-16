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
8. Produce one evidence receipt using
   `${CLAUDE_PLUGIN_ROOT}/references/evidence-receipt.schema.json` and validate
   it with `${CLAUDE_PLUGIN_ROOT}/scripts/validate_evidence_receipt.py`.

An evidence-receipt structural pass never means the data or conclusion is
factually correct. Apply the LLM Accuracy claim-fidelity check before presenting
a consequential conclusion.
