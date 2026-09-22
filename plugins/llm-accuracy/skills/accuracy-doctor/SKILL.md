---
name: accuracy-doctor
description: Check LLM Accuracy version, trigger configuration, bypasses and hook commands when the plugin seems inactive or behaves differently across machines.
argument-hint: "[optional: live]"
---

# Accuracy doctor

Run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/accuracy_doctor.py"` (use `python`
when Python 3 is installed under that name). On Windows, the command probe needs
Git Bash; `--shell` accepts its executable path.

The command probe requires local Python and a shell. Host inventory and `--live`
also require a locally installed Claude Code CLI. In a skills-only host or a
host without these tools, report the check as unavailable; do not imply that
this command diagnoses that host's activation.

Report the package version, reminder mode, configuration status, phrase counts,
disabled checks, host-listed installations and command-probe outcomes. The report contains no configured
phrases, paths, prompts, tool output or credentials. Explain fixed diagnostic
codes using the plugin README. Do not dump settings files or ask for credentials.

Lead with `presentation.headline` verbatim. Report the diagnostic details, then
end with `Checked:`, `Gap:` and `Next:` using the corresponding `presentation`
values verbatim. Do not upgrade the headline to "working", "healthy" or
"nothing needs fixing". These fields describe bounded probes, not the whole
runtime. If an older doctor lacks `presentation`, preserve the same scope and
explicitly mark current-session activation and factual accuracy unverified.

The host inventory filters the plugin name before `@`; the marketplace name
after `@` is not the plugin identity. Every returned installation is for
LLM Accuracy. An unknown version does not mean the row belongs to another
plugin. Multiple rows, disabled entries, unknown versions or mismatches need
inspection in the host's plugin interface; do not guess their origin or remove
them automatically. Registration alone does not prove activation.

The offline probe executes this package's hook commands with synthetic prompts.
It cannot prove the running host loaded the plugin. Verify host registration in
the host's plugin and hook interfaces before attributing a missing reminder to
the model. A skill being available does not prove its hooks ran.

If a live check is requested, run the same command with `--live`. This sends one
synthetic prompt through an isolated Claude Code profile with the package
explicitly loaded and normal trigger defaults. It uses an existing local
subscription login, disables tools and MCPs, and retains no session. Authentication
may need refreshing through the host. Never request secret values in chat.

Separate package-command success, isolated host delivery and model compliance.
The live acknowledgement does not establish factual accuracy, current-session
activation, custom-phrase compliance or Cowork support. Do not silently repair
or overwrite user configuration.
