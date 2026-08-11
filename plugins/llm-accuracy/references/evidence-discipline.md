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

## Partial results

A page is not the set. When a result declares partiality — `has_more`, a next
cursor or page token, `truncated`, a row cap, or a total that exceeds the rows
returned — either keep paginating until the source is exhausted or report the
answer as partial and name what was actually read: rows seen, pages fetched, and
cursor state.

Silence is not coverage. The absence of a partiality marker is not evidence that
a result is complete, because many sources cap quietly. Treat unknown coverage as
a data gap, not as a confirmed full set, and do not let a declared total that was
never reconciled against the rows in hand stand in for one that was.

### What the automated sentinel covers

The `PostToolUse` sentinel is a narrow backstop for the rule above, not a
substitute for it. It reads one tool result at a time and keeps no state, so it
can never observe that a later page was fetched and can never certify coverage.

It detects, in the response envelope only: boolean partiality flags (`has_more`,
`hasNextPage`, `truncated`, `is_truncated`, `row_cap_hit`, and
`pagination_complete: false`); populated next-page cursors, page tokens, offsets,
`links.next`, and `@odata.nextLink`; exact machine warning codes in an envelope
warning collection; a GraphQL Relay `pageInfo` block reached through nested
dictionaries; and the host's own over-budget notice when it replaces an oversized
result with a pointer to a file.

It deliberately does NOT do the following, and you remain responsible for each:

- **Compare a declared total against rows returned.** A bare total is ambiguous —
  an invoice total, an aggregate, and a record count are indistinguishable — and
  binding a total to the right list is not solvable generically. Reconciling a
  total against rows in hand is your job, not the hook's.
- **Read record content.** Row arrays are never inspected, so a column named
  `has_more`, a cell whose value is `row_cap_hit`, or a `pageInfo` object nested
  inside a record array will not raise a signal.
- **Detect undeclared caps.** A source that silently truncates emits nothing to
  detect.
- **Read flags whose names are ordinary business vocabulary.** Salesforce's
  `done: false` and Jira's `isLast: false` do declare a further page, but the
  same fields appear on task records, job statuses, and survey questions, where
  firing would be wrong. They are left out deliberately; a paired cursor
  (`nextRecordsUrl`, `nextPageToken`) is what gets detected instead.
- **Infer partiality from offset arithmetic.** A classic `startAt` /
  `maxResults` / `total` triple, or an Elasticsearch `hits.total` above the hits
  returned, states partiality only by arithmetic on an ambiguous total. That is
  the declared-total case above, and it stays yours to reconcile.

A signal is evidence of partiality. Its absence is not evidence of completeness.

## Boundary

LLM Accuracy improves evidence hygiene. It does not independently establish
domain definitions, retrieve new evidence, or guarantee correctness.
