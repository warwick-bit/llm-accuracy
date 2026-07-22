---
name: self-audit
description: Use when asked to audit, check, rate, or correct Claude Code's own previous answer, including "you said", "you told me", "your previous answer", "audit your answer", or a pasted prior response from this assistant. Do not use for intern, agent, or bot output review.
argument-hint: "[paste or describe the prior assistant answer to audit]"
skill: self-audit
plugin: llm-accuracy
fully_qualified: llm-accuracy:self-audit
version: "0.1.0"
triggers:
  - pattern: "\\b(you said|you told me|your previous answer|audit your answer|check your answer|were you right|did you make that up)\\b"
    confidence: 0.90
  - explicit_invocation: true
excludes:
  - pattern: "\\b(intern|agent|bot|employee assistant)\\b"
priority: 55
---

# Self-Audit

Use this skill to audit your own prior answer. Do not use it for intern, agent,
or bot output review; route those to the relevant domain/plugin review skill.

## Workflow

1. Identify the prior answer being audited. If the user did not provide enough
   context, ask for the missing answer or summarize the exact claim you can
   audit.
2. Read `references/evidence-discipline.md` when the answer includes
   high-stakes facts, provider/customer/business claims, readiness claims, or
   exact values.
3. Inventory load-bearing claims: numbers, dates, IDs, statuses, file paths,
   PR/commit/deploy claims, provider facts, and strong causal statements.
4. Re-derive each load-bearing claim from current source evidence when tools or
   files are available. If source evidence is unavailable, say that rather than
   substituting memory.
5. Classify each material claim as supported, unsupported, garbled, overstated,
   missing caveat, or not checked.
6. Give the corrected answer in plain language. Lead with the verdict, then
   include evidence notes and confidence aligned with the body.

## Output Shape

- Verdict: one sentence stating whether the prior answer was accurate enough.
- Corrections: concise bullets for each unsupported, garbled, or overstated
  claim.
- Supported claims: mention only material claims that survived re-checking.
- Evidence: use the footer labels from `references/evidence-discipline.md`
  when the audit depends on business/provider/customer or readiness evidence.
- Confidence: High, Medium, or Low, with the body matching the confidence.

Do not defend the prior answer. If the earlier answer was wrong, say what was
wrong and what the current evidence supports.
