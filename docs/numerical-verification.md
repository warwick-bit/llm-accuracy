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

The original repository CLI remains available:

```text
python scripts/numerical_claims_demo.py source.json claims.txt
```

It delegates to the packaged checker. Results bind the actual checker bytes.
The checker recognizes two revenue-claim forms; it does not prove a whole answer,
authenticate sources or replace the assistant's raw-source and interpretation audit.
