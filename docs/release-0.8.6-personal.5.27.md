# LLM Accuracy 0.8.6-personal.5.27

This release stops background results from setting off the final source reread.

## Changes

- Claude Code submits a finished background task (`<task-notification>`) and a
  subagent's report (`<agent-message>`) as prompts, so each one ran the
  `UserPromptSubmit` hook. A long one marked the turn, and the Stop hook then
  asked for a source reread of the reply to that delivery.
  Prompts that start with either tag no longer mark a reread, and they clear a
  leftover marker the way a short prompt does.
- Other typed prompts behave as before, including one that mentions either tag
  after its opening text. A typed prompt that opens with either tag is treated
  as a delivery.
- Earlier changes are in the
  [0.8.6-personal.5.26 release notes](release-0.8.6-personal.5.26.md).

## Qualification and limits

In a print-mode probe on Claude Code 2.1.316, the `UserPromptSubmit` input for a
finished background command started with `<task-notification>` and the input
for a background subagent's report started with `<agent-message`. The input had
no field naming where a prompt came from, so the hook matches on the prompt's
opening text. The match also accepts the `Another Claude session sent a
message:` line that interactive transcripts show before an agent message. If
Claude Code changes these wrappers, the extra rereads return; typed prompts
keep their reread either way.

In print-mode sessions on Claude Code 2.1.287 with the plugin loaded from source
(one run per case), the reply after a finished background command was asked for
a reread with the 0.8.6-personal.5.26 hooks and was not with these hooks. A
typed 346-character prompt with figures was still asked for one. Interactive
sessions and subagent hand-backs were not run.

The [live bundle receipt](validation/claude-bundle-smoke-0.8.6-personal.5.27.json) and
[Accuracy installation/archive receipt](validation/claude-code-smoke-0.8.6-personal.5.27.json)
record the final package's native Windows qualification. Publication requires
the release gates, including installed-hook checks on Linux, macOS and Windows
with and without Git Bash. Other live and UI coverage remains as recorded in
the compatibility matrix; these terminal checks do not certify Desktop or Cowork.

## Update

Refresh the `warwick-bit/llm-accuracy` repository marketplace in Claude or Codex,
update **LLM Accuracy**, confirm **0.8.6-personal.5.27**, and start a new conversation.
Claude Desktop and Cowork users upload the release ZIP instead.
