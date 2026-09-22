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
expected values. Missing, duplicate or ambiguous fields fail the output
contract. A malformed field is a formatting failure, not proof of a wrong belief.
Footer labels are measured separately; a correct footer cannot rescue a wrong
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
