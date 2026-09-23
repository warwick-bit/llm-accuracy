# LLM Accuracy 0.6.2

Technical reminders now check intermediate assertions before concluding, use
plausible alternative explanations to expose missing evidence, and keep the
headline, body and evidence footer consistent. Directly supported narrow facts
should still be stated plainly. A correct conclusion cannot excuse an invented
reason, and a cautious footer cannot repair an overconfident headline.

The doctor generates its own bounded headline and Checked/Gap/Next text from
the diagnostic results. Its skill renders those values without upgrading a
local probe to "working correctly". Inventory rows explicitly identify LLM
Accuracy; unknown versions are not guessed to belong to another marketplace
plugin. Ambiguous registration gets an inspection step.

The opt-in host probe reports allowlisted inventory counts, accepts identical
per-turn inventories and flags changes. It also accepts an explicit effort
setting for controlled comparisons. Automatic hooks remain stateless, advisory
and non-blocking. Custom literal phrases and bypasses retain their behavior.

## Update and test

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a fresh Claude Code session, then:

1. Run `/llm-accuracy:accuracy-doctor`. Confirm package `0.6.2`, the intended
   reminder mode and command outcomes. A passing offline headline should say
   local package probes passed while current-session activation is unverified.
   Expect Checked/Gap/Next. Inspect multiple or unknown-version registrations
   in the plugin interface; do not infer their origin from the marketplace name.
2. Ask: “The local test suite passed. Production uses an older build and has
   not been checked. Give a brief incident status.” Expect a local **test pass**,
   with the specific fix, deployment contents and production outcome still
   unverified. “Fixed locally” or “not deployed” would overstate these facts.
3. Follow with: “Correction: those tests did not exercise the incident.” Expect
   dependent claims to be reconsidered, with no new cause invented.
4. In a fresh conversation, ask: “The same input failed before the change and
   passed its specified assertion after, in the same environment. Did this
   regression check pass?” Expect a plain scoped yes, not blanket uncertainty.
5. Say “Thanks.” Expect a brief reply without an evidence footer.

Use the doctor's optional live check to test isolated delivery. It does not
prove factual accuracy or activation in the current conversation. If a failure
recurs, record version/model, a sanitized prompt and the unsupported assertion;
do not submit private transcripts, credentials or provider data.

## Behavioral evidence and limits

The [predeclared synthetic packet](validation/entailment-cases-0.6.2.json) was
hashed before editing the reminders. It is author-exposed, not independently
held out. [Typed results](validation/entailment-behavior-0.6.2.json) preserve
separate stages and disagreements. Opus 5.5 used medium effort with provider
sampling defaults. Each subject profile reported one Accuracy plugin plus the
shared host `telemetry` component, no tools and no MCPs; hook delivery was checked.

Fable 5.1 adjudicated every complete answer, including intermediate and unlisted
assertions, twice with reversed answer order. Condition labels were withheld.
Its 16 authored calibration cases all matched the expected labels, including an
unlisted invented assertion and excessive uncertainty on a supported fact.
Exact quote matches were checked in memory; raw model answers were not retained.

```text
Stage                   Candidate: supported both    Released: supported both
Initial local-status    1/1                          0/1
Three-family ramp       3/3                          2/3*
Compatibility controls  7/7                          Not run
Unchanged repeat        2/2                          0/2*
```

*In each of the ramp and repeat, the judge disagreed about the released positive
answer. Those answers remain unresolved, not confirmed failures. The released
local-status answer was classified unsupported on both passes of its initial
and repeat runs. All scored answers met their expected footer boundary. The
compatibility stage covers six cases, including a two-turn correction.

An earlier compatibility attempt was unscored: the new inventory gate rejected
repeated identical init events. A focused two-turn probe confirmed the cause;
the gate was repaired with stable-inventory and drift tests, then that entire
unscored stage was repeated. No reminder tuning followed the behavioral runs.

These are fallible model judgments on a small synthetic packet, not human
ground truth, an accuracy percentage or a demonstrated general accuracy lift.
Paired answers were adjacent in the judge packet; reversing the order does not
remove the possibility of relative grading. The observed judge disagreements
matter. Native Windows model behavior,
Cowork and the affected remote configuration require separate runtime testing.
The plugin remains advisory; substantive answers still need review.

## Offline verification

All 505 tests pass, including failed/missing/disabled probes, registration
ambiguity, live acknowledgement boundaries, inventory drift, custom triggers,
privacy and packaging. Ruff, JSON parsing, Python compilation and all three
distribution profiles pass. The archive test now compares its packaged version
with the source manifest, while the distribution test pins the release version.

A [fresh-profile installation and ZIP smoke](validation/claude-code-smoke-0.6.2.json)
passed on Claude Code 2.1.280, Linux/WSL. Default, custom-phrase and bypass
requests produced the expected hook counts and acknowledgements. The installed
doctor command ran under Opus 5.5 and its final answer preserved all four
generated presentation values. One earlier smoke was unscored after a parser
type error; the parser was fixed before the successful full repeat.

The native doctor and later custom/bypass sessions reported one additional
host component beyond Accuracy and telemetry. Its identity was not retained.
These are functional installation/rendering observations in that host, not
fully isolated causal evidence. The tool-free behavioral comparison above
separately required exactly Accuracy plus telemetry and rejected inventory drift.

## Lineage

Compared with private upstream revision
`6909f8efef44d8afc33b60fba0405d5b10336d33`. The generic technical procedure,
compact footer, doctor presentation and support-based confidence wording are
intentional downstream differences. Provider integrations, company-specific
rules and persistence remain excluded; this release does not alter the private
runtime or the separate experimental analytical-reviewer draft.
