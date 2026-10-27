# LLM Accuracy 0.8.4

This stable release adds Clarify and strengthens Self-Audit across the LLM
Accuracy workflows. Install or update LLM Accuracy from the repository
marketplace in Claude or Codex; Clarify and Self-Audit are included in the plugin.

## Changes

- Clarify asks for unresolved choices that materially affect an answer, using
  the host's interactive question tool when available. It follows the user's
  language preferences, with plain English as the default.
- Explicit definitions, requested alternatives and authorized assumptions proceed
  without unnecessary questions. A selected definition stays settled while a
  missing amount is requested separately.
- Numerical answers preserve the chosen population, units, period and cost
  definition. Explanatory notes should stay within the supplied evidence too.
- Self-Audit separates original evidence from the assistant's prior assertions,
  checks the corrected answer, and preserves accurate conditional caveats.
- Codex now exposes Self-Audit alongside Clarify, claim-fidelity,
  verify-numerical and verify-technical. It remains skills-only, with no hooks.
- Claude Code's session mode includes a short clarification reminder on each
  request. Existing targeted mode and disable controls remain available.

The plugin adds no telemetry, persistent memory, connector or external service.
The separately installed Deterministic Data, Session Ledger and Evidence Memory
plugins retain their own versions and support boundaries.

## Install or update

In Claude, open **Customize → Plugins**, add a marketplace from a repository,
and enter `https://github.com/warwick-bit/llm-accuracy`. Install **LLM Accuracy**.
If already installed, refresh/sync the marketplace and update the plugin.
Confirm **0.8.4**, then start a new conversation.

In Claude Code:

```text
/plugin marketplace add warwick-bit/llm-accuracy
/plugin install llm-accuracy@llm-accuracy
```

Existing Claude Code users should refresh the marketplace and update the plugin
through the plugin manager. In Codex, add the same repository URL in the plugin
marketplace, then install or update **LLM Accuracy** and confirm **0.8.4**.
This is distribution through the repository's two marketplace catalogs, not a
claim of acceptance into either vendor's curated directory.

For an explicit check in Claude, use `Use llm-accuracy:clarify.` or
`Use llm-accuracy:self-audit.` In Codex, select the corresponding installed skill.

## Qualification and limits

The [native live bundle receipt](validation/claude-bundle-smoke-0.8.4.json) and
[Accuracy installation/archive receipt](validation/claude-code-smoke-0.8.4.json)
bind qualification to the released package bytes. Publication also requires the
full release gates, including native installation and installed-hook checks on
Linux, macOS, and Windows with and without Git Bash.

Maintainer-reported Chat and Cowork trials on the dev.14 instructions preserved
correct arithmetic and valid conditional caveats, and removed unsupported
category exclusions. These focused trials are not a reliability rate or complete
Desktop installation/upgrade/uninstall qualification. The compatibility matrix
keeps incomplete host checks visible. Chat does not run hooks; Cowork hook
delivery and ChatGPT Work installation remain unverified.

Skill selection and following its instructions depend on the model. Explicit
Self-Audit can still add imprecise explanation even when the corrected answer is
sound. The plugin helps with evidence discipline; it does not guarantee factual
correctness or automatic prevention of unsupported claims.
