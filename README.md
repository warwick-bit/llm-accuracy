# LLM Accuracy

Evidence-first accuracy hygiene for Claude Code.

LLM Accuracy helps an LLM distinguish direct evidence from inference, recheck
stale details, calibrate confidence, and audit its own prior answers. It does
not guarantee truth, completeness, timeliness, or domain correctness.

## Private preview

This repository is an invite-only private preview. It is not open source and
has no public licence. Do not submit credentials, customer data, provider
payloads, or raw conversation transcripts in issues, pull requests, or test
fixtures.

The preview includes only a generic core:

- evidence and provenance discipline;
- stale-memory rechecks and calibrated uncertainty;
- self-audit of a prior assistant answer; and
- no persisted prompts or tool output. **LLM Accuracy itself remains stateless.**

The marketplace also offers a separate, optional **Session Ledger** plugin for
Claude Code terminal or IDE use only. It starts a bounded local ledger with every
session, appends a rolling user/assistant session record as work progresses, and
flushes that ledger before compaction. It then restores it when the same
compacted session continues, so accuracy-relevant decisions, sources, unknowns,
and re-check warnings survive. It is not shared with a new Claude session, never
writes to the project or Git, and expires after 30 days. Install it only if you
accept that the retained record and compact summary can contain sensitive local
content.

Provider-specific verification integrations are intentionally out of scope.
See [PREVIEW.md](PREVIEW.md) for participation rules and [SECURITY.md](SECURITY.md)
for responsible disclosure.

## Install for preview participants

Choose the installation path that matches your Claude environment. Installation
access to this private repository is limited to invited GitHub collaborators.

- **Claude Code in a terminal or IDE:** the full preview, including advisory
  hooks. Follow the [terminal guide](docs/INSTALL.md#claude-code-terminal-or-ide-full-preview).
- **Claude Desktop Chat:** upload the release ZIP for skills-only use. The
  automatic advisory hooks do not run in chat.
- **Claude Cowork:** upload the same ZIP for the full skills-and-hooks preview.
- **Claude chat on the web:** add the private GitHub marketplace through
  **Customize → Plugins** for skills-only use; Chat does not run the advisory
  hooks. Team and Enterprise owners can alternatively distribute it through an
  organization marketplace.
- **Claude Code on the web:** not yet supported for this preview; it needs a
  project-scoped cloud smoke test against a private marketplace.

See the complete [installation guide](docs/INSTALL.md), including activation,
updates, removal, and troubleshooting. The first preview release must be
validated in a clean supported runtime before relying on it for consequential
work.

## Day-to-day use

After installation and activation, use Claude Code normally. There is no command
to run or system prompt to paste for matching prompts. The self-audit workflow
is also available when you ask the assistant to check one of its earlier
answers.

In Claude Code, advisory hooks add targeted reminders for matching open-ended
analysis or source-conflict prompts and after context compaction. They do not
run on every prompt, block work, fetch evidence, or verify an answer for you.

When separately installed, Session Ledger starts automatically with each Claude
Code session, captures a bounded rolling session record as that session
progresses, flushes it before compaction, and restores it when the same compacted
session continues. There is no everyday command to run. `/session-ledger:begin-plan`
is optional when you deliberately start unrelated work within the same long
session, and `/session-ledger:clear` removes the plugin's local ledger state.

## Why freshness matters

An LLM can give too much weight to recalled training material, earlier messages,
or a stale summary after a long session even when the underlying fact has
changed. That can degrade accuracy while the answer still sounds confident.
LLM Accuracy asks the model to recheck current evidence, distinguish evidence
from inference, and mark an unavailable source as unknown rather than fill the
gap from memory.

## Development

Run the lightweight distribution checks:

```bash
python3 -m pytest -q
python3 -m py_compile $(find plugins -path '*/hooks/*.py' -print)
```
