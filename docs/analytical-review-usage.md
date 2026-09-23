# Using the experimental analytical reviewer

This draft provides a named artifact-review workflow for Claude Code. It does
not establish that an additional reviewer prompt is more accurate than a plain
Claude review. Read the [free-form comparison](analytical-review-everyday-results.md) and
[earlier structured comparison](analytical-review-challenge-results.md) before
drawing performance conclusions. The skill is not part of a released plugin version.

With a plugin build containing this skill loaded, invoke:

```text
/llm-accuracy:analytical-review Review analysis.sql and findings.md against
metric-definition.md and the synthetic fixtures in fixtures/. Check whether
the query and conclusions meet that definition. Use only those files and local
read-only calculations. Report material errors, checks performed and unresolved
evidence gaps. Do not change files.
```

Supply the actual artifacts and requirements explicitly. The reviewer runs in
a separate subagent context, so “check what we just discussed” is insufficient.
The parent-supplied task and project instructions can still influence it; fresh
context does not make a review unbiased or correct.

## What to include

- **Data:** question, SQL dialect, query, schema, grain/key expectations,
  metric definition, date window and representative authorized fixtures.
- **Finance:** formulas or workbook extracts, units/currencies, period, supplied
  accounting or management policy, assumptions and reconciliation inputs.
- **Systems:** intended invariants, implementation or design, relevant operation
  trace, transaction boundaries, failure semantics and acceptance criteria.

Include correct examples as well as suspected failures. Ask for a small
counterexample when a method may be wrong: offsetting join errors can preserve
the total, and deduplicated events can still overwrite newer state. Definitions
and external evidence matter more than how forcefully the reviewer is prompted.

For a missing input, a useful result is an explicit evidence gap and the smallest
check that would resolve it. More confidence or agreement between models cannot
supply an exchange rate, prove a warehouse load complete or choose your policy.

## Relationship to the existing accuracy skills

Use self-audit to revisit the assistant's own answer and claim fidelity to check
whether claims preserve their supporting evidence. Use this reviewer when the
object is an artifact or method: a query, calculation, report or system design.
These purposes overlap. Running every skill in sequence is not a tested accuracy
improvement and may add cost, latency and repetitive findings.

The reviewer asks for read-only work and no saved review artifacts. These are
behavioral instructions, not enforced tool restrictions; host permissions and
conversation retention still apply. It supplies neither provider access nor a
canonical business definition. Do not treat a supported verdict as certification
of an entire dataset, financial statement or production system.
