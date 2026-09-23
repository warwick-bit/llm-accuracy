# Probe failure diagnostics

The Claude host probe waits for a final `result` for each conversation turn.
A timeout does not establish that authentication failed, a hook hung, or the
model stopped generating. Partial text can still be arriving without a final
answer.

Failed captures include a `progress` object containing only counters: turns
sent, events and results received, text updates and character counts, and the
largest repetition count of a nonempty line. Partial text and stderr remain in
memory and are never included in this object. Repetition is diagnostic evidence,
not a heuristic that aborts or approves a response. Counts span the whole probe.

Interpret the counters together:

- No events: the probe observed no complete JSON event before failure.
- Text updates but no result: generation was observed, but no final answer was
  captured. Repetition counts can reveal repetitive generation.
- Fewer results than sent turns: the conversation did not finish.
- All results present: process shutdown or stream closure may have timed out.

These are cumulative observations, not proof of activity at the deadline or a
provider-side root cause. Whitespace contributes to total characters but not
non-whitespace characters or the nonempty-line repetition count.

Timeouts still return `answers: []` and must not be scored, even when an earlier
turn completed. The hard deadline, capture-size limit, model, effort, prompts,
and owned-process cleanup remain in force. Partial streaming increases captured
bytes and therefore may reach the existing capture-size limit earlier.

For small conversational probes, explicitly bound each answer with
`run_probe(..., max_response_chars=8000)`. This is an opt-in character limit,
not a token or cost limit. It includes whitespace and resets after each final
result. Text that exceeds the limit stops the owned process and returns
`status: response_limit`, `answers: []`, and the same safe progress counters.
The triggering event may overshoot the character limit; the independent total
capture-size limit still applies. A completed result is checked as well, so a
host that emits no partial events cannot bypass the answer limit.

There is no automatic retry, model switch, truncation into a passing answer, or
change to the default response budget. Existing callers remain unbounded by
this optional character limit until they explicitly select it. Pick the budget
for the intended task; a short conversation and a large review need different
limits.

Do not retry until success and present only the successful result. Any change to
models, response budgets, prompts, or retry policy in a registered comparison
requires a new declared comparison applied consistently to both arms. A provider
generation loop cannot be repaired by interpreting partial output as approval.
