# LLM Accuracy 0.8.0

This release sends the general claim-fidelity reminder once per session
instead of on every prompt, and fixes three smaller hook issues.

**What changes for you.**

- **Once per session:** the general reminder is now added from `SessionStart`:
  at startup, resume and `/clear`, and again after every compaction, because an
  injected reminder does not survive the next one. Before, it was added to every
  non-empty prompt. Prompts that match a fidelity trigger still receive the
  detailed guidance and the `Checked / Gap / Next` footer rule on that prompt.
- **Every prompt is an option:** set the new optional **Claim fidelity reminder
  mode** in `/config` to `general` to restore the 0.6.0 to 0.7.2 behaviour, or
  to `targeted` for trigger-only guidance. Empty means `session`. A non-empty
  `CC_CLAIM_FIDELITY_MODE` in the environment still works and overrides the
  saved option; if you already set it to `general` or `targeted`, nothing
  changes for you. Unknown values now select `session`, not `general`.
- **`# fidelity-ok` mutes a prompt, not the session:** the marker still mutes
  that prompt's fidelity guidance, but it cannot remove a session reminder that
  is already in context. `CC_SKIP_CLAIM_FIDELITY=1` still mutes both.
- **Partial-read warning:** a `Read` with a `limit` the model chose no longer
  gets an excerpt warning, because the model already knows it read a slice. An
  offset alone still gets the warning, because the host can still cut the end.
- **Source-conflict reminder:** it now reads "Source reconciliation" instead of
  naming an internal protocol.
- **One label:** in `general` mode, a prompt that also matches a fidelity
  trigger gets one "CLAIM FIDELITY CHECK" label, not two.

`/llm-accuracy:accuracy-doctor` reports the effective mode, including a mode
saved in `/config`.

**Evidence and limits.** The change rests on the
[reminder-cadence evidence note](validation/reminder-cadence-2026-10.md), which
compared three arms that differ only in how an instruction is registered: on
every prompt, once from `SessionStart`, and not at all. Every arm also carried a
competing per-prompt banner. Decision rules were written before any model run.

- **This reminder (the footer instruction):** on Claude Opus 5.5, deep probes
  (turns 5 and 8 of 8) received the footer in 24/24 every-prompt, 24/24
  once-per-session and 0/24 no-reminder probes, 12 sessions per arm, which
  meets the predeclared "every prompt is redundant" rule. A 20-turn stress run
  with about 137k characters of filler gave 8/8, 8/8 and 0/8. A smaller Claude
  Sonnet 5.5 screen (4 sessions per arm) gave 8/8, 8/8 and 0/8.
- **A behaviour-changing reminder:** a pointer that asks Claude to read a
  metric registry before quoting a metric met the same rule on Claude Opus 5.5
  and on Codex `gpt-5.5`, including a variant with a competing route to a
  direct answer. A Claude Haiku 4.5 screen of that variant was model-dependent:
  4/8 once-per-session vs 8/8 every-prompt.
- **What this does not show:** behaviour in real long sessions, tool-heavy
  work or real 400k-token contexts; this reminder on Claude Haiku 4.5; or that
  answers become more accurate. If you rely on a model these tests did not
  cover, choose `general`.

**Installation.** A clean temporary Claude Code 2.1.293 profile on Linux/WSL
installed 0.8.0 from a local-path marketplace; the installed files matched the
committed package byte for byte. The default session received one reminder,
from `SessionStart`; a session whose prompt matched a fidelity trigger received
two; the same prompt with `# fidelity-ok` received one; and the release-archive
session received one. See the
[installation smoke](validation/claude-code-smoke-0.8.0.json). The isolated
bundle smoke on the same commit passed every required Code check and is
recorded as the `code-wsl` live pass in the
[compatibility record](validation/compatibility-candidate.json); the native
Linux, macOS and Windows installation rows come from CI.

## Update

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a new Claude Code session, then confirm package `0.8.0` and mode
`session` in `/llm-accuracy:accuracy-doctor`. See the [install guide](INSTALL.md).
