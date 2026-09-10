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

## Current structural rerun

Observed: Claude Code 2.1.267, 10 Sep 2026, Linux (WSL2). A fresh authenticated
`CLAUDE_CONFIG_DIR` ran the repeatable smoke below against this source plugin.
The observer retained event names, key names, and boolean presence flags only.
The harness derives per-event counts plus safe execution and exit status from
those structural receipts; it never retains a host payload value.
The committed [content-free receipt](../../../docs/validation/session-ledger-host-smoke-2026-09-10.json)
contains the complete retained result.

- The direct scenario emitted `SessionStart`, `UserPromptSubmit`, and `Stop`.
- The named no-tool child emitted `SubagentStart` and `SubagentStop` with
  `agent_id` and `agent_type` present. Both lifecycle payloads carried the
  parent test session id (`shared-session`).

This is a structural receipt, not a fresh compaction-ordering or natural-recall
claim.

## Source-level subagent policy

Claude Code's current hook documentation defines `SubagentStart` and
`SubagentStop` lifecycle events with `agent_id` and `agent_type` fields. Session
Ledger does not register those events, persist either field, or use either
field to infer a parent-child relationship. Its only identity inputs are the
host-provided `session_id` and `cwd`:

- hook deliveries with the same session id and workspace append to the same
  full-fidelity rolling record, even when their optional agent metadata differs;
- deliveries with a different session id remain in a separate record; and
- the plugin does not claim that a particular host version uses either identity
  arrangement for subagents until a host smoke observes it.

This keeps the local record keyed to Claude Code's own session boundary without
persisting raw actor identifiers or inventing an unsupported parent-child map.

## Repeatable current-host structural smoke

`scripts/session_ledger_host_smoke.py` is a clean-config smoke for the current
Claude Code host. It loads the source plugin directly for one non-interactive,
synthetic turn and generates a temporary observer plugin. The observer records
only event names, the complete host-defined payload key set (never values),
allowlisted `SessionStart.source` values, and boolean presence flags for
`session_id`, `agent_id`, and `agent_type`. The report derives per-event counts
and safe execution/exit status from those structural receipts. Claude
stdout/stderr, every payload value, prompts, transcripts, model output, and
credentials are captured and discarded. The Claude child receives only `HOME`,
`PATH`, the clean config path, the observer-receipt path, and a synthetic
requested-session id; it does not inherit ambient environment values. `HOME`
and `CLAUDE_CONFIG_DIR` both point to the clean config directory.

Use an empty persistent config directory and authenticate it interactively once
before running the smoke. On Linux and Windows, `CLAUDE_CONFIG_DIR` includes
the login credential, so this does not copy or read credentials from another
Claude profile:

```bash
CLAUDE_CONFIG_DIR=/path/to/clean-claude-config claude
# Run /login interactively, then exit.
python3 scripts/session_ledger_host_smoke.py \
  --config-dir /path/to/clean-claude-config --scenario direct
python3 scripts/session_ledger_host_smoke.py \
  --config-dir /path/to/clean-claude-config --scenario subagent
```

The direct scenario requires `SessionStart`, `UserPromptSubmit`, and `Stop`.
The subagent scenario requires `SubagentStart`, `SubagentStop`, and the three
direct-turn events. It records only boolean agent-metadata presence on the two
lifecycle events, then reports whether their host session ids equal the
requested test session (`shared-session`) or differ (`separate-session`).
Neither arrangement warrants an identity-policy change; a `FAIL` is an
inconclusive host result. `not_observed`, `missing-session-id`, and
`mixed-session` are also inconclusive mappings, never an invitation to infer a
parent-child relationship. This structural smoke deliberately does not re-test
the historical forced-compaction receipt above (Claude Code 2.1.218, 24 Jul
2026): run and record a separate interactive `/compact` receipt before making a
newer ordering claim.

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
