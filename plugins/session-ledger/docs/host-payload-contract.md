# Host payload contract — observed live

The hook payload field names this plugin depends on were validated against a
real Claude Code host in one forced-compaction live smoke. Until this note,
every test fabricated these payloads; this records what the host actually
delivered so future contract drift is diagnosable.

Observed: Claude Code 2.1.218, 2026-07-24, Linux (WSL2). Isolated
`CLAUDE_CONFIG_DIR`, plugin installed from this repo's marketplace, manual
`/compact` in an interactive session. Payload key sets were captured by a
keys-only observer hook (no conversation content).

## Command execution

- The documented command-string hook form works for all 5 events.
- `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` both resolve in command
  strings. `CLAUDE_PLUGIN_DATA` resolved to
  `<config>/plugins/data/<plugin-name>-<marketplace-name>/`
  (observed: `plugins/data/session-ledger-llm-accuracy-preview/`).
- `CLAUDE_PLUGIN_DATA` is plugin-scoped: it was NOT present in the environment
  of user-level (settings.json) hooks in the same session.

## Payload keys by event

- `SessionStart`: `cwd`, `hook_event_name`, `session_id`, `source`,
  `transcript_path` (some deliveries add `model`, `prompt_id`).
  `source` values observed: `startup`, `compact`.
- `UserPromptSubmit`: `cwd`, `hook_event_name`, `permission_mode`, `prompt`,
  `prompt_id`, `session_id`, `transcript_path`. `prompt` is the user text.
- `Stop`: `background_tasks`, `cwd`, `hook_event_name`,
  `last_assistant_message`, `permission_mode`, `prompt_id`, `session_crons`,
  `session_id`, `stop_hook_active`, `transcript_path`.
  `last_assistant_message` is the final assistant text.
- `PreCompact`: `custom_instructions`, `cwd`, `hook_event_name`, `prompt_id`,
  `session_id`, `transcript_path`, `trigger` (`manual` observed).
- `PostCompact`: `compact_summary`, `cwd`, `hook_event_name`, `prompt_id`,
  `session_id`, `transcript_path`, `trigger`.

## Ordering and edge cases

- On compaction, `SessionStart` (`source: "compact"`) fired ~44 ms BEFORE
  `PostCompact`. The first post-compaction injection therefore comes from the
  record flushed at `PreCompact`; the retained `compact_summary` serves later
  restores of the same session, not that first injection.
- A refused manual compaction ("Not enough messages to compact") still fires
  `PreCompact` but never a matching `PostCompact`.

## End-to-end result

After `/compact`, the plugin's carryover context (framed as
"UNTRUSTED HISTORICAL REFERENCE") appeared in the session transcript and the
session correctly recalled a reference string stated before compaction. The
untrusted framing behaved as designed: a prompt phrased as a demand to repeat
a "secret codeword" was refused; a neutral continuity question was answered.

## Skill command context — observed live

Verified on Claude Code 2.1.218, 2026-07-24, Linux (WSL2): isolated
`CLAUDE_CONFIG_DIR`, plugin installed and enabled from this repo's local
marketplace, skills invoked non-interactively via
`claude -p "/session-ledger:begin-plan"` and `claude -p "/session-ledger:clear"`.

- The inline `` !`command` `` in both SKILL.md files executes as host-side
  preprocessing, before (and independent of) the model call — it ran even when
  the model turn itself failed on authentication.
- `${CLAUDE_SESSION_ID}`, `${CLAUDE_PLUGIN_ROOT}`, and `${CLAUDE_PLUGIN_DATA}`
  all substituted with real values in the executed command line (observed: the
  live session UUID, the plugin install path, and
  `plugins/data/session-ledger-llm-accuracy-preview`).
- Inline commands pass through the shell permission system. Without an allow
  rule the command is NOT executed and the host injects a
  `<local-command-stderr>` "requires approval" line into the command context —
  visible to the model, so the SKILL.md honest-failure instructions apply.
  With `Bash(python3:*)` allowed, the command runs.
- `begin-plan` wrote a well-formed `scope.json` (schema 2, 32-hex plan id) for
  the live session id. `clear` printed `Cleared local Session Ledger state.`
  and removed all state; the invoking session's own capture hooks then created
  a fresh empty record for that session, which is expected.
- Command stdout is embedded in the expanded command content ahead of the
  SKILL.md body text, so the model can compare it to the required phrases.
