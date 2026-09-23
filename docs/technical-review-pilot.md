# Explicit technical review pilot

The new command reviews a complete question/draft/evidence packet in a fresh
Claude context. It is explicit-only and advisory. The automatic reminders are
unchanged. It does not promise a resolution of general model overconfidence.

## Evidence and limits

The final prototype localized every seeded defect and left all clean controls
unflagged across ten authored synthetic cases, each run twice. The second run
reversed case order and evidence order while keeping IDs bound to their content.
The host reported `claude-fable-5-1`, medium effort, no tools/MCPs/Accuracy plugin,
and one shared host telemetry component. Each call had a 180-second timeout;
there were no quality rerolls or transport retries in this pilot.

Cases cover invented lifecycle status, patch absence inferred from a different
build label, unsupported cause, a draft instruction aimed at the reviewer,
attributed Closed with recovery unverified, a complete negative inventory, a
specific passing test, an omitted answer, separate unsupported/omitted topics,
and unwarranted refusal of a supplied narrow fact. Three cases are clean.

The predeclared gate checks each finding's category, literal unique quote span
and required/allowed evidence IDs. Every finding must cover a seeded defect and
all defects must be covered. Grouping or splitting compound defects is permitted;
extra findings on supported material fail. Omission anchors the question. Exact
duplicates fail, but differently quoted overlapping findings can remain.

These are hand-authored controls, not a representative sample of model-generated
answers or a treatment/control accuracy comparison. Repeating the same reviewer
is not independent truth. Same-topic independent-attribute omission is untested.
Source truth, evidence completeness, factual improvement after correction, and
resistance to arbitrary prompt injection remain unproven. The separate native
Opus-to-Fable call demonstrated transport and different reported model identities,
not an accuracy gain; its finding had no independent outcome oracle.

## Previous attempts remain failed

Two earlier reminder/answer-shape candidates failed their frozen first-pair
acceptance gates and were withheld. They are not included in this release.

The first reviewer pilot stopped on the deployment case: domain-specific
categories and a single-finding expectation conflicted with split findings.
The second used three general categories and coverage of compound defects;
its reverse repeat stopped when the injected draft produced both an unsupported
claim finding and an omission of the correct alternative. Neither failed pilot
was rescored. The third added a general rule against double-counting that same
issue and two controls ensuring independent omissions and overhedging remain
reportable. All ten cases then passed twice under the newly frozen gate.
This is development evidence on the same authored fixtures, not a held-out test.

## Reproducible structural boundary

[Typed receipt](validation/technical-review-pilot-2026-09-23.json) records the
original frozen dependency hashes and fixed findings, without model answer text.
[Authored fixtures](../tests/fixtures/technical-review-cases.json) contain only
fictional input and predeclared expected defect spans. The receipt records the
prototype, not a blanket certification of every later packaged build. The public
runner retains the exact tested reviewer prompt; parser/CLI/host-failure tests
and clean installation checks are separate release gates.

To run deterministic boundary tests without model usage:

```bash
python3 -m pytest tests/test_technical_review.py -q
```

Live use is deliberately opt-in. See the
[command guide](../plugins/llm-accuracy/README.md#opt-in-technical-review).

## Packaged command smoke

[Installation receipt](validation/technical-review-install-2026-09-23.json)
records the exact committed package, local marketplace installation, matching
installed files, normal/custom/bypass reminders and ZIP loading on Linux/WSL.
The first native-command run returned tool errors under narrow test permission
rules and failed. A diagnostic repeat also failed; neither produced a review.
With Bash and Skill allowed in the isolated synthetic test, the unchanged
package invoked the reviewer once, flagged the seeded unsupported lifecycle
status, preserved all presentation fields and reported unknown author identity.
This is a test-permission correction, not a successful reroll of a bad review.
Normal installations can ask for command approval. No user permission setting
is modified by the plugin. Native Windows and Cowork remain unverified.
