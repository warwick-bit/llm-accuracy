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

## Changing a detection rule

A rule that decides whether output is partial has two failure directions, and a
fixture suite written by the rule's own author can hide both. Before widening or
narrowing one, measure it against real tool results:

```bash
python3 scripts/measure_tool_result_corpus.py --exclude-session <your-session-id>
```

To show what a change COST, score the old and new hook over one snapshot. A count
compared against a count taken earlier is not a control: the corpus grows while
you work, so an unchanged hook can appear to gain detections.

```bash
git show <old-sha>:plugins/llm-accuracy/hooks/partial-result-sentinel.py \
    > /tmp/old-sentinel.py
python3 scripts/measure_tool_result_corpus.py --compare-hook /tmp/old-sentinel.py
```

The corpus is your own local transcripts. The script itself never writes corpus
content or any corpus-supplied value: every report it prints is one of its own
labels, its own signal codes, its own scope word, or an aggregate count. Errors are the exception, and they are about the
command line rather than the corpus — a bad `--hook` path is named so you can fix
it. That guarantee covers the script, not the hook you
point it at — a hook is arbitrary imported code in the same process, and no
in-process check can contain one. Measure a hook you would run anyway, and do not
paste corpus contents into an issue, a pull request, or a commit message.

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
