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

## Skill command context (documented, not yet live-verified)

The `begin-plan` and `clear` skills embed an inline `` !`command` `` that runs
as skill preprocessing. Per the official docs (code.claude.com/docs/en/skills
and /plugins-reference, checked 2026-07-24): inline-command preprocessing runs
when a skill is invoked; `${CLAUDE_SESSION_ID}` is a documented skill content
substitution; `${CLAUDE_PLUGIN_ROOT}` and `${CLAUDE_PLUGIN_DATA}` are
documented plugin command substitutions. The docs are silent on whether these
values are also present as *shell environment variables* during that
execution, so the skill commands must stay honest on failure: if either value
is missing, the script prints a "Could not confirm ..." line instead of
silently doing nothing, and each SKILL.md tells the model to report that
outcome. A live in-session verification of both skills is still pending.
