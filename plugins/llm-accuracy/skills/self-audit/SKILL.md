---
name: self-audit
description: Use when asked to audit, check, rate, or correct Claude Code's own previous answer, including "you said", "you told me", "your previous answer", "audit your answer", or a pasted prior response from this assistant. Do not use for intern, agent, or bot output review.
argument-hint: "[paste or describe the prior assistant answer to audit]"
skill: self-audit
plugin: llm-accuracy
fully_qualified: llm-accuracy:self-audit
version: "0.1.1"
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
   audit. Separate the user's supplied facts, choices and source material from
   assertions introduced by the answer. The answer is the object of the audit,
   not evidence for itself. Accepting a category or giving a total does not
   confirm the assistant's examples of what that category contains or excludes.
2. Read `${CLAUDE_PLUGIN_ROOT}/references/evidence-discipline.md` when the answer includes
   high-stakes facts, provider/customer/business claims, readiness claims, or
   exact values.
3. Inventory load-bearing claims: numbers, dates, IDs, statuses, file paths,
   PR/commit/deploy claims, provider facts, and strong causal statements. Include
   factual claims inside examples, caveats and recommendations; correct
   arithmetic does not establish that this surrounding explanation is supported.
4. Re-derive each load-bearing claim from current source evidence when tools or
   files are available. If source evidence is unavailable, say that rather than
   substituting memory.
5. If the answer reconciles sources that disagree, check that it commits to
   the official source. When the data does not say which source is official,
   the answer must name the source that the governing rule or source-of-truth
   registry picks and state that basis. The rule must be checkable (a registry
   entry, a documented definition, or the user), never taken from the answer
   being audited. With a checkable rule, "the data can't establish which is
   official" is a correction, not caution, and naming the other source is
   wrong. With none, the answer should name the source it used and why, say
   official status is unconfirmed, and say what would confirm it; an invented
   rule is the error.
6. Classify each material claim as supported, unsupported, garbled, overstated,
   missing caveat, withheld source, or not checked. For claimed members or
   exclusions, require an explicit mapping in the user's facts or source
   definition. A category label or conventional example is not that mapping.
   Preserve accurate scope limits and explicitly conditional statements: they
   do not assert that the unknown condition holds. Unnecessary wording is not
   automatically a factual error. Missing evidence also does not establish the
   opposite claim; distinguish an unverified wider result from a different one.
7. Rebuild the corrected answer from the supported facts and definitions. Retain
   correct calculations and useful supported explanations. Where a category's
   composition is unknown, use its agreed name rather than replacing rejected
   examples with a different list. Do not invent missing information to explain
   a correction or to predict the direction of an unspecified adjustment.
8. Check the actual rewritten answer, including its closing note, against the
   original evidence and the audit's classifications. No rejected assertion
   may return as a caveat, example, synonym or unconditional recommendation.
   If a new clause lacks support, remove it or state the specific unknown; do
   not ask for details needed only for optional commentary. Apply this check
   to the correction explanations and evidence notes too.
9. Lead with a verdict that distinguishes what was correct from what needed
   correction. Align confidence with those specific claims, not just the ease
   of the arithmetic. Give the corrected answer in plain language.

## Output Shape

- Verdict: one sentence stating what survived and what needed correction;
  do not approve the whole answer solely because its number was correct.
- Corrections: concise bullets for each unsupported, garbled, overstated, or
  withheld-source claim.
- Supported claims: mention only material claims that survived re-checking.
- Evidence: use the footer labels from `${CLAUDE_PLUGIN_ROOT}/references/evidence-discipline.md`
  when the audit depends on business/provider/customer or readiness evidence.
- Confidence: High, Medium, or Low, with the body matching the confidence.

Do not defend the prior answer. If the earlier answer was wrong, say what was
wrong and what the current evidence supports.
