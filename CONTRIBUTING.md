# Contributing to the Private Preview

This is an invite-only preview. Open a draft pull request for a scoped change,
or use the private-preview issue form for a sanitized, reproducible problem.

Never include credentials, customer data, raw prompts, provider responses, logs,
or private transcripts. Replace names, IDs, amounts, dates, and examples with
synthetic equivalents.

Before proposing a release-affecting change, run:

```bash
python3 -m pytest -q
find plugins/llm-accuracy/hooks -name '*.py' -print0 | xargs -0 -r python3 -m py_compile
```

Keep the preview generic. The plugin may improve evidence hygiene, but it does
not guarantee correct or current answers.
