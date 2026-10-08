# Contributing

Open a draft pull request for a scoped change, or use the feedback issue form
for a sanitized, reproducible problem.

Runtime and packaging changes must follow [the compatibility contract](docs/COMPATIBILITY.md).
Run `python3 scripts/check_compatibility.py`, keep all OS/host cells explicit,
and record current installed-host QA before a release (`--release`). Tests on
Windows with Git Bash do not establish support without it; Chat is skills-only.

Main is the marketplace delivery branch. Protected changes require actual native
installation and direct installed-hook execution on Linux/macOS/Windows with
and without Bash, plus at least one current-source local live Code pass. Desktop
Chat/Cowork are experimental stateless skills; their untested rows remain visible.
Run `python3 scripts/check_marketplace_publication.py --base-ref BASE_SHA` using
the actual PR base commit. Main/tag builds use `--release`. Keep native installed
QA and publication in the required aggregate; independently review checker,
workflow and receipt changes. Offline installed rows cannot be used as live
passes. Hosted jobs run without login files, secrets or model calls; local live
QA uses isolated profiles. See [free QA setup](docs/INSTALLED_QA.md#hosted-code-qa).

Never include credentials, customer data, raw prompts, provider responses, logs,
or private transcripts. Replace names, IDs, amounts, dates, and examples with
synthetic equivalents.

Before proposing a release-affecting change, run:

```bash
python3 -m pytest -q
uv run --no-project --python 3.9 --with pytest python -m pytest -q
find plugins -path '*/hooks/*.py' -print0 | xargs -0 -r python3 -m py_compile
```

The second line runs the suite on Python 3.9, the oldest version the gates test
(they run 3.9 to 3.14). A newer local Python does not catch a 3.10+ API: for
example, `TemporaryDirectory(ignore_cleanup_errors=True)` passed on 3.11 and
failed only in the 3.9 gate.

Before a release, run the clean installation smoke on the committed tree:

```bash
python3 scripts/claude_install_smoke.py --receipt docs/validation/claude-code-smoke-<version>.json
```

It installs the plugin from this checkout through a local-path marketplace into
an auth-only temporary profile, checks the installed files byte for byte, then
runs four short Sonnet sessions: installed, a fidelity-trigger prompt, the same
prompt with the `# fidelity-ok` bypass, and the release archive. The receipt holds only counts, booleans and
hashes. It configures the running Python executable only inside the temporary
profiles, including explicit settings for the archive session. Configuration
failure blocks the smoke. `--skip-live` checks the installation without model calls.

Keep the plugins generic. The plugin may improve evidence hygiene, but it does
not guarantee correct or current answers.

## Releasing

`main` is the delivery branch for marketplace installs: a version is live for
them once its pull request merges. Claude Desktop and Cowork users install the
LLM Accuracy ZIP from the latest release instead (README, `docs/INSTALL.md`),
so a version reaches them only when its release carries that ZIP. After a
version-bump pull request merges:

1. Write the notes in `docs/release-<version>.md` (LLM Accuracy) or
   `docs/release-<plugin>-<version>.md` (Evidence Memory, Session Ledger).
   Start them with a line that dates the version, for example
   `_Published 8 Oct 2026 for the version that reached main on 8 Oct 2026 (17bae38)._`
2. Tag the merge commit, not a later `main`:

   ```bash
   gh release create v<version> --target <merge-sha> --title "LLM Accuracy <version>" \
     --notes-file docs/release-<version>.md --latest
   ```

   Evidence Memory and Session Ledger use the tag prefixes `evidence-memory-v`
   and `session-ledger-v`, their own titles, and `--latest=false`, so the
   newest LLM Accuracy release stays marked Latest.
3. Attach the LLM Accuracy ZIP and its checksum, built from a clean checkout of
   the tagged commit. Evidence Memory and Session Ledger releases carry no
   assets.

   ```bash
   git switch --detach v<version>
   python3 scripts/build_plugin_zip.py --output dist/llm-accuracy-<version>.zip
   (cd dist && sha256sum llm-accuracy-<version>.zip > SHA256SUMS.txt)
   gh release upload v<version> dist/llm-accuracy-<version>.zip dist/SHA256SUMS.txt
   ```

4. Check each tag's commit directly; `gh release list` shows tags, not commits.
   After `git fetch --tags origin`, `git rev-parse v<version>^{commit}` must
   print the merge commit. Then `gh release view v<version>` must list both
   assets, and `gh release list` must show LLM Accuracy as Latest.

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
markers, receipt persistence, and session continuity remain excluded from the
generic plugin. The generic evidence-receipt schema and stateless structural
validator are intentionally shared with Deterministic Data; neither establishes
domain truth.

Deterministic Data contributions must remain synthetic and provider-neutral.
Catalogue fixtures contain definitions and fake source-binding identifiers,
never provider payloads, query results, credentials, customer records or real
business values.

Cross-repository drift is not currently enforced in CI because this repository's
GitHub Actions token cannot read the separate private upstream repository.
Until a scoped cross-repository credential or common generated source is
available, include the compared upstream commit and deliberate divergences in
the pull request.

Session Ledger source must not include any captured ledger content. Use only
synthetic compact summaries and synthetic session records in tests, and preserve
its local-only, 30-day, same-session boundary.

Evidence Memory is independently packaged. Its source and fixtures must not
contain captured tool results or real corrections; enabling the plugin in Claude
settings starts future sessions automatically. Test the fresh cutoff, session
stop/deletion, and expiry with synthetic data.
