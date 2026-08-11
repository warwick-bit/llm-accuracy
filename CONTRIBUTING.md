# Contributing

Open a draft pull request for a scoped change, or use the feedback issue form
for a sanitized, reproducible problem.

Never include credentials, customer data, raw prompts, provider responses, logs,
or private transcripts. Replace names, IDs, amounts, dates, and examples with
synthetic equivalents.

Before proposing a release-affecting change, run:

```bash
python3 -m pytest -q
find plugins -path '*/hooks/*.py' -print0 | xargs -0 -r python3 -m py_compile
```

Keep the plugins generic. The plugin may improve evidence hygiene, but it does
not guarantee correct or current answers.

## Feedback

Report a sanitized reproduction: the prompt shape, expected evidence boundary,
actual behaviour, runtime, and plugin version. Replace all real names, IDs,
amounts, dates, and provider responses with synthetic equivalents.

Never submit:

- credentials, tokens, or secrets;
- customer, employee, or prospect data;
- raw provider responses, logs, or locally persisted session-ledger contents; or
- content you are not authorised to share.

The plugins are advisory. Users remain responsible for reviewing outputs before
using them in decisions or external communication.

Maintainers may convert a reviewed, sanitized failure report into a synthetic
regression fixture. No real-world report is copied verbatim into the test set.

## Downstream lineage

The generic accuracy plugin is a sanitized downstream distribution of the
maintainer's internal accuracy toolkit. Shared hook or evidence-doctrine changes
must be compared in both directions and either backported or recorded as an
intentional downstream divergence. Domain integrations, provider-specific
markers, deterministic receipt tooling, and session continuity remain excluded
from the generic plugin.

Cross-repository drift is not currently enforced in CI because this repository's
GitHub Actions token cannot read the separate private upstream repository.
Until a scoped cross-repository credential or common generated source is
available, include the compared upstream commit and deliberate divergences in
the pull request.

Session Ledger source must not include any captured ledger content. Use only
synthetic compact summaries and synthetic session records in tests, and preserve
its local-only, 30-day, same-session boundary.
