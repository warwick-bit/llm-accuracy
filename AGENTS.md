# LLM Accuracy Repository Guidance

This private preview repository distributes one Claude Code plugin. Keep the
preview generic and safe to share with invited external collaborators.

## Before changing files

- Check `git status --short` and `git log --oneline -5`.
- Keep work on a dedicated branch and open a draft PR before merge.
- Treat `plugins/llm-accuracy/` as the packaged source for Claude Code.
- Do not copy material from a company, customer, provider, private prompt, or
  local-runtime configuration into this repository without a documented review.

## Packaging and privacy

- Keep `.claude-plugin/plugin.json` versioned with the preview release.
- Keep hook commands relative to `${CLAUDE_PLUGIN_ROOT}`; hooks must remain
  advisory and non-blocking.
- Do not add credentials, telemetry, raw prompts, provider payloads, customer
  data, or persisted session-ledger contents.
- Keep the public-facing claim bounded: the plugin improves evidence hygiene;
  it does not guarantee factual correctness.

## Required checks

Run `python3 -m pytest -q`, JSON parsing for the marketplace and plugin
manifests, and `python3 -m py_compile` for every hook module. Run a clean
Claude installation smoke before a release.
