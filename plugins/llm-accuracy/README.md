# LLM Accuracy plugin

LLM Accuracy is a Claude Code plugin for evidence-aware LLM work. It ships
general accuracy hygiene rather than a claim of universal factual correctness.

## What it does

- prompts for provenance, scope, freshness, and caveats on consequential
  factual answers;
- checks whether claims remain within their source, population, definition,
  window, freshness and completeness boundaries;
- nudges a model to recheck stale details after long sessions; and
- provides self-audit and claim-fidelity workflows;
- includes a stateless evidence-receipt schema and structural validator for
  workflows that already produce typed evidence boundaries.

## What it does not do

- access a provider, database, or external source of truth;
- verify a specific domain metric or business definition;
- certify source truth, arithmetic, domain correctness or factual accuracy;
- create or persist prompt epochs, receipts, prompts, or tool output;
- collect telemetry, persist prompts or tool output, or send data to a server;
  or
- guarantee that an answer is complete, current, or correct. It does not guarantee factual correctness.

Hooks are advisory and non-blocking.

The receipt validator emits `structural_only` results and stable error codes. A
pass means the receipt satisfies the generic structural contract; it does not
mean the underlying claim is correct.

## Day-to-day use

Once installed and activated, use Claude Code normally: there is no separate
command to run or prompt to paste for matching prompts. Claude Code adds
targeted advisory reminders for matching analysis and source-conflict prompts,
and after context compaction; it does not interrupt every prompt or verify facts
automatically. Ask the assistant to audit one of its earlier answers when you
want a direct self-check.

## Freshness and memory

An LLM can over-weight recalled training material, earlier context, or a stale
summary after a long session. The result can sound confident but be outdated or
unsupported. This plugin therefore asks the model to recheck current evidence,
label inference, and say when a source is unavailable instead of filling the
gap from memory.

## Feedback boundary

Use synthetic, authorised material in feedback and follow the repository's
[contributing guide](https://github.com/warwick-bit/llm-accuracy/blob/main/CONTRIBUTING.md).

No session ledger, prompt history, or tool output is included or persisted by
this plugin.
