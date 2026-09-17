# LLM Accuracy

Evidence-first accuracy hygiene for Claude Cowork and Claude Code.

LLM Accuracy helps an LLM distinguish direct evidence from inference, keep
claims inside their source and scope, recheck stale details, calibrate
confidence, and audit its own prior answers. It does not guarantee truth,
completeness, timeliness, or domain correctness.

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
> **Evidence boundary:** 62% of the 80 surveyed trial users activated under the
> survey's definition and time window.
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
  "rows": ["25 fictional records"],
  "has_more": true,
  "next_cursor": "page-2"
}
```

**Typical failure**

> There are 25 records in total.

**With LLM Accuracy**

> This is a partial result: 25 rows were seen on the first page and another page
> is declared. I need to continue from `page-2`, or report only the 25 rows
> observed so far. The complete total is withheld.

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
updates, removal, and troubleshooting. The first public release must be
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

Use `/llm-accuracy:claim-fidelity` to check whether a conclusion is supported
by its source, population, definition, window, freshness and completeness. The
receipt validator checks structure only and stores no receipt content.

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
