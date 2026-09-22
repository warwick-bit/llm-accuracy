# Analytical review (experimental)

Use this optional Claude Code skill for a second review of SQL, calculations,
financial analyses or systems logic. Supply the question, work and definitions:

```text
/llm-accuracy:analytical-review Review reports/revenue.sql against docs/revenue-definition.md; check grain, totals and period boundaries.
/llm-accuracy:analytical-review Review forecasts/model.md and forecasts/assumptions.md; recompute material values and identify unsupported assumptions.
/llm-accuracy:analytical-review Review docs/payment-events.md; trace duplicate delivery, partial failure and recovery against its stated requirements.
```

Claude Code runs the skill in a foreground subagent (`context: fork`). The
subagent does not receive the parent conversation history, so include explicit
artifact paths and requirements. This reduces reliance on the author's narrative;
it does not guarantee independence or accuracy. Project instructions, supplied
context and the host's tool permissions still affect the review.

The skill is also available for Claude to select on matching review requests;
it is not an always-running review hook. This branch is a draft candidate, not a
released plugin update.

The reviewer examines methods and material conclusions, performs authorized
calculations when tools are available, and distinguishes wrong results from
missing evidence. It reports findings and checks, without fixing the artifacts.
Read-only behavior is an instruction, not a sandbox. The skill grants no provider
access and supplies no accounting policy or canonical metric definition.

The workflow asks Claude not to save inputs, outputs or receipts. Host conversation
retention still applies. This new command's native behavior is tested in Claude
Code only; other hosts are unverified.

`self-audit` checks the assistant's previous answer; `claim-fidelity` checks whether
claims stay within their evidence. This skill provides a separate artifact-review
entry point with domain checks. It is experimental: **better performance than a
plain review request or the existing audits has not been established**.

See the [evaluation contract](analytical-review-evaluation.md) and
[exploratory results](analytical-review-results.md) for scope and limitations.
