# Install LLM Accuracy

LLM Accuracy has different installation and capability paths across Claude
products. Use the path below that matches where you work.

## Claude Code terminal or IDE — full preview

This is the recommended and fully supported private-preview path. It includes
the self-audit skill and the targeted advisory hooks.

### Before you start

- Use a current Claude Code installation. If `/plugin` is unavailable, update
  Claude Code first.
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

### Update or remove

To refresh the private marketplace, run:

```bash
claude plugin marketplace update llm-accuracy-preview
```

Then run `/reload-plugins` in an active Claude Code session. To remove the
plugin and marketplace:

```bash
claude plugin uninstall llm-accuracy@llm-accuracy-preview --scope user
claude plugin marketplace remove llm-accuracy-preview
```

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

## Claude chat on the web — organization-managed only

Individual preview participants cannot self-install this private GitHub
marketplace in Claude chat on the web. A Team or Enterprise organization owner
can connect a private GitHub repository to an organization marketplace and make
the plugin available to members. That organization path is separate from this
personal private preview.

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

The preview has no telemetry, server-side store, persisted session ledger,
prompt capture, or tool-output capture. It improves evidence hygiene; it does
not guarantee factual correctness, completeness, freshness, or domain truth.

For feedback, submit only sanitized and authorized reproductions through the
private-preview issue form.
