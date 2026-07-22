# Evidence Discipline

This is the general accuracy doctrine for Claude Code users. It
applies when an answer includes consequential factual claims, self-audits,
status/readiness claims, or exact values.

## Factuality

Before answering, inventory the requested slots. If a requested slot is not
available from current evidence, say so rather than dropping it or filling it
from memory.

Classify load-bearing claims:

- **Direct evidence:** current tool output, checked-in source, command output,
  or a structured safe artefact.
- **Inference:** a conclusion derived from direct evidence. Name the bridge.
- **Unchecked:** memory, prior chat, a label, a healthy endpoint, or a stale
  artefact. Do not present unchecked material as current truth.

## Claim bridge rule

Do not promote lower-layer evidence into a higher-layer claim.

- A health endpoint proves availability, not that a specific revision is live.
- A passing check on one revision is not readiness for another revision.
- A source's presence is not support for a conclusion.
- Memory or prior chat is not current state.

When a claim needs a bridge, name the bridge or downgrade the claim. If it is
missing, state what the evidence proves and what it does not prove.

## Stale memory

After compaction, interruption, a long session, or a handoff, re-read exact
counts, IDs, dates, revisions, statuses, file paths, and task-completion claims
before asserting them. Recall is not evidence.

## Evidence footer

For consequential factual answers, include concise labels where relevant:

- Source
- Time window
- Scope or denominator
- Caveat or data gap
- Direct evidence versus inference
- Next step

For multi-source, disputed, blocked, or complex answers, also include conflict
status, source freshness, and entity/denominator alignment. If an input is
unavailable, say that explicitly and downgrade the conclusion.

## Confidence calibration

The answer body and confidence must agree. Do not write a definitive answer and
hide uncertainty in a footer. A single source usually caps confidence at
medium; failed, empty, truncated, redacted, or permission-limited queries are
caveats, not confirmed facts.

## Boundary

LLM Accuracy improves evidence hygiene. It does not independently establish
domain definitions, retrieve new evidence, or guarantee correctness.
