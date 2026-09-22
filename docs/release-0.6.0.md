# LLM Accuracy 0.6.0

Prepared release notes. This candidate has not been published.

Technical prompts and short follow-ups now receive evidence guidance by default.
The guidance asks Claude to check support before diagnosing, separate observed
facts from hypotheses, and update dependent conclusions after a correction.
These are advisory instructions; the plugin does not verify facts by itself.

## Changes

- Add user-owned literal phrases for claim fidelity, analysis and source-conflict
  reminders. Configuration lives outside the plugin cache and survives updates.
- Request compact **Checked / Gap / Next** footers for substantive technical
  diagnoses and verification claims. Routine replies are excluded.
- Add `/llm-accuracy:verify-technical`: reproduce, isolate, fix and rerun the
  original check. Keep local, deployment and production evidence separate.
- Add `/llm-accuracy:accuracy-doctor`: inspect version, configuration, bypasses
  and hook commands. Explicit live mode checks isolated Claude Code delivery.
- Recognize Read and Bash excerpts from typed host metadata, alongside existing
  MCP partial-result checks. Missing metadata does not trigger a warning.
- Add synthetic behavioral checks that score declared factual fields separately
  from footer formatting. Equivalent decimal answers compare by value.
- Stop owned diagnostic subprocesses when interrupted; avoid selecting the
  Windows WSL launcher as a native Git Bash hook shell.

## Upgrade after publication

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy --scope user
```

Run `/reload-plugins` in Claude Code. Use `/llm-accuracy:accuracy-doctor` to check
configuration and package commands; check `/plugin` and `/hooks` for the current
host's registration. No data migration is required.

General reminders add context to each non-empty prompt. Set
`CC_CLAIM_FIDELITY_MODE=targeted` to restore keyword-targeted behavior. Existing
bypasses remain available. See [configuration and custom phrases](../plugins/llm-accuracy/README.md#custom-trigger-phrases).

## Validation and boundaries

The [candidate install receipt](validation/claude-code-technical-smoke-2026-09-23.json)
records a clean local marketplace install, installed defaults, custom phrase,
bypass, ZIP loading and source identity. [Installation status](INSTALL.md#validation-status)
separates Linux/WSL runtime evidence, native Windows CI and untested hosts.

A compact footer is model-written, not an accuracy certificate. The small
[technical evaluation](technical-evaluation.md) does not establish general
accuracy improvement. Live diagnostics need local Claude Code and existing
login; they do not verify another session or machine. Cowork behavior for the
new features remains untested. The separate experimental analytical-review
proposal is outside this release.
