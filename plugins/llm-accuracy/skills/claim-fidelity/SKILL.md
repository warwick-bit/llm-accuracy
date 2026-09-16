---
name: claim-fidelity
description: Use when checking whether a factual conclusion is supported by its sources, scope, freshness, completeness, comparison, or causal evidence; including claims that data is complete, populations match, a source is current, or a provisional result is reliable.
argument-hint: "[claim, evidence, or draft answer to check]"
skill: claim-fidelity
plugin: llm-accuracy
fully_qualified: llm-accuracy:claim-fidelity
version: "0.1.0"
triggers:
  - pattern: "\\b(does this prove|can we conclude|claim fidelity|evidence supports|fully synced|same population|complete data|source is current|provisional result)\\b"
    confidence: 0.85
  - explicit_invocation: true
priority: 56
---

# Claim Fidelity

Check whether the conclusion stays inside the authority of the evidence.

## Workflow

1. State the exact load-bearing claim. Split compound claims before checking.
2. Identify the evidence actually observed, including failed, partial, cached,
   stale, redacted, permission-limited, or unavailable reads.
3. Compare the claim and evidence across source, subject, population, measure,
   grain, time window, freshness, completeness, and definition.
4. Check the bridge from evidence to conclusion:
   - equal counts or totals do not prove equal membership;
   - a business timestamp does not prove pipeline or source completeness;
   - a successful tool call does not prove the returned source is correct;
   - a provisional label does not repair a method/execution mismatch;
   - correlation, sequence, and a plausible story do not prove cause.
5. Preserve conflicts and unknowns. Do not resolve them by silently choosing a
   preferred source or definition.
6. Classify the claim as `supported`, `qualified`, `withheld`, or `unchecked`.
7. Give the smallest additional check that could change the classification.

When an evidence receipt is supplied, validate its structure with
`${CLAUDE_PLUGIN_ROOT}/scripts/validate_evidence_receipt.py`. A structural pass
does not verify source truth, arithmetic, domain correctness, or the resulting
claim. If the calling workflow supplies the current prompt epoch, pass it with
`--expected-epoch`; otherwise report prompt binding as unchecked.

## Output

- **Claim:** the exact conclusion checked.
- **Status:** supported, qualified, withheld, or unchecked.
- **Evidence boundary:** what the observed evidence establishes.
- **Overreach:** any unsupported extension in scope, completeness, freshness,
  comparison, or causality.
- **Next check:** the smallest check that would resolve the material gap.

Do not manufacture certainty because an answer is labelled provisional or
because a tool returned without an error.
