# Evidence boundaries and answer publication

This guide is for application authors. The bundled public plugins remain
advisory and non-blocking. They do not implement the publication boundary
outlined here, and this guide is not an accuracy benchmark or a release claim.

## A correct warning can accompany an unsupported answer

Consider this fictional example, created for this guide:

> A questionnaire of 70 evaluation accounts reports 61% completed onboarding.
> Does that establish the onboarding rate for every subscriber?

The supported statement preserves the questionnaire population and reported
percentage. It does not establish a rate for all subscribers. Without further
evidence, an answer must not add:

- an exact completion count inferred from a rounded percentage;
- an uncertainty interval calculated from that inferred count;
- a claim about which subscribers previously used an evaluation account; or
- a direction of response bias inferred merely from the word questionnaire.

A suitable minimum answer is: “The questionnaire reports 61% for its 70
evaluation accounts. That does not establish the rate for all subscribers.
Confirm raw counts, the sampling method and the onboarding definition before
calculating uncertainty or describing bias.”

Conditional reasoning remains useful: “If the respondents were sampled at
random under an appropriate sampling model and the raw counts were supplied,
an interval could be considered.” The condition must not be presented as known.

## Separate three designs

```text
Design                   What it can establish             Remaining boundary
Advisory prompt           Gives evidence-handling guidance  Model can ignore or extend it
Typed answer receipt      Checks declared fields/schema    Declaration is not source proof
Host-owned publication    Releases only validated content  Requires control of every output path
```

A receipt needs independent evidence binding: trusted source captures, a
host-issued request identity, and checked operations. Binding can occur in memory
without retaining the raw capture after validation. A model inventing both
an answer and its supporting receipt does not create corroboration. See the
[tool-failure guide](tool-failure-contract.md) for refresh and failure semantics.

A host-owned renderer can keep factual fields outside model control. It does
not validate the upstream source, the chosen population, or the suitability of
a calculation unless those checks are implemented separately. Unrestricted
model prose beside a checked fact card remains an unchecked output path.

## Check the runtime before choosing an enforcement hook

Answer generation, streaming, completion callbacks, display and saved history
are different surfaces. A completion check cannot retract text already
streamed. A display replacement is not enough if original text remains in
another export, transcript or client view. A hook that stops generation may
also hide its explanation, leaving the user without the supported answer.

For each client and version, inspect the real event payload and record whether
it can observe the answer, stop publication, replace it, and preserve a useful
failure explanation. Do not infer desktop-client behaviour from a command-line probe
or one runtime's behaviour from another's. Keep checks optional/advisory when
that is the only supported contract; document the limitation explicitly.

For a finite, fully specified request, application code may be able to return
the minimum answer before inference. Match the entire supported request and
preserve supplied values. Rejecting or ignoring additional evidence to force a
match would create a new accuracy problem. A finite template is a narrow
product feature, not a semantic solution: paraphrases and follow-up turns need
separate handling, and a bypassable template is not a security boundary.

## Test the claim, not just the process exit code

Use independent positive, negative and limitation controls:

```text
Case                         Required observation
Supported request            Minimum supported answer actually reaches user
Unrelated request            Normal answer remains available
Extra evidence/conditional   Evidence is preserved; no forced template override
Invented count or interval   Rejected by the claimed publication boundary
Invented bias or population  Rejected by the claimed publication boundary
Valid conditional reasoning  Allowed without upgrading assumptions into facts
Failed refresh               No old value silently promoted to current evidence
Invalid retry                No retry flag bypasses the publication check
Malformed hook input         Documented failure behaviour; no verification claim
Streaming/export/history     Every claimed protected surface tested separately
```

Record exactly which rows were executed and which layer they exercise. An
injected bad draft tests the checker; it is not spontaneous model fabrication.
An exact-text mismatch is not automatically a factual error. A process that
exits successfully may still hide the answer or fail to invoke the checker.
A model call count of zero can demonstrate a pre-response path when the
lifecycle evidence supports it, but does not establish broader accuracy.

Measure false blocks and answer availability as well as rejected errors. Keep
retries bounded. A maximum retry count must end in a clear unavailable outcome,
not release the last invalid draft. Broader efficacy requires held-out phrasing,
independent scoring and an adequate comparison; a demonstration is insufficient.

## Privacy and distribution review

Prefer metadata-only receipts: runtime/version, event names, outcome codes,
call counts and explicitly scoped assertions. Avoid persisting raw requests,
answers or source captures by default. Even metadata such as content hashes
can be identifying; retain only what the investigation needs. A stateless hook
does not make its host runtime's conversation history stateless.

This document is a newly authored, provider-neutral abstraction of publication
boundary lessons. Its example is fictional. No private implementation,
transcript, runtime receipt, business data or internal identifiers are included.
The deliberate downstream divergence is unchanged: these public hooks stay
advisory; blocking enforcement and host-controlled rendering belong to the
integrating application. No packaged plugin files or versions change here.
