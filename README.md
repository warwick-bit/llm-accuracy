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
- no persisted prompts, tool output, or session ledgers. No session ledger is
  included in this distribution.

Provider-specific verification integrations are intentionally out of scope.
See [PREVIEW.md](PREVIEW.md) for participation rules and [SECURITY.md](SECURITY.md)
for responsible disclosure.

## Install for preview participants

Add this private Git repository as a marketplace in Claude Code, then install
`llm-accuracy`. Installation access is limited to invited GitHub collaborators.
The first preview release must be validated in a clean local Claude Code runtime
before relying on it for consequential work.

## Day-to-day use

After installation and activation, use Claude Code normally. There is no command
to run or system prompt to paste for matching prompts. The self-audit workflow
is also available when you ask the assistant to check one of its earlier
answers.

In Claude Code, advisory hooks add targeted reminders for matching open-ended
analysis or source-conflict prompts and after context compaction. They do not
run on every prompt, block work, fetch evidence, or verify an answer for you.

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
python3 -m py_compile $(find plugins/llm-accuracy/hooks -name '*.py' -print)
```
