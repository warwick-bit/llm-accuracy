# LLM Accuracy Repository Guidance

This public repository distributes standalone Claude Code plugins.
Keep each plugin generic and safe to share publicly.

## Before changing files

- Check `git status --short` and `git log --oneline -5`.
- Keep work on a dedicated branch and open a draft PR before merge.
- Treat each directory under `plugins/` as independently packaged Claude Code
  source. `llm-accuracy` is stateless; `session-ledger` and `evidence-memory`
  are separately installed local-persistence plugins.
- Do not copy material from a company, customer, provider, private prompt, or
  local-runtime configuration into this repository without a documented review.

## Packaging and privacy

- Keep `.claude-plugin/plugin.json` versioned with each release.
- Keep hook commands relative to `${CLAUDE_PLUGIN_ROOT}`; hooks must remain
  advisory and non-blocking.
- Do not add credentials, telemetry, raw prompts, provider payloads, customer
  data, or persisted session-ledger contents to repository source, fixtures,
  issues, or pull requests. Session Ledger may persist only its bounded compact
  summary and rolling session record. Evidence Memory may persist exact tool
  results and durable state only after the plugin is explicitly enabled in Claude
  settings. An enabled plugin starts capture for each session at a fresh cutoff;
  session-level disable, clear, and plan boundaries must stop automatic capture
  for that session until an explicit resume.
  Each plugin uses its own `${CLAUDE_PLUGIN_DATA}` directory; preserve the
  local-only, same-session, same-plan, 30-day boundary and keep captured data
  out of source.
- Keep the public-facing claim bounded: the plugin improves evidence hygiene;
  it does not guarantee factual correctness.

## Required checks

Run `python3 -m pytest -q`, JSON parsing for the marketplace and plugin
manifests, and `python3 -m py_compile` for every hook module. Run a clean
Claude installation smoke before a release.
