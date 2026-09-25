# LLM Accuracy

Make everyday Claude answers more predictable, consistent and trustworthy.

LLMs are built to give useful answers quickly. When a question is ambiguous,
they often fill the gaps by choosing a definition, time period, comparison or
source for you. Those choices can change between sessions, so the same simple
question can produce different answers.

LLM Accuracy asks Claude to slow down at those decision points: clarify what
you mean, keep claims within the evidence, preserve conflicts between sources
and say what is still unknown. Deterministic Data adds your team's reviewed
definitions and declared source routes when repeat questions need a consistent
method.

## Start here

Use **LLM Accuracy** for everyday questions where a plausible answer could
still be the wrong answer. Most people should install only this plugin first.

The basic loop is:

1. You ask Claude a normal question.
2. A Claude Code or Cowork hook adds a short general evidence reminder on each
   non-empty prompt, including technical requests and brief follow-ups.
3. Claude is asked to clarify material ambiguity or keep the answer aligned
   with the source's population, definition, time window, freshness and
   completeness.
4. When you want a structured second pass, run
   `/llm-accuracy:claim-fidelity` or ask Claude to audit its previous answer.

The hooks are advisory. They help Claude reason more carefully, but they do not
independently verify the source or guarantee the final answer. **Deterministic
Data** is the separate plugin for applying your own reviewed definitions and
declared source routes to repeat data questions.

The general reminder asks Claude to verify measurements and coverage, test
competing causes, and revisit dependent conclusions when correcting a diagnosis.
Additional business-ambiguity and source-conflict reminders remain targeted.
Use `/llm-accuracy:claim-fidelity` for an explicit check. See
[reminder modes](plugins/llm-accuracy/README.md#reminder-modes) to restore the
previous targeted-only behaviour or mute the fidelity reminder.
Users can also [add their own trigger phrases](plugins/llm-accuracy/README.md#custom-trigger-phrases)
for fidelity, analysis or source-conflict checks without editing the plugin cache.

For technical work, `/llm-accuracy:verify-technical` guides reproduction,
competing-cause checks and verification after a fix. Use
`/llm-accuracy:accuracy-doctor` to inspect activation and configuration when
machines behave differently. Substantive technical diagnoses request a compact
Checked / Gap / Next footer. These are advisory workflows, not accuracy guarantees.

### Questions that look simple but are not

- **What is our revenue?** It could mean MRR, ARR, recognised revenue, invoices
  raised or cash received, for several possible time periods.
- **Who are our best customers?** "Best" could mean highest revenue, margin,
  retention, product use or growth potential.
- **Which marketing channel performs best?** The winner changes when success
  means leads, conversion, revenue, retention or payback.
- **Did the new onboarding flow improve activation?** The answer depends on the
  activation event, cohort, measurement window and comparison group.
- **Sales increased after our pricing change. Does that prove the pricing
  change caused the increase?** Timing alone does not rule out seasonality,
  mix changes, campaigns or other causes.

### Pick the plugin you need

- **LLM Accuracy** — start here for general claim fidelity, evidence hygiene,
  uncertainty and self-audit. It does not persist prompts or tool output; see
  [Licence and boundary](#licence-and-boundary).
- **Deterministic Data** — add this only when you want to maintain your own
  definitions and route data questions to declared read-only sources. Its
  bundled catalogue is fictional and fully editable in your own source copy.
- **Session Ledger** — add this only in Claude Code when accuracy-critical
  context must survive compaction within the same long session. It stores a
  bounded local record, so review its data boundary before installing it.
- **Evidence Memory** — independent experimental Claude Code plugin for exact
  earlier tool results and revisioned corrections in the current session. It
  stores potentially sensitive tool data locally only after a separate
  per-session enable step; Session Ledger is not required.

### Try LLM Accuracy in five minutes

Before installing it, ask your current Claude:

> What is our revenue?

Note whether it asks what revenue means or silently chooses a metric, period
and source. Then install LLM Accuracy.

**A typical answer before installation might be:**

> Revenue was $120k last month.

That answer sounds useful, but it silently chose the revenue definition,
period, currency and source.

You need a current, signed-in Claude Code installation with the `plugin`
subcommand. If `/plugin` is unavailable, update Claude Code first; the
[installation guide](docs/INSTALL.md#claude-code-terminal-or-ide--full-plugin)
covers the full prerequisites and troubleshooting path.

Install it in Claude Code:

```bash
claude plugin marketplace add warwick-bit/llm-accuracy --scope user
claude plugin install llm-accuracy@llm-accuracy --scope user
```

Run `/reload-plugins`, then ask the same question again:

> What is our revenue?

The reminder should make Claude ask a short, concrete clarification before it
answers, such as which revenue basis you mean, the period or as-at date,
currency and source. The exact wording can vary.

**A safer answer after installation might be:**

> Which revenue do you mean: MRR, ARR, recognised revenue, invoiced revenue or
> cash received? Which period, currency and source should I use?

Then try a question that already supplies those choices:

> What is our recognised revenue from the general ledger for September 2026?

The ambiguity reminder stays silent because the definition, source and period
are explicit. Claude may still need access to the ledger or ask about currency
under other instructions.

This test shows an advisory clarification, not independent verification. To
make the answer repeatable across a team, add **Deterministic Data**, define
each revenue measure in its editable catalogue and bind each definition to its
approved read-only source. Then invoke `/deterministic-data:data-routing` with
the question and your catalogue path. Installing its untouched fictional
catalogue cannot answer questions about your company.

The [raw-free Claude Code smoke receipt](docs/validation/claude-code-ambiguity-smoke-2026-09-17.json)
records the paired prompts, negative controls and limits of the test without
publishing the model responses.

### What the test showed

In a small synthetic Claude Code test using the same Claude model and a fresh
session for every run:

- Without the plugin, Claude asked for both the revenue definition and time
  period in **0 of 3** runs of `What is our revenue?`.
- With LLM Accuracy, Claude asked for both in **3 of 3** runs.
- Both setups correctly rejected the pricing-causality claim in the one run
  tested for each setup (`n=1` per setup). No improvement was observed on that
  prompt.
- The plugin's programmatic ambiguity check stayed silent for **3 of 3**
  precise questions that already named the metric, period and source.

This measures whether Claude asked for the missing choices before answering.
It does not measure a percentage improvement in overall factual accuracy. The
sample is small and synthetic, so treat it as an exploratory product smoke,
not a statistically powered benchmark. See the
[raw-free test receipt](docs/validation/claude-code-ambiguity-smoke-2026-09-17.json)
for the exact setup and limits.

### What broader prototype testing taught us

The public-plugin test above showed that LLM Accuracy made Claude ask for the
missing revenue definition and period. Separately, we tested early prototypes
of stricter fact checking. These prototypes are not part of the plugins you can
install today.

- **A narrow fact checker rejected 102 of 102 deliberately altered answers.**
  It also refused expired information and did not reuse an old answer after a
  failed refresh. It checked a fixed set of rules; it did not prove that the
  original data source was correct.
- **Known facts remained available when other information was missing.** In
  four hand-written examples covering revenue, customer support and product
  usage, the prototype kept supported facts and withheld calculations that
  needed missing data. Tools were disabled, and normal explanatory text could
  still add unsupported claims.

These prototype tests support the direction of stricter checking, but they do
not show that the current plugins improve overall accuracy. **LLM Accuracy**
helps Claude clarify ambiguous questions. **Deterministic Data** gives teams
consistent definitions and approved source routes. Neither guarantees that
every sentence Claude writes is true.

The [detailed test record](docs/validation/broader-fidelity-evidence-2026-09.json)
lists the numbers and limitations. It includes totals only, not the original
questions or answers, so other people cannot rerun the same tests from this
repository alone.

For Cowork, download the latest
[`llm-accuracy-<version>.zip`](https://github.com/warwick-bit/llm-accuracy/releases/latest),
upload it through **Customize → Plugins**, and use the same test prompts. See
the [installation guide](docs/INSTALL.md) for updates, removal, other Claude
products and the optional plugins.

## Licence and boundary

This repository is public and MIT-licensed; see [LICENSE](LICENSE).
Do not submit credentials, customer data, provider payloads, or raw
conversation transcripts in issues, pull requests, or test fixtures.

The plugins cover only a generic core:

- evidence and provenance discipline;
- claim/source/scope/freshness/completeness alignment;
- a stateless evidence-receipt schema and structural validator;
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

For source-adapter integration, see [tool failures, refreshes and evidence receipts](docs/tool-failure-contract.md), including synthetic regression cases and the limits of structural validation. For output-boundary guidance, see [evidence boundaries and answer publication](docs/answer-boundaries.md), including unsupported derivations and runtime limitations.

Provider-specific verification integrations are intentionally out of scope.
See [CONTRIBUTING.md](CONTRIBUTING.md) for feedback rules and [SECURITY.md](SECURITY.md)
for responsible disclosure.

The marketplace also includes **Deterministic Data**, a separate editable
template for user-owned catalogues, definition routing and source bindings. Its
bundled catalogue is fictional. Users customise a fork or source copy and then
install it in Claude Code or upload a rebuilt ZIP to Cowork; installed
marketplace files are not the editing surface.

## See it in practice

These examples use fictional data. They show the failure being corrected, the
safer answer, and which part of the plugin changes the behaviour.

Examples 1 and 2 use **LLM Accuracy**. Example 3 uses **Deterministic Data**,
which is offered through the same repository marketplace but installed and
enabled separately. Neither plugin depends on the other.

### 1. A narrow source becomes an over-broad claim

**Question**

> A survey of 80 trial users says 62% activated. Can we report that 62% of all
> customers activated?

**Typical failure**

> Yes. Customer activation is 62%.

The answer silently changes the population from surveyed trial users to all
customers.

**With `/llm-accuracy:claim-fidelity`**

> **Status:** withheld
>
> **Evidence boundary:** the survey reports 62% for a group described as 80
> trial users.
>
> **Unknown:** raw activated count, survey method, activation definition and
> time window.
>
> **Overreach:** this does not establish activation for all customers.
>
> **Next check:** measure the full customer population using the same activation
> definition and window.

**How it changes the answer:** the workflow compares the claim and source across
population, measure, time window, freshness and completeness. This is a
model-guided evidence check; it does not independently verify that the survey
itself is correct.

### 2. One page of data is treated as the complete set

**Tool response envelope**

```json
{
  "rows": ["fictional records omitted from this example"],
  "returned_count": 25,
  "has_more": true,
  "next_cursor": "page-2"
}
```

**Typical failure**

> There are 25 records in total.

**With LLM Accuracy**

> This is a partial result: the response declares 25 returned rows on the first
> page and another page is available. I need to continue from `page-2`, or
> report only this page. The complete total is withheld.

**How it changes the answer:** a programmatic post-tool hook detects explicit
partial-result markers such as `has_more`, a next-page cursor, row-cap warnings
or host truncation. It adds a bounded reminder without retaining or echoing the
tool payload. The model can still cite details from the original response, as
it does above; those details are not re-emitted by the hook. The hook cannot
prove completeness when the source declares no partial-result marker.

### 3. An undefined metric gets a confident number

**Question**

> What were active service units last month?

**Typical failure**

> Active service units were 1,240 last month.

That answer can invent the definition, calendar window, source and value.

Deterministic Data's catalogue and validators provide deterministic boundaries
around a model-guided routing workflow.

**With `/deterministic-data:data-routing` and the bundled example catalogue**

The following is a model-produced response that follows the routing workflow.
The validators can check its catalogue and receipt structures, but do not
programmatically select the definition or execute the route.

> **Matched definition:** `active-service-units`
>
> **Route status:** source unavailable
>
> **Window:** `latest_complete_month`; concrete dates unresolved
>
> **Evidence receipt:** emitted inline and structurally validated
>
> **Canonical value:** withheld because the example has no working provider
> adapter and defines no calendar, timezone or close rule.

**How it changes the answer:** the workflow instructs the model to match exact
aliases to a reviewed definition, stop on candidate, ambiguous and missing
definitions, and use only the declared read-only source binding for an approved
definition. Failed, partial or unavailable reads stay unresolved instead of
being replaced with a remembered number. The programmatic
[catalogue validator](plugins/deterministic-data/scripts/validate_catalogue.py)
rejects invalid structure and duplicate normalized aliases. The
[receipt validator](plugins/deterministic-data/scripts/validate_evidence_receipt.py)
rejects malformed receipts and, when supplied the expected epoch,
prompt-epoch mismatches. These validators do not execute the route or prove the
source value is true.

To make the third route useful, copy the fictional catalogue, add your own
reviewed definition and calendar rules, bind it to a read-only source, validate
the catalogue, and test it with synthetic fixtures before using real data.

**After that setup, a successful fictional route could return**

> **Matched definition:** `active-service-units`
>
> **Route status:** declared read-only source executed
>
> **Window:** resolved using the catalogue's calendar, timezone and close rule
>
> **Evidence receipt:** emitted inline and structurally validated
>
> **Canonical value:** 1,240 fictional units, supported by the completed source
> read for the resolved window.

The value becomes eligible to return because the definition, window, binding
and completed read align. Human review still decides whether those inputs and
the underlying source are trustworthy.

### What is enforced in code?

- **Programmatic:** explicit partial-result detection, catalogue schema and
  alias-uniqueness validation, and receipt-shape and prompt-binding validation.
- **Model-guided:** claim/source alignment, exact-alias routing, stop/withhold
  decisions, uncertainty language, self-audit and the decision to follow an
  advisory hook.
- **Outside the plugin:** source truth, business-definition approval, connector
  correctness and human review of consequential answers.

## Install

Choose the installation path that matches your Claude environment.

- **Claude Code in a terminal or IDE:** the full plugin, including advisory
  hooks. Follow the [terminal guide](docs/INSTALL.md#claude-code-terminal-or-ide--full-plugin).
- **Claude Desktop Chat:** upload the release ZIP for skills-only use. The
  automatic advisory hooks do not run in chat.
- **Claude Cowork:** upload the same ZIP for the full skills-and-hooks
  experience.
- **Claude chat on the web:** add the GitHub marketplace through
  **Customize → Plugins** for skills-only use; Chat does not run the advisory
  hooks. Team and Enterprise owners can alternatively distribute it through an
  organization marketplace.
- **Claude Code on the web:** not yet supported; it still needs a
  project-scoped cloud smoke test.

See the complete [installation guide](docs/INSTALL.md), including activation,
updates, removal, and troubleshooting. Validate each release in a clean
supported runtime before relying on it for consequential work.

## Day-to-day use

After installation and activation, use Claude Code normally. There is no command
to run or system prompt to paste for matching prompts. The self-audit workflow
is also available when you ask the assistant to check one of its earlier
answers.

In Claude Code, the general fidelity reminder runs on each non-empty prompt.
Additional reminders target ambiguous business questions, open-ended analysis,
evidence-boundary claims, source conflicts and context compaction. They do not
block work, fetch evidence, or verify an answer for you. General mode adds context
even to greetings and creative tasks; it asks Claude to keep those tasks brief.
Delivery coverage is not proof that the model follows the reminder or answers
more accurately.

Use `/llm-accuracy:claim-fidelity` to check whether a conclusion is supported
by its source, population, definition, window, freshness and completeness. The
receipt validator checks structure only and stores no receipt content.

When separately installed, Session Ledger starts automatically with each Claude
Code session, captures a bounded rolling session record as that session
progresses, flushes it before compaction, and restores it when the same compacted
session continues. There is no everyday command to run. `/session-ledger:begin-plan`
is optional when you deliberately start unrelated work within the same long
session, and `/session-ledger:clear` removes the plugin's local ledger state.
Evidence Memory can be installed separately; `/evidence-memory:memory` explains
its explicit capture, lookup, correction and deletion commands.

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
