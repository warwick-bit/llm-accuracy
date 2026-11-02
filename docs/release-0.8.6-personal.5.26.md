# LLM Accuracy 0.8.6-personal.5.26

This release merges the accuracy skills into one Verify skill, so Claude Desktop
users get the checks without choosing between several skills, and adds a final
reread against the supplied source.

## Changes

- One **Verify** skill replaces Verify Numerical, Verify Technical, Claim
  Fidelity and Self-Audit, and absorbs the saved-output audit guidance. Clarify
  and Accuracy Doctor stay. Codex gets Verify and Clarify.
- Verify ends with "Reread against the source before sending", so the check
  also runs where plugin hooks don't.
- One fail-open Stop-hook reread on turns that use supplied material. It is the
  stronger reread and runs where plugin hooks run.
- The Verify description also covers people asking whether a claim, figure or
  draft is right before it is sent, forwarded or shared.
- Includes the saved-output and data-check work from the personal.3 and
  personal.4 candidates.

## Qualification and limits

The [live bundle receipt](validation/claude-bundle-smoke-0.8.6-personal.5.26.json) and
[Accuracy installation/archive receipt](validation/claude-code-smoke-0.8.6-personal.5.26.json)
record the final package's native Windows qualification. Publication requires
the release gates, including installed-hook checks on Linux, macOS and Windows
with and without Git Bash. Other live and UI coverage remains as recorded in
the compatibility matrix; these terminal checks do not certify Desktop or Cowork.

A personal-account Claude Desktop check of the 0.8.6-personal.5.25 package (one
run per case, before the description change) gave right final answers in all
core cases. In sessions with a folder the reread fired and caught a mislabelled
figure and unsupported claims. Sessions without a folder showed no hook
evidence and kept some unsupported additions, so attach a folder for checked
work. Plugin hooks are ignored in Desktop Chat.

In hooks-off command-line tests, the new description got Verify chosen on
everyday team-style prompts in 7 of 12 runs, against 1 of 12 for the previous
description, with no selections on 9 control prompts for either. Selection
varied widely between days for identical text, and these small command-line
samples stand in for Desktop. Automatic skill selection remains unreliable on
everyday wording; ask for a check in plain words.

The plugin improves evidence discipline; following its guidance remains
model-dependent and does not guarantee correctness.

## Update

Refresh the `warwick-bit/llm-accuracy` repository marketplace in Claude or Codex,
update **LLM Accuracy**, confirm **0.8.6-personal.5.26**, and start a new conversation.
Claude Desktop and Cowork users upload the release ZIP instead.
