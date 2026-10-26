# Config Doctor — 0.1.3 preview

Find instructions that disagree, outdated advice and missing checks in your
Claude Code or Codex setup. Config Doctor helps your AI review the setup you
choose and checks its report against the files reviewed. It suggests changes;
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
3. Choose what you want checked. The AI finds the relevant files in that setup
   for you; you do not need to know file paths or make a file list. It follows
   the [guide](QUICKSTART.md) to review them and check its report.
4. Review the checklist and proposed edits. Applying changes is a separate decision.

```text
Fetch and extract CONFIG Doctor from this released ZIP into a new local folder:
https://github.com/warwick-bit/llm-accuracy/releases/download/config-doctor-v0.1.3/config-doctor-0.1.3.zip
Do not overwrite existing files. Use its config-doctor folder to audit my selected
profile. Check that Python 3.11+ is available; if not, explain what is needed.
Before any memory/history lookup or audit-input read, read that directory's
QUICKSTART.md by itself. Do not open earlier audit memory, reports or history.
Disclose any historical audit context already loaded; do not use it as evidence.
Ask what I want checked using a short multiple-choice question, unless I already
chose. Explain that you will find the relevant files in that setup for me, following
the guide's bounded collection rules. Do not ask me to supply file paths or a
manifest as the normal starting step. Keep an explicit file list I supply strict.
Include relevant installed add-ons and available descriptions of connected tools;
check what they already provide before suggesting another rule. Do not connect to
services, run the files being reviewed, read credentials or change my setup.
Ask again only for a real choice, such as which setup I mean or whether to include
an additional folder. Explain findings and anything you could not check in plain
English. Prepare the audit, complete the assessment and validate the report.
```

### Optional manual download

If you prefer, [download the ZIP](https://github.com/warwick-bit/llm-accuracy/releases/download/config-doctor-v0.1.3/config-doctor-0.1.3.zip)
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

Doctor searches only within your chosen setup. Do not supply credentials, `.env`, transcripts,
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
