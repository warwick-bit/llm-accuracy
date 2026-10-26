# Config Doctor — 0.1.2 preview

Find instructions that disagree, outdated advice and missing checks in your
Claude Code or Codex setup. Config Doctor helps your AI review the files you
choose and checks that its report matches those files. It suggests changes;
you decide what to apply.

This is a separate tool. You do not need the LLM Accuracy plugin, and installing
that plugin does not install Config Doctor. The plugin's `accuracy-doctor` command
is a different diagnostic for that plugin's own installation and configuration.

## Start here

1. Open a fresh **Claude Code or Codex** session and paste the prompt below.
   Your agent fetches the released tool for you; no manual download is needed.
2. The workflow needs **Python 3.11 or later** and a session that can fetch files,
   read your selected local files and run Python. No additional Python packages
   or API key are required. Ordinary web chat alone cannot run this local workflow.
3. Choose what you want checked and which files the AI may read when asked.
   It follows the [guide](QUICKSTART.md) to review them and check its report.
4. Review the checklist and proposed edits. Applying changes is a separate decision.

```text
Fetch and extract CONFIG Doctor from this released ZIP into a new local folder:
https://github.com/warwick-bit/llm-accuracy/releases/download/config-doctor-v0.1.2/config-doctor-0.1.2.zip
Do not overwrite existing files. Use its config-doctor folder to audit my selected
profile. Check that Python 3.11+ is available; if not, explain what is needed.
Before any memory/history lookup or audit-input read, read that directory's
QUICKSTART.md by itself. Do not open earlier audit memory, reports or history.
Disclose any historical audit context already loaded; do not use it as evidence.
Ask the audit extent if I have not supplied one or an explicit file manifest.
Account for relevant installed plugins and configured MCP tools in every scope,
using supplied plugin guidance, tool descriptions/schemas and safe settings summaries.
Ask for missing sources or record coverage as unverified before proposing overlaps.
Do not connect to MCP servers or call their tools for this source audit.
For profile-and-harness scope, identify missing or unknown launcher, review
adapter and hook/plugin source before collection. Ask for exact paths or my
explicit acceptance of a partial audit; reuse decisions already supplied.
Use an interactive question tool when available. Do not discover files, run
audited code or change configuration. Follow prepare, assessment and report
validation, and state the selected scope and any unverified coverage.
```

### Optional manual download

If you prefer, [download the ZIP](https://github.com/warwick-bit/llm-accuracy/releases/download/config-doctor-v0.1.2/config-doctor-0.1.2.zip)
and extract it yourself. Use the local-folder startup prompt in
[QUICKSTART.md](QUICKSTART.md), replacing its folder placeholder with your path.

Expect a plain-English checklist of what's already covered, what may need fixing
and what hasn't been checked yet. Each finding explains what was found, why it
matters, how certain it is and the simplest next step. Doctor explains what to
**do first**, what to **keep**, what **needs more checking**, and what's
**optional**, with up to three immediate next actions. You do not need to accept
every recommendation. Include relevant add-ons (plugins) and descriptions of
connections to other services (MCP tools), so Doctor can check what they already
provide before suggesting another rule.

Where a useful follow-up remains, Doctor offers a multiple-choice question:
**Check what's uncertain**, **Try a change safely**, or **Finish here**. It uses
your app's interactive question tool when available and explains what each check
would tell you, which files or tools it needs and the likely effort. You choose
how far to go; a test uses a separate copy and does not change your live setup.

The audit does not connect to MCP servers, call a model itself, execute audited
hooks, change configuration or save persistent memory. Your existing agent performs
the semantic review. Startup instructions cannot remove context the host already
loaded; the agent should disclose it.

## Keep your audit private

Choose only files you authorize. Do not supply credentials, `.env`, transcripts,
raw logs or unrelated data. Prepared packets contain selected text sources in full;
settings are reduced to structural summaries. Keep packets and reports outside this
repository and do not upload them as issues. Credential-pattern refusal is a
backstop, not a complete secret detector or a filesystem sandbox.

## More detail

- [Full workflow and manifest examples](QUICKSTART.md)
- [Practical setup, memory and data-access guidance](SETUP.md)
- [Review principles and limits](EVAL-LESSONS.md)
- [Validation and preview limits](VALIDATION.md)
- [Optional fresh-session audit comparison](COMPARISON.md)

This preview checks source coverage and report consistency. It does not certify
that instructions are loaded or followed, or guarantee more accurate answers.
The full evaluation write-up is separate and is not included in this download.

Licensed under the [MIT License](LICENSE).
