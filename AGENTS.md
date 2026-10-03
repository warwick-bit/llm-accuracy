# LLM Accuracy Repository Guidance

This public repository distributes standalone Claude Code plugins. Evidence
Memory also ships a separate experimental Codex POSIX package; the other plugins
stay Claude-only. Read `docs/COMPATIBILITY.md` before editing runtime or packaging.
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

- Keep `.claude-plugin/plugin.json` versioned with each release, and keep
  `plugins/evidence-memory/.codex-plugin/plugin.json` at the same version.
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
- Before a release, commit the change, run the clean Claude installation smoke
  (`python3 scripts/claude_install_smoke.py --receipt
  docs/validation/claude-code-smoke-<version>.json`), and link that raw-free
  receipt from the release note.

## Required checks

Run `python3 -m pytest -q`, JSON parsing for the marketplace and plugin
manifests, and `python3 -m py_compile` for every hook module. Run a clean
Claude installation smoke before a release.

Run `python3 scripts/check_compatibility.py` before proposing a change. Before a
release, also run it with `--release`. Reset stale candidate receipts to untested;
never copy a historical pass onto changed source. Preserve native Windows without
Git Bash CI and its no-skip check. Skills must not assume POSIX preprocessing or
local execution in Chat. Keep Codex manifests free of Claude userConfig placeholders.

Main publishes the marketplace. Before merging protected source, run
`python3 scripts/check_marketplace_publication.py --base-ref BASE_SHA` with the
actual PR base commit; main/tag builds use `--release`. Keep publication in the
required `release-gates` aggregate and fail on missing or skipped jobs. Its
narrow docs/test exemptions do not cover package READMEs, catalogs or receipts.
Independently review checker/workflow/receipt changes. Require all five Code
targets, including both Windows Bash scenarios. Desktop Chat/Cowork are
experimental stateless skills; keep their six untested rows explicit and
validate any recorded pass, but their gaps do not block Code publication.
Terminal receipts do not certify Desktop Code UI or Cowork hooks. Require
the native installed-Code CI job in the aggregate; missing live authentication
fails. Never manufacture a pass to clear a publication hold. CI credentials
are dedicated Actions secrets; never upload a local login or profile.
