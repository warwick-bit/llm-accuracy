# Technical behaviour checks

Hypothesis: general evidence guidance should preserve supported factual fields,
reject unsupported technical conclusions and add compact evidence footers only
where appropriate. This exploratory suite is not a release or accuracy-lift gate.

Run from the repository with an existing Claude Code subscription login:

```sh
python3 scripts/eval_technical_behavior.py --live
```

The full declared population is eight synthetic conversations: sampling,
competing causes, denominator arithmetic, wrong environment, a supported local
fix, conflicting sources, a two-turn correction and a routine greeting. Each
case runs once per arm. Baseline and candidate use the same requested model
(`--model`, default `sonnet`), provider sampling defaults, isolated temporary
profiles and working directories, no tools or MCPs, and no saved session.
Only the candidate loads this plugin. Hook events attest delivery and detect
baseline contamination. Turns are sent after the preceding result event.

The factual oracle compares exact declared Answer fields with author-owned
expected values, comparing decimal numbers by value (for example, `20.0` and
`20` are equal) without rounding. Missing, duplicate or ambiguous fields fail the output
contract. A malformed field is a formatting failure, not proof of a wrong belief.
Footer labels must be unique, nonempty and appear in Checked / Gap / Next order
on the final three nonblank lines. They are measured separately; a correct footer cannot rescue a wrong
fact. The routine control detects footer overapplication. Arbitrary explanation
text and the truthfulness of footer prose are **not scored**. This is packet
synthesis, not a test of tool selection, source retrieval or execution of skills.

Infrastructure, authentication, timeout and activation failures exclude the
entire pair from both comparison denominators. Output reports fixed case IDs,
status codes and counts only; raw answers remain in memory. Exit zero means the
run is scorable, not that all quality checks passed. Desired regression targets
are all seven factual cases passing and no routine footer; footer coverage is
reported without treating every short arithmetic answer as a required footer.
Do not tune the cases or oracle to make a run pass.

Variance is unmeasured at one run per case/arm. There is no same-length placebo,
and model aliases may change. No result from this suite establishes causal
accuracy lift, broad factual correctness, or parity on another machine. Use a
pinned model, repeated runs, independent free-prose scoring and a matched
placebo before making stronger claims.

## Tool-output coverage

Claude's [PostToolUse reference](https://code.claude.com/docs/en/hooks#posttooluse)
describes a tool-dependent structured response. The built-in detector uses only
observed host fields: Read `type=text` and integer `startLine`, `numLines`,
`totalLines`; Bash `persistedOutputPath`, integer `persistedOutputSize` and
`stdout`. Saved size is compared with UTF-8 bytes, not character count. These
fields are host-version-dependent and missing metadata stays silent.

`scripts/measure_builtin_result_corpus.py` reports aggregate detections against
the previous MCP-only registration (zero built-in invocations). It does not
claim independently labelled precision/recall. Exclude the development session.
The existing `measure_tool_result_corpus.py --compare-hook` remains the separate
same-snapshot MCP regression comparison. Neither script emits transcript data.

## Distribution boundary

Only the explicitly invoked `accuracy_doctor.py` and `host_probe.py` may import
subprocess in the accuracy package. The doctor executes package commands and
reads the host plugin listing; `--live` opts into a synthetic model request.
Network-library imports remain excluded, and automatic hooks have no subprocess
exception. The live runner temporarily copies the existing subscription auth
file, deletes that temporary profile on exit and never prints its values. The
pattern scanner is a packaging guard, not a security sandbox for arbitrary code.

## Candidate observation — 23 Sep 2026

The [typed receipt](validation/technical-behavior-2026-09-23.json) records the
post-review candidate and scorer identities. All eight pairs were scorable.
Both arms passed all seven factual cases, with no invalid Answer fields. The
candidate emitted complete footers in five technical conversations; baseline
emitted none. Neither arm emitted a greeting footer. The denominator and
two-turn correction cases did not have complete candidate footers on every turn.

This run followed fixes for decimal-value comparison. An earlier candidate run
recorded baseline 6/7 and candidate 7/7; those historical results were not
rescored or pooled. The current observation shows no factual-field advantage.
It neither establishes nor rules out improvement on real technical work.

## Natural footer comparison

`eval_footer_behavior.py` compares two loaded plugin versions on the same pinned
model. It uses natural synthetic questions with no requested Answer field or
footer. Extract a trusted released plugin ZIP into a temporary directory, then run:

```sh
python3 scripts/eval_footer_behavior.py --live --baseline-plugin /path/to/released-plugin --rung ramp
python3 scripts/eval_footer_behavior.py --live --baseline-plugin /path/to/released-plugin --rung full
python3 scripts/eval_footer_behavior.py --live --baseline-plugin /path/to/released-plugin --rung repeat
```

The default model is `claude-opus-5-5`; a missing or different resolved model
makes the pair unscorable. Both arms must deliver fidelity guidance on every
turn. The ramp is one two-turn causal/scope case. Full adds deployment scope,
conflicting build reports, thanks and a creative slogan. Repeat runs the three
technical cases unchanged once more. Each arm runs sequentially with provider
defaults and the same tool-free, auth-only isolation as the field suite.

This measures footer presence and routine/creative overapplication only.
Natural-prose correctness and the truthfulness of Checked/Gap/Next content are
**not scored**. A zero exit means all pairs were scorable, not that the candidate
passed a quality threshold. Treat each rung separately; do not pool the repeated
cases as independent examples or keep rerunning until a preferred result appears.

### Bounded transport recovery

Choose `--transport-attempts 2` or `3` **before** a natural-footer run to recover
from incomplete host calls. The default remains one attempt. Each attempt runs
both versions; a timeout, missing result or host transport error discards both
answers before another whole-pair attempt, with the order reversed. A completed
pair is never retried because of its footer or factual quality. Authentication,
rate limits, wrong model identities and activation failures stop recovery.

Every attempt's fixed status codes, validity and result counts are reported in
`transport_attempts`; raw answers stay in memory. Report failures and recovery
rates alongside any comparison. Recovered results describe successfully completed
pairs, not the unsuccessful calls, equal reliability or general accuracy. The
per-call timeout still applies, so three attempts can cost up to six calls per
case. Cancellation immediately stops the run.
# Full-answer follow-up

The [0.6.2 transfer check](release-0.6.2.md#behavioral-evidence-and-limits)
adds a separate, model-adjudicated view of intermediate and unlisted claims.
Its authored cases, disagreements and excluded instrumentation attempt are
recorded separately. This does not change the constrained-field or footer
scorers into general factuality validators. No raw model answers are retained.

## Polarity follow-up: wording withheld

A later experiment tested more explicit unknown-versus-absent wording and
courtesy replies that add no unverified status. The
[typed result](validation/polarity-comparison-2026-09-23.json) records the
failed promotion gate. The released plugin remains at 0.6.2 with identical
package contents; this follow-up changes repository evaluation tooling only.

Opus 5.5, medium effort, completed an author-exposed synthetic packet against
0.6.2. Each scored pair required the expected model and isolated inventory,
plus exact ordered reminder text observed in host hook events. Fable 5.1 judged
each arm separately, twice with reversed order, after matching all 25 authored
calibration labels in both passes. These are two passes of one fallible judge,
not independent ground truth. No raw answers were retained.

```text
Stage       Cases  Turns per arm  Candidate supported twice  Extra pair attempts
Initial     1      2              2                          1
Ramp        3      3              3                          0
Controls    4      6              6                          0
Repeat      4      5              5                          0
```

All candidate turns also met the footer boundary and had no judge-detected
unlisted assertion. The initial released incident answer had a judge
disagreement, so its case was not counted as a clear advantage. The build-label
case supplied the sole clear initial advantage; both versions passed it on
repeat. The incident case showed an advantage only on repeat, so it could not
count as replicated either. The frozen gate required at least two advantages initially and on
repeat. None replicated, so the wording was withheld without changing the gate.
Passing the candidate controls does not establish a general accuracy benefit.

The initial pair recovered from one released-arm timeout by discarding both
answers and rerunning both arms in reversed order. All other pairs completed
on their first attempt. This demonstrates bounded recovery in that run, not a
fix for the underlying intermittent host stall or equal completion reliability.
Earlier one-shot attempts remain inconclusive; no partial answer was scored.
The exact-context observer and full-answer judge were local experimental tools;
the public footer runner still scores footer structure only.

The generic whole-pair recovery helper is repository-only tooling. Comparison
with private upstream revision `6909f8efef44d8afc33b60fba0405d5b10336d33`
found no corresponding paired footer runner to backport. No shared hook,
evidence doctrine, private runtime or packaged plugin changes are promoted.
