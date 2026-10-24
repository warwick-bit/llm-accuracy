# Check a numerical report against its sources

The optional Accuracy plugin now packages the [verification workflow](../plugins/llm-accuracy/references/numerical-verification.md)
and its bounded checker. In Claude Code with this local candidate installed:

```text
/llm-accuracy:verify-numerical Check this report against these sources.
```

Claude can also select the skill for relevant ordinary requests. Automatic
selection is advisory, not guaranteed. Coding and nonnumerical claims use the
existing verify-technical and claim-fidelity workflows instead.

For local Codex testing, register this checkout as a marketplace and install its
experimental skills-only package in the intended Codex profile:

```text
codex plugin marketplace add /absolute/path/to/this/checkout
codex plugin add llm-accuracy@llm-accuracy
```

Start a fresh session. Ask normally or invoke `$llm-accuracy:verify-numerical`.
The Codex package exposes three shared verification skills and no automatic hooks.
Claude keeps its existing advisory session reminders. Installation in an isolated
test profile does not enable either package in your everyday profile.

For the same local candidate in Claude Code:

```text
claude plugin marketplace add /absolute/path/to/this/checkout
claude plugin install llm-accuracy@llm-accuracy
```

Start a fresh session after installing. If this marketplace name already points
to a different checkout or the published repository, inspect that registration
before changing it so the intended source is clear.

The 24 October 2026 local WSL trial exercised one four-turn session each in
Codex 0.160.0 (Sol6.1) and Claude Code 2.1.310 (Sonnet5.5): report checking, a
source correction, a coding bug and planning with incomplete approvals. Both
consumed the installed package and produced correct results on those tasks.
This is a local candidate, not a published release or evidence of universal
reliability. Native Windows, macOS and Desktop delivery remain unqualified for
this change; see the [scope and checks](plans/bundle-publication.md#installed-mixed-workflow-result--24-october-2026).

The original repository CLI remains available:

```text
python scripts/numerical_claims_demo.py source.json claims.txt
```

It delegates to the packaged checker. Results bind the actual checker bytes.
The checker recognizes two revenue-claim forms; it does not prove a whole answer,
authenticate sources or replace the assistant's raw-source and interpretation audit.
