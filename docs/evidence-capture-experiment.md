# Evidence capture: development baseline and feasibility

Status: experimental tooling outside every distributed plugin. No plugin release
or accuracy improvement is proposed by this change.

The [first native feasibility receipt](validation/evidence-capture-feasibility.json)
records both arms passing on Claude Code 2.1.280, Linux, reported Sonnet 5.
Control and candidate took 4.8 and 7.5 seconds respectively; these single runs
do not estimate overhead. Each inventory included the public accuracy plugin
and an additional telemetry plugin. No MCP was reported; no profile JSONL file
was found before cleanup. Both temporary directories were removed. Native
Windows, unprompted use of observations and behavioral accuracy remain untested.

## General problem and competing explanations

Technical assistants can claim a fix, diagnosis or deployment without adequate
support, or reverse a supported answer under pressure. Plausible causes include
missing observations, wrong environment/revision, unsupported inference despite
adequate evidence, lost corrections, user-agreement pressure and conflicting
instructions. The inaccessible configuration of any particular user is not an
assumed cause. These experiments use synthetic generic technical work only.

Three approaches were considered: more advisory wording; mechanically captured
observations; another model reviewing the answer. The first already exists in
the technical skill. The earlier tool-free reviewer did not demonstrate added
benefit in the declared conversational trial. Capture is the next feasibility
question, not an established general solution. Capturing evidence does not
establish that a model interprets it correctly.

## Development baseline

`scripts/accuracy_baseline_cases.py` provides ten authored development cases:
unrelated passing check, local reproduction positive, environment switch,
build-age ambiguity, incorrect correction, source-supported correction,
conflicting reports, partial coverage, missing evidence, and routine naming.
Nine have fixed multi-turn scripts, including vague requests and closure
pressure. Inputs are separate from evaluator expectations. The tiny retry
fixture is executable: the before implementation stops at a transient error;
the after implementation tries the next response. It produces observations,
not model-assigned correctness labels. Other records are explicitly synthetic
reports, whose truth does not follow merely from reading them.

This is **not a held-out benchmark**. Its author knows its cases and rubrics.
No live baseline cohort runs automatically. A future runner must expose only
the selected case's `model_input`, keep the oracle inaccessible, and permit
only its fixture tools. An independent author must create transfer cases after
the candidate freezes; never tune against those cases.

For the later baseline, the unit is the full conversation, including every
assistant progress message and final answer. Inspect all cases at the first
small rung. Ground execution claims in fixture traces. Adjudicate unanticipated
claims and entailment against the actual evidence, not keyword matching, footer
presence or a model's own verdict. Record `supported`, `unsupported`, or
`disputed` with case/turn/claim index, category and in-memory quote offsets;
persist no response text. A second model's agreement is not ground truth.

Measure unsupported claims AND useful task completion, unjustified reversals,
unnecessary clarification and latency. Wrong user corrections must not become
authority. Transport, tool-access and adjudication failures remain separate;
exclude invalid paired runs from both arms' quality denominator. Report their
attrition. A tiny all-clean baseline has insufficient headroom, not proof of
effectiveness or ineffectiveness. Freeze a practical effect threshold and sample
size before any efficacy comparison, after a development incidence estimate.

## Frozen feasibility protocol

Question: can this installed Claude host expose a successful Read observation
to a small hook and deliver an additional observation to the model while
preserving the original tool result?

Run `python3 scripts/evidence_capture_smoke.py --live --model <model>`. The model
is explicitly selected; effort defaults to medium. One silent-control request
then one additional-context request, each with a fresh temporary profile/cwd,
120-second timeout and no retries. Stop at the first failed arm. A failure is
an ambiguous plumbing observation, never an accuracy score. Diagnose offline;
any later live attempt needs a documented protocol amendment.

Both arms explicitly load the current public accuracy plugin, plus identical
test-isolation hooks. Only the experimental emission switch changes. Tools are
limited to Read; MCP configuration is empty. An exact-path PreToolUse rule
allows only the generated fixture; aliases and partial reads that do not return
the full expected content do not pass. The hook never resolves/reads a path
supplied by the model. This blocking isolation is **test infrastructure only**;
the public plugin remains stateless and advisory. The profile is explicitly
denied to Read. No skills or native session persistence are enabled.
The runner copies the existing local CLI credential file into the private
temporary profile with restrictive permissions, without printing its contents;
profile removal also removes this temporary copy.

The file and hook receive separate random 128-bit markers. The observation
marker is absent from the user prompt and file; it appears only in candidate
additionalContext. Prompts explicitly request markers, so success measures
delivery, not normal-task uptake. The hook compares the host's returned content
to the known fixture in memory, writes only fixed typed booleans to a temporary
receipt, and never substitutes the tool output. It makes no claim that reading
a reported test pass proves test execution or factual correctness.

Acceptance requires both completed arms, public fidelity-hook activation,
matching reported model identities, no MCPs, valid observed fixture content,
the exact source marker, and respectively `none` or the exact observation
marker. Duplicate, invented or missing marker lines fail. Negative-control
tests exercise the actual scorer. Host inventory records extra components;
activation does not establish full absence of managed/built-in context.
The temporary observation receipt represents the most recent expected-path
Read, not a complete tool-call history. A partial read followed by a complete
read can pass; this establishes at least one matching observation. The fidelity
activation count measures prompt-hook delivery, not the number of tool calls.
Early host/auth failures have shorter result objects; consumers must check
`passed` and `host_status` before reading optional check fields.
Temporary directories are removed; JSONL file counts in the isolated profile
are checked before removal. This is not a claim about provider retention.
Only typed receipts, counts, hashes and duration are emitted, never answers.

The live runner currently supports POSIX hosts. Cross-platform unit checks
cannot establish native Windows host behavior. No general capture adapter,
cross-session storage, transcript monitoring or automatic command rerun ships.

## Next experiment, conditional on feasibility

Start with completion-state claims, comparing current plugin, captured
observations, and observations plus status guidance at matched budgets. Include
positive and negative cases, relevance of the test, source freshness and scope.
An observation adapter must name what it actually establishes; do not promote
"tool returned" into "test passed", or "test passed" into "bug fixed".

Correction handling and bounded local-harness ablations remain separate later
experiments. A smoke pass does not justify promoting a wider cohort's results,
a second-model product feature or a release.
