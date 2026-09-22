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
a correction. It also points consequential diagnoses to the claim-fidelity skill;
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
receive this reminder directly. The partial-result sentinel still covers MCP
results only, not Bash output or silently incomplete reads.

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
