---
name: claim-fidelity
description: Use before consequential technical diagnoses, root-cause conclusions, fix-verification claims or external factual drafts; when correcting a prior diagnosis; and when checking source scope, freshness, completeness, comparisons or causality.
argument-hint: "[claim, evidence, or draft answer to check]"
skill: claim-fidelity
plugin: llm-accuracy
fully_qualified: llm-accuracy:claim-fidelity
version: "0.2.0"
triggers:
  - pattern: "\\b(does (this|that) prove|can we conclude|claim fidelity|evidence supports|fully synced|same population|complete data|source is current|provisional result)\\b"
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

## Technical investigations

- Pin the affected process, environment and version. A successful probe from a
  different process or network path may not reproduce the affected workload.
- Verify what the instrument measures: field definition, units, denominator,
  time window and parsing. Match structured status fields, not incidental text
  inside identifiers. Confirm that a throughput denominator measures the phase
  being discussed before interpreting the rate.
- Establish coverage before universal claims. Count the complete input and the
  matching subset programmatically; a preview, sample or displayed page cannot
  establish a total. Preserve unknown coverage even without a truncation marker.
- Keep competing causes until a discriminating test supports one. Correlated
  candidates do not establish which caused the symptom. If a test is unavailable,
  report the diagnosis as a hypothesis and name that test.
- On a correction, identify the new evidence, replace the specific claim and
  revisit dependent recommendations or drafts. Repeated reversals are a reason
  to reconsider the framing, not to present the next guess more confidently.
- Before a fix-verification claim or an external draft, check each load-bearing
  fact against relevant evidence. A successful command is not proof of the fix;
  earlier evidence may still be valid when its source, version and scope match.

Use these checks proportionately. Do not invent uncertainty for a directly
verified fact or require new tool calls merely to repeat still-valid evidence.

## Output

For a substantive technical diagnosis or verification claim, lead with the
conclusion and its uncertainty, then end with three short evidence bullets:

- **Checked:** checks actually performed, their result and relevant scope. If
  none were performed, say so; proposed checks do not belong here.
- **Gap:** unresolved causes, incomplete coverage or untested environments.
  Say no material gap identified only when the evidence supports that statement.
- **Next:** the smallest action that resolves the gap, or none if no action
  remains within the requested scope.

Do not add this footer to greetings, acknowledgements, creative tasks or routine
replies without a diagnosis or verification claim. It is a model-written account
of evidence, not an independently validated receipt. Never hide a material
qualification in the footer while stating certainty in the answer body.

For an explicit claim-by-claim audit, use the fuller format instead:

- **Claim:** the exact conclusion checked.
- **Status:** supported, qualified, withheld, or unchecked.
- **Evidence boundary:** what the observed evidence establishes.
- **Overreach:** any unsupported extension in scope, completeness, freshness,
  comparison, or causality.
- **Next check:** the smallest check that would resolve the material gap.

Do not manufacture certainty because an answer is labelled provisional or
because a tool returned without an error.
