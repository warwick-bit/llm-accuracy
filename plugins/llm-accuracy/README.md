# LLM Accuracy plugin

LLM Accuracy is a Claude Code and Cowork plugin for evidence-aware LLM work. It
ships general accuracy hygiene rather than a claim of universal factual
correctness.

## What it does

- prompts for provenance, scope, freshness, and caveats on consequential
  factual answers;
- asks for a short clarification on selected common business prompts with
  multiple reasonable definitions, windows, comparisons or sources;
- checks whether claims remain within their source, population, definition,
  window, freshness and completeness boundaries;
- nudges a model to recheck stale details after long sessions; and
- provides self-audit and claim-fidelity workflows;
- includes a stateless evidence-receipt schema and structural validator for
  workflows that already produce typed evidence boundaries.

## What it does not do

- access a provider, database, or external source of truth;
- verify a specific domain metric or business definition;
- certify source truth, arithmetic, domain correctness or factual accuracy;
- create or persist prompt epochs, receipts, prompts, or tool output;
- collect telemetry, persist prompts or tool output, or send data to a server;
  or
- guarantee that an answer is complete, current, or correct. It does not guarantee factual correctness.

Hooks are advisory and non-blocking.

The receipt validator emits `structural_only` results and stable error codes. A
pass means the receipt satisfies the generic structural contract; it does not
mean the underlying claim is correct.

## Day-to-day use

Once installed and activated, use Claude Code or Cowork normally. A general
fidelity reminder covers each non-empty prompt, including technical requests,
file paths, implementation requests and brief follow-ups. It asks Claude to
verify the measurement, population and environment, establish coverage before
universal claims, test competing causes, and revisit dependent conclusions after
a correction. It also points diagnoses and fix checks to the verify-technical skill;
the model still decides whether to invoke it.

For substantive technical diagnoses and verification claims, the reminder asks
for a compact `Checked / Gap / Next` footer: what was actually checked and its
scope, what remains unresolved or untested, and the next action (or none).
Routine replies do not need it. The answer body must retain material uncertainty;
the footer is a model-written account, not a validated receipt. Hook tests prove
the instruction is emitted, not that Claude follows it.
Targeted mode includes this guidance only when a fidelity trigger matches.

Business-ambiguity, analysis and source-conflict reminders remain targeted.
The post-compaction reminder remains separate. None verifies facts automatically.

## Reminder modes

- **General (default since 0.6.0):** a short evidence reminder on each non-empty
  prompt. Explicit evidence-boundary prompts also receive the existing detailed
  fidelity guidance. Greetings and creative tasks receive the general reminder
  too; it asks Claude to keep non-factual tasks brief. This trades extra context
  for coverage, not for guaranteed compliance or correctness.
- **Targeted:** set `CC_CLAIM_FIDELITY_MODE=targeted` in the environment inherited
  by Claude Code to restore the previous keyword-gated fidelity behaviour.
  Unset it or use `general` to restore the default. Unknown values use general
  mode. Restart Claude Code after changing its inherited environment.
- **Mute:** include `# fidelity-ok` in a prompt, or set
  `CC_SKIP_CLAIM_FIDELITY=1` in the host environment. These controls mute only the
  fidelity reminder; the other hooks keep their own controls.

For example, start a targeted-only Claude Code session from a POSIX shell:

```bash
CC_CLAIM_FIDELITY_MODE=targeted claude
```

Do not edit installed cache files to configure the mode. Host support for
inheriting environment settings varies; this shell example is for Claude Code,
not a Cowork settings control.

## Custom trigger phrases

Create `llm-accuracy.json` in your Claude configuration directory, outside the
plugin cache. The default is `~/.claude/llm-accuracy.json` on Linux/macOS and
`%USERPROFILE%\.claude\llm-accuracy.json` on Windows. If you use
`CLAUDE_CONFIG_DIR`, put it there instead. Alternatively, set
`LLM_ACCURACY_CONFIG` to the full path of your own JSON file in the environment
inherited by Claude Code.

```json
{
  "schema_version": 1,
  "extra_triggers": {
    "claim_fidelity": ["packet capture", "release verification"],
    "analysis": ["capacity planning"],
    "fusion_evidence": ["conflicting logs", "replica mismatch"]
  }
}
```

- **Claim fidelity:** evidence scope, measurement, coverage and causal claims.
  In general mode, a match adds detailed guidance to the short baseline. In
  targeted mode, it activates the check even when built-in phrases do not match.
- **Analysis:** the existing open-ended data-analysis contract. Use for analysis
  of your domain's data, not for every technical word.
- **Source conflict (`fusion_evidence`):** the existing source-reconciliation
  contract. Use for wording that signals conflicting or incomplete evidence.

Matches are additive and apply only to the selected check. A custom match takes
precedence over the built-in file-path, lookup and execution suppressors, but
never over that hook's bypass marker or skip environment variable. They add the
plugin's fixed guidance; they do not execute commands, add custom instructions,
or force a skill invocation.

Phrases ignore case and normalize repeated whitespace. They match whole words
or phrases: `trace` matches `(trace)` but not `traces` or `trace_id`. Punctuation
is literal: `net.py` does not match `netXpy`, and `a.*b` is not a regex.

Each family accepts up to 64 phrases of 120 characters each; each phrase must
contain a letter or number. The entire UTF-8 JSON file is capped at 32 KiB.
Unknown keys, invalid types, invalid JSON, unreadable files and oversized files
disable custom triggers for that invocation, leaving built-in behaviour intact.
Diagnostics contain a fixed code, never the path, phrases or file contents.
An absent default file is normal and silent. The file is reread on each hook
invocation; editing it needs no plugin update. Restart Claude Code if you change
the environment variable that selects the file.

Use non-sensitive phrases. Although the hook does not echo or persist them,
the configuration file is ordinary local plaintext. Cowork discovery of this
user-owned file is not runtime-tested; do not assume the desktop host shares the
same home directory or environment as your terminal.

## Runtime boundaries

The hook requires the documented `prompt` field. Empty, malformed or oversized
inputs (over 1,000,000 characters of serialized input) fail open without a
reminder. It does not persist prompts, read transcripts, count retractions or
enforce a Stop gate. Child sessions that do not emit `UserPromptSubmit` do not
receive this reminder directly. The partial-result sentinel covers MCP envelope
signals, text Read line-range metadata, and Bash saved-output metadata. It never
parses shell stdout or file contents for pagination fields. Missing metadata and
silently incomplete reads remain invisible. An intentional excerpt is not a
failure, and no signal certifies full-file or project-wide coverage.

## Diagnose activation

Run `/llm-accuracy:accuracy-doctor` when reminders appear inactive. The local
report checks package version, general/targeted mode, user-config validity,
phrase counts, bypasses and actual registered hook commands using synthetic
prompts. It also lists the host's reported installation versions and enabled
flags for this plugin. `not_listed` can be normal for an explicit `--plugin-dir`
load. Neither registration nor a working command proves the current session
loaded a hook: `current_session_activation` remains `unverified`.

The doctor generates a bounded `presentation` with a headline and Checked/Gap/Next
text. `local_probes_passed` means only these local checks passed. `attention`
means a diagnostic check needs investigation. Neither means the assistant is
factually accurate. Missing, disabled, multiple, unknown-version or mismatched
host registrations get an inspection prompt even when local probes pass.
Inventory rows identify **LLM Accuracy**, not every plugin from its marketplace;
an unknown version must not be guessed to belong to Session Ledger.

The underlying script is `scripts/accuracy_doctor.py` in the installed plugin.
Use Python 3; on Windows install Git Bash or pass its path using `--shell`.
`emitted` means the command returned hook context; `disabled` identifies a
bypass; `no_context`, `invalid_response`, `execution_failed`, `timeout` and
`shell_unavailable` need investigation. `missing_default` is normal;
`config_unavailable` or `invalid_config` leaves only built-in triggers active.
Unknown reminder modes are reported and fall back to general mode.

Add `--live` only when you want one model request. It uses an existing local
Claude subscription login in a temporary auth-only profile, explicit plugin
load, default trigger controls, no tools/MCPs and no saved session. It checks
hook delivery and a simple acknowledgement. It does not certify factual
accuracy, your current session, custom phrases, or another host. Authentication
can require `claude auth login`; never share credentials. This opt-in diagnostic
invokes local commands and sends a synthetic prompt to Claude; automatic hooks
do neither. No raw answers or credential values are reported.

## Verify technical work

Use `/llm-accuracy:verify-technical` for a diagnosis, disputed cause or fix claim.
It asks for a scoped reproduction, competing explanations, the smallest justified
change, and a rerun of the original check. Local verification, deployment and
production verification stay separate. Corrections require checking dependent
conclusions again. The workflow is advisory and respects repository instructions.

Before concluding, check intermediate assertions as well as the final verdict.
A plausible alternative that the evidence cannot distinguish leaves the claim
unresolved. State directly supported narrow facts plainly, and keep the same
scope in the headline, body and footer. Passing unspecified tests does not
establish a particular fix; relative build age does not establish patch contents.

Maintainers can run the opt-in synthetic behavioural suite described in
[`docs/technical-evaluation.md`](https://github.com/warwick-bit/llm-accuracy/blob/main/docs/technical-evaluation.md). Factual
field support and footer presence are scored independently; neither certifies
arbitrary prose or real-world accuracy.

## Freshness and memory

An LLM can over-weight recalled training material, earlier context, or a stale
summary after a long session. The result can sound confident but be outdated or
unsupported. This plugin therefore asks the model to recheck current evidence,
label inference, and say when a source is unavailable instead of filling the
gap from memory.

## Feedback boundary

Use synthetic, authorised material in feedback and follow the repository's
[contributing guide](https://github.com/warwick-bit/llm-accuracy/blob/main/CONTRIBUTING.md).

No session ledger, prompt history, or tool output is included or persisted by
this plugin.

### Live diagnostic counters

The doctor includes fixed `counter_definitions` in its live report.
`host_inventory` reports only allowlisted counts from the host's init event;
missing inventory is `unreported`, not evidence of an empty host. A host may
include its own shared components, such as a reported `telemetry` plugin.
Identical per-turn inventories are accepted; changed entries report `changed`.
Model identity is `unreported` if it differs between turns.
`fidelity_hook_responses` counts delivered claim-fidelity reminders;
`hook_response_count` counts all hook-response events, including silent ones.
`builtin_signal_responses` is a legacy name for events containing a
`PARTIAL RESULT SIGNAL` warning. It does **not** count keyword matches.
The tool-free acknowledgement probe normally reports zero for this counter;
that does not mean prompt checks are inactive. A successful acknowledgement
proves neither factual accuracy nor activation in your existing conversation.

## Opt-in technical review

From 0.7.0, explicitly invoke:

```text
/llm-accuracy:technical-review model=<available Claude model>
```

Supply the original question, complete draft and attributed evidence. The command
uses a fresh Claude context to flag unsupported assertions, missing requested
content and unwarranted uncertainty. It does not run automatically or change the
normal reminders. Choose a reviewer model available in your Claude account;
there is no silent fallback. A different model is only established relative to
a known, caller-reported author identity; unknown identity remains unknown.

This requires local Python 3 and a signed-in Claude Code CLI. Each invocation
makes one additional model request, with medium effort and a default 180-second
limit, consuming account usage. The helper disables tools, MCPs and session
persistence, checks reported host inventory, and temporarily copies local CLI
authentication into an isolated profile that is deleted afterwards. It saves no
packet or response. The parent conversation and provider retention still apply.
A host-reported shared `telemetry` component is tolerated; the plugin adds none.
Native Windows and Cowork execution of this command are unverified.

Missing or oversized packets are rejected rather than silently trimmed: maximum
24,000 characters on stdin and after JSON serialization, with 1..20 evidence
items. The helper returns only fixed categories, exact character locations,
evidence IDs, model metadata and a scoped Checked / Gap / Next receipt. Findings
are model judgments to recheck against the cited evidence. A failed review is
unavailable, never a clean verdict. No findings means only that the reviewer
found no material issue in the supplied packet. It does not establish source
truth, packet completeness, factual accuracy or task completion.

A synthetic check you can paste after the command:

```text
Question: What is the incident status?
Draft: Status: Open. Local tests reportedly pass.
Evidence e1, user report: Local tests pass. Production is unchecked.
No incident tracker status was supplied.
```

Look for a finding on the unsupported `Status: Open` assertion; reporting local
tests as a user claim should remain valid. As a separate control, supply an
authoritative tracker status of Closed and a draft that attributes Closed to
that tracker while leaving recovery unverified. The reviewer should preserve
that supported narrow fact. These checks are fallible model behavior, not
installation or accuracy guarantees.

The underlying CLI is available to trusted local callers:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/technical_review.py" --model <model>
```

Pass JSON via stdin with exactly `question`, `draft`, and `evidence` keys.
Each evidence item has `id`, `source`, and `text`. Use local IDs such as `e1`.
Optional `--author-model` accepts a known full `claude-...` identity; omit when
unknown. Optional `--timeout` accepts 1..180 seconds. Exit 0 means parsed review,
exit 2 means unavailable. `start` and `length` are zero-based Python character
positions in the indicated question/draft anchor, not byte offsets.

See [pilot evidence](https://github.com/warwick-bit/llm-accuracy/blob/main/docs/technical-review-pilot.md)
for the small authored test, earlier failed gates and its limits. Broader
real-answer accuracy improvement has not been demonstrated.
