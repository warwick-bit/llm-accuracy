# Install LLM Accuracy

LLM Accuracy has different installation and capability paths across Claude
products. Use the path below that matches where you work.

## Validation status

Platform capability and this release's runtime evidence are separate:

- **Claude Code terminal or IDE:** exact shipped hook commands, the automated
  distribution suite and a clean isolated-profile marketplace installation
  (marketplace add plus both plugin installs) were re-tested on 16 Sep 2026.
  Authenticated, non-persistent local sessions also exercised the claim-fidelity
  hook and skill, Deterministic Data routing, receipt validation and a negative
  hook control on 16 Sep 2026. A paired candidate smoke on 17 Sep 2026 tested
  the five ambiguity examples, three negative controls and repeated revenue
  prompts; see the
  [raw-free receipt](validation/claude-code-ambiguity-smoke-2026-09-17.json).
- **Claude Desktop Chat:** not runtime-smoke-tested for this release. The
  skills-only description follows Anthropic's current plugin documentation.
- **Claude Cowork:** an initial Desktop 2.110.0 smoke on 16 Sep 2026 verified
  plugin activation, the claim-fidelity hook and skill, Deterministic Data
  routing, receipt validation and a negative control. A follow-up Cowork smoke
  of the final rebuilt ZIP used no `Write` tool, validated its receipt through
  stdin with a route-bound prompt epoch, preserved the unresolved
  `latest_complete_month` token and withheld the canonical value. See the
  [raw-free smoke receipt](validation/cowork-deterministic-data-smoke-2026-09-16.json).
- **Claude chat on the web:** not runtime-smoke-tested for this release. The
  skills-only description follows Anthropic's current plugin documentation.
- **Claude Code on the web:** untested and unsupported for this release.

Recheck the linked platform documentation and record a new tested-on date when
claiming support after a release or host-runtime change.

## Claude Code terminal or IDE — full plugin

This is the recommended path. It includes the self-audit skill
and the targeted advisory hooks.

### Before you start

- Use a current Claude Code installation. If `/plugin` is unavailable, update
  Claude Code first.
- Have Python 3.9 or later available as `python3` or `python` and a
  POSIX-compatible hook shell. The repository's exact command-launcher tests currently run on POSIX only.
- Install only if you trust the plugin source. It runs local advisory hook
  commands in Claude Code.

### Install

Run these commands in your terminal:

```bash
claude plugin marketplace add warwick-bit/llm-accuracy --scope user
claude plugin install llm-accuracy@llm-accuracy --scope user
```

Start or return to Claude Code, then run:

```text
/reload-plugins
```

To confirm the plugin is active, open `/plugin` and check **Installed**. Open
`/hooks` to see the plugin's advisory hook entries.

### Use it

Use Claude Code normally. LLM Accuracy has no command to run or system prompt to
paste for matching prompts. Its self-audit skill is available when you ask
Claude to check one of its own earlier answers.

The hooks add reminders only for matching ambiguous business questions,
open-ended analysis, evidence-boundary claims or source conflicts, and after
context compaction. They do not run on every prompt, fetch evidence, block work,
or verify facts automatically. The automatic patterns are deliberately bounded;
use `/llm-accuracy:claim-fidelity` when you want an explicit check.

## Deterministic Data — editable template

Deterministic Data is a separate plugin for teams that want their own metric or
data catalogue. Installers can change every definition, alias and source-binding
ID in their own fork or source copy. Do not edit the installed marketplace
cache because an update can replace those files.

Start by forking or copying the repository, copy the fictional example
catalogue, fill it with your metadata, and validate it:

```bash
python3 plugins/deterministic-data/scripts/validate_catalogue.py \
  plugins/deterministic-data/catalogues/your-catalogue.json
python3 scripts/build_plugin_zip.py --plugin deterministic-data
```

After installing your customised copy, invoke
`/deterministic-data:data-routing` with the question and catalogue path. The
bundled fictional catalogue cannot answer questions about your company, and
the routing skill is not a replacement for configuring definitions and
read-only source bindings.

Keep credentials, provider payloads, query results, customer records and raw
prompt content out of catalogue files. Add separately reviewed read-only
adapters for real sources. In Claude Code, add your customised repository as a
marketplace and install `deterministic-data` from it. In Cowork, upload the ZIP
built from your customised source. A Cowork smoke of the rebuilt ZIP and bundled
fictional catalogue on 16 Sep 2026 stayed file-free, matched the receipt epoch
to the route, kept unresolved window bounds unresolved and withheld the
canonical value. Custom adapters and catalogues need their own runtime test. The
linked raw-free smoke receipt records the candidate commit, exported-session
identifier, transcript hash and pass checks.

## Session Ledger — Claude Code terminal or IDE only

Session Ledger is a separate, optional plugin for accuracy across one long
Claude Code session. It starts a bounded local ledger at SessionStart, appends a
rolling user/assistant session record as the session progresses, and flushes it
to local plugin storage before compaction. It restores the record when that same
compacted session continues. Install it only if you accept that the retained
record and Claude's compact summary may contain sensitive local content. It is
unsupported in Claude Desktop Chat, Cowork, Claude chat on the web, and Claude
Code on the web.

Session Ledger requires Python 3.9 or later (CI-tested 3.9-3.13) on the machine
running Claude Code. Check it with `python3 --version`, or `python --version`
when `python3` is unavailable (for example, a Windows python.org installation).
Both plugins select `python3` when present and otherwise use `python`; the
selected command must run Python 3.9 or later. Windows hooks still require a
POSIX-compatible shell such as Git Bash. No `python3.exe` copy or alias is needed.

Install it after adding the marketplace:

```bash
claude plugin install session-ledger@llm-accuracy --scope user
claude plugin enable session-ledger@llm-accuracy --scope user
```

Then run `/reload-plugins` in an active Claude Code session, or start a new
one. After that, use Claude normally: the ledger starts automatically with the
session, captures a bounded rolling user/assistant session record on user-prompt
and turn-complete hooks, flushes it before context compaction, and restores it
only when that same compacted session continues. It never carries into a
completely new Claude session.

### Local-data boundary

- **Stored:** the bounded compact summary, rolling user/assistant session
  record, hashed session/workspace identifiers, schema version, and expiry
  metadata. The summary and record can contain sensitive local material,
  including conversation text, paths, names, and credentials supplied as normal
  text.
- **Not retained:** raw JSONL transcript structure, the hook's separate
  workspace-path or plan-name fields, tool input/output, provider payloads,
  telemetry, or any server copy. The rolling user/assistant record is
  deliberately not redacted within its fixed byte limit.
- **Retention:** records are never read or injected after 30 days and are
  purged on the next Session Ledger hook. Claude's default final-scope uninstall
  also deletes plugin data; `--keep-data` deliberately preserves it.
- **Clear:** run `/session-ledger:clear` to delete all local Session Ledger
  state immediately.

Restored content is explicitly marked as untrusted historical reference. Claude
must not treat it as instructions and must reverify time-sensitive facts before
reuse.

If ledger data is missing, malformed, expired, unsupported, or unavailable, the
plugin fails open: Claude Code continues normally with no carried-over context.

### Optional plan boundary

Every session has an automatic default ledger; a plan is not required. If you
start unrelated work within a long session, run `/session-ledger:begin-plan`.
It starts a clean ledger section for the current session without storing a plan
name or carrying data to another session.

### Update or remove

To update to the latest released versions:

```bash
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy --scope user
claude plugin update deterministic-data@llm-accuracy --scope user
claude plugin update session-ledger@llm-accuracy --scope user
```

Run the optional plugin updates only for plugins you installed. Then run
`/reload-plugins` in an active Claude Code session.

Marketplace auto-update is off by default for third-party marketplaces like
this one. To opt in, run `/plugin`, open **Marketplaces**, select
`llm-accuracy`, and choose **Enable auto-update**. Claude Code then refreshes
the marketplace and updates installed plugins in the background after a
session starts, and prompts you to run `/reload-plugins` when versions
changed. To remove the
plugins and local Session Ledger data:

```bash
claude plugin uninstall session-ledger@llm-accuracy --scope user
claude plugin uninstall deterministic-data@llm-accuracy --scope user
claude plugin uninstall llm-accuracy@llm-accuracy --scope user
claude plugin marketplace remove llm-accuracy
```

The default final-scope uninstall removes Session Ledger plugin data. Do not use
`--keep-data` unless you intentionally want to retain its compact summaries and
local session record.

If installation fails, first confirm the repository contains
`.claude-plugin/marketplace.json` on `main`.

## Claude Desktop and Cowork — release ZIP

Download the latest `llm-accuracy-<version>.zip` asset from the
[latest GitHub release](https://github.com/warwick-bit/llm-accuracy/releases/latest).
In Claude Desktop or Cowork, open **Customize**, then **Plugins**, and upload
the custom plugin file. Confirm that the self-audit skill appears before relying
on the plugin for consequential work.

For a customised Deterministic Data plugin, edit the source catalogue first,
run the validators and build `deterministic-data-<version>.zip`. Upload that ZIP
to Cowork. Shared installed plugin content is replaced through an updated ZIP or
synced marketplace; it is not an in-place catalogue editor.

### Claude Desktop Chat — skills-only

In the **Chat** tab, LLM Accuracy's skills are available, including self-audit.
The automatic advisory hooks do not run in chat, so use the skill when you want
an explicit check of an earlier answer.

### Claude Cowork — full plugin

In **Cowork**, the plugin's skills and advisory hooks can run. The hook behavior
is the same targeted, non-blocking behavior described for Claude Code terminal.

## Claude chat on the web — personal marketplace (skills only)

On a paid Claude plan, open **Customize**, then **Plugins**. Under **Personal
plugins**, select **Add marketplace**, choose **Add from a repository**, and add
`warwick-bit/llm-accuracy`, then install LLM Accuracy from the new
marketplace.

Chat exposes the plugin's skills, including self-audit, but does not run its
advisory hooks. Team and Enterprise owners can instead connect the
repository as an organization marketplace for controlled member distribution.

## Claude Code on the web — pilot only

LLM Accuracy is **not yet supported** in Claude Code on the web. User-scoped
plugins from a local machine do not carry into its fresh cloud environment.

To pilot it, nominate a target coding repository and test a project-scoped
marketplace declaration in that repository's `.claude/settings.json`. The cloud
environment must be able to reach this GitHub marketplace. Do not treat cloud
behavior as supported until that smoke test has passed.

## Migrating from the private preview

The marketplace was renamed from `llm-accuracy-preview` to `llm-accuracy` for
the public release. If you installed during the private preview, remove the old
marketplace and reinstall:

```bash
claude plugin uninstall session-ledger@llm-accuracy-preview --scope user
claude plugin uninstall llm-accuracy@llm-accuracy-preview --scope user
claude plugin marketplace remove llm-accuracy-preview
claude plugin marketplace add warwick-bit/llm-accuracy --scope user
claude plugin install llm-accuracy@llm-accuracy --scope user
```

Session Ledger's local data directory is derived from the marketplace name, so
preview-era ledger records do not carry over after the rename; the default
final-scope uninstall above removes them.

If you also used Session Ledger during the preview, reinstall and enable it
from the new marketplace:

```bash
claude plugin install session-ledger@llm-accuracy --scope user
claude plugin enable session-ledger@llm-accuracy --scope user
```

## Platform references

Claude's product behavior changes independently of these plugins. For current
details, see Anthropic's documentation for
[Claude Code marketplaces](https://code.claude.com/docs/en/discover-plugins),
[plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude),
[organization marketplaces](https://support.claude.com/en/articles/13837433-manage-plugins-for-your-organization),
and [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web).

## Privacy and safety

LLM Accuracy has no telemetry, server-side store, persisted prompt capture, or
tool-output capture. The separate Session Ledger plugin has no telemetry or
server-side store, but does persist a local compact summary and bounded rolling
session record as described above. Neither plugin guarantees factual correctness,
completeness, freshness, or domain truth.

For feedback, submit only sanitized and authorized reproductions through the
feedback issue form.
