# Install LLM Accuracy

LLM Accuracy has different installation and capability paths across Claude
products. Use the path below that matches where you work.

## Preview validation status

Platform capability and this preview's runtime evidence are separate:

- **Claude Code terminal or IDE:** exact shipped hook commands and the automated
  distribution suite were tested on 24 Jul 2026. A clean marketplace
  installation smoke has not yet been recorded.
- **Claude Desktop Chat:** not runtime-smoke-tested for this preview. The
  skills-only description follows Anthropic's current plugin documentation.
- **Claude Cowork:** not runtime-smoke-tested for this preview. The
  skills-and-hooks description follows Anthropic's current plugin documentation.
- **Claude chat on the web:** not runtime-smoke-tested for this preview. The
  skills-only description follows Anthropic's current plugin documentation.
- **Claude Code on the web:** untested and unsupported for this preview.

Recheck the linked platform documentation and record a new tested-on date when
claiming support after a release or host-runtime change.

## Claude Code terminal or IDE — full preview

This is the recommended private-preview path. It includes the self-audit skill
and the targeted advisory hooks.

### Before you start

- Use a current Claude Code installation. If `/plugin` is unavailable, update
  Claude Code first.
- Have `python3` 3.9 or later and a POSIX-compatible hook shell. The preview's
  exact command-launcher tests currently run on POSIX only.
- Ask the preview maintainer to add your GitHub account as a collaborator on
  [`warwick-bit/llm-accuracy`](https://github.com/warwick-bit/llm-accuracy).
- Install only if you trust the plugin source. It runs local advisory hook
  commands in Claude Code.

### Install

Run these commands in your terminal:

```bash
claude plugin marketplace add warwick-bit/llm-accuracy --scope user
claude plugin install llm-accuracy@llm-accuracy-preview --scope user
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

The hooks add reminders only for matching open-ended analysis or source-conflict
prompts and after context compaction. They do not run on every prompt, fetch
evidence, block work, or verify facts automatically.

## Session Ledger — Claude Code terminal or IDE only

Session Ledger is a separate, optional plugin for accuracy across one long
Claude Code session. It starts a bounded local ledger at SessionStart, appends a
rolling user/assistant session record as the session progresses, and flushes it
to local plugin storage before compaction. It restores the record when that same
compacted session continues. Install it only if you accept that the retained
record and Claude's compact summary may contain sensitive local content. It is
unsupported in Claude Desktop Chat, Cowork, Claude chat on the web, and Claude
Code on the web.

Session Ledger requires `python3` version 3.9 or later (CI-tested 3.9-3.13) on the machine running
Claude Code. Check it with `python3 --version` before installing.

Install it after adding the marketplace:

```bash
claude plugin install session-ledger@llm-accuracy-preview --scope user
claude plugin enable session-ledger@llm-accuracy-preview --scope user
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

To refresh the private marketplace, run:

```bash
claude plugin marketplace update llm-accuracy-preview
```

Then run `/reload-plugins` in an active Claude Code session. To remove the
plugins and local Session Ledger data:

```bash
claude plugin uninstall session-ledger@llm-accuracy-preview --scope user
claude plugin uninstall llm-accuracy@llm-accuracy-preview --scope user
claude plugin marketplace remove llm-accuracy-preview
```

The default final-scope uninstall removes Session Ledger plugin data. Do not use
`--keep-data` unless you intentionally want to retain its compact summaries and
local session record.

If installation fails, first confirm that you can access the private GitHub
repository and that it contains `.claude-plugin/marketplace.json` on `main`.

## Claude Desktop and Cowork — release ZIP

Download the latest `llm-accuracy-<version>.zip` asset from the
[latest GitHub release](https://github.com/warwick-bit/llm-accuracy/releases/latest).
In Claude Desktop or Cowork, open **Customize**, then **Plugins**, and upload
the custom plugin file. Confirm that the self-audit skill appears before relying
on the preview for consequential work.

### Claude Desktop Chat — skills-only

In the **Chat** tab, LLM Accuracy's skills are available, including self-audit.
The automatic advisory hooks do not run in chat, so use the skill when you want
an explicit check of an earlier answer.

### Claude Cowork — full preview

In **Cowork**, the plugin's skills and advisory hooks can run. The hook behavior
is the same targeted, non-blocking behavior described for Claude Code terminal.

## Claude chat on the web — personal marketplace (skills only)

On a paid Claude plan, open **Customize**, then **Plugins**. Under **Personal
plugins**, select **Add marketplace**, choose **Add from a repository**, and add
`warwick-bit/llm-accuracy`. Use the GitHub account that the preview maintainer
has added to the private repository, then install LLM Accuracy from the new
marketplace.

Chat exposes the plugin's skills, including self-audit, but does not run its
advisory hooks. Team and Enterprise owners can instead connect the private
repository as an organization marketplace for controlled member distribution.

## Claude Code on the web — pilot only

LLM Accuracy is **not yet supported** in Claude Code on the web. User-scoped
plugins from a local machine do not carry into its fresh cloud environment.

To pilot it, nominate a target coding repository and test a project-scoped
marketplace declaration in that repository's `.claude/settings.json`. The cloud
environment must be able to reach and authenticate to this private GitHub
marketplace. Do not treat cloud behavior as supported until that smoke test has
passed.

## Platform references

Claude's product behavior changes independently of this preview. For current
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
private-preview issue form.
