# Reminder cadence: SessionStart once vs every prompt (October 2026)

This tests whether a static instruction injected once by a `SessionStart` hook
keeps working as well as the same text injected on every `UserPromptSubmit`, deep
into a session, while another per-prompt banner competes for attention. Each
experiment has three arms that differ only in how the instruction is registered:

- `every_prompt`: the instruction is injected on every prompt (the released behaviour);
- `session_start`: the byte-identical text is injected once, from `SessionStart`;
- `none`: no instruction. This framework-off control shows the behaviour comes from the text.

All arms also carry a fixed per-prompt advisory banner of about 1.6k characters.
Prompts and banners never mention the behaviour being scored. The decision rules
were written before any model run. A verdict needs at least 12 sessions per arm;
anything smaller is a screen.

## Instructions under test

1. **Claim-fidelity contract** (`scripts/eval_reminder_cadence.py`). The scored behaviour
   is the Checked / Gap / Next footer on substantive diagnosis questions. The scorer is
   the deterministic `footer_present` check. Sessions have 8 turns, with probes at turns
   2, 5 and 8 and routine or ~12k-character filler between them. The stress variant has
   20 turns, ~150k characters of filler, and probes at turns 2, 11 and 20.
2. **Metrics-registry pointer** (`scripts/eval_pointer_cadence.py`, Claude Code;
   `scripts/eval_pointer_cadence_codex.py`, Codex CLI). The pointer is a behaviour
   instruction: read a synthetic metric registry before quoting a metric. A probe scores
   as a hit when its metric's entry file was read at or before the probe turn. Only file
   reads are enabled. The S2 variant adds a competing route: a second per-prompt banner
   and CSV exports that invite a direct answer.

Deep probes are those at turns 5 and 8 (11 and 20 in the stress variant).

## Results

```text
Instruction / model             Variant       Per arm  Deep: every / start / none  Label
Contract  claude-opus-5-5       8 turns       12       24/24  24/24  0/24          redundant
Contract  claude-opus-5-5       20 turns      4         8/8    8/8   0/8           holds at depth (screen)
Contract  claude-sonnet-5-5     8 turns       4         8/8    8/8   0/8           screen
Pointer   claude-opus-5-5       main          12-13    26/26  24/24  0/24          redundant
Pointer   claude-opus-5-5       S2            12       24/24  24/24  0/24          redundant
Pointer   claude-sonnet-5-5     S2            4         8/8    8/8   0/8           screen
Pointer   claude-haiku-4-5      S2            4         8/8    4/8   0/8           screen, model-dependent
Pointer   gpt-5.5 xhigh (Codex) main          12       24/24  24/24  0/24          redundant
Pointer   gpt-5.5 xhigh (Codex) S2            12       24/24  24/24  0/24          redundant
```

`redundant` is the predeclared label `every_prompt_redundant_for_retention`. To earn it,
the session-start arm's deep rate is within 10 points of every-prompt, the upper 95%
session-cluster bootstrap bound of the gap is at most 20 points, and over-application
on filler turns rises by at most 5 points. At this ceiling the bootstrap interval is
degenerate ([0, 0]). The Wilson 95% lower bound for the session-start deep rate at
24/24 is 0.862. No arm applied the footer or opened the registry on a filler turn.

On Haiku 4.5 under the competing route, the session-start pointer decayed: 4/8 deep
probes, and 7 of 12 probes answered from the CSV exports without reading the registry
entry. The every-prompt arm on Haiku scored 8/8. Cadence can therefore depend on the
model, and these results should not be carried over to other models without a test.

## Scope

- Headless sessions (`--print` stream-json for Claude Code; `exec` / `exec resume` for
  Codex), synthetic prompts, at most one or two competing banners, and no MCP servers.
- Contract cadence was tested on Claude only: Opus 5.5 (verdict) and Sonnet 5.5 (screen).
  Pointer cadence covers Opus 5.5 and Codex gpt-5.5 (verdicts), plus Sonnet 5.5 and
  Haiku 4.5 (screens).
- Not tested: interactive sessions, real auto-compaction inside a scored session,
  tool-heavy work, or full user configurations with many skills and plugins.
- The receipts measure instruction retention. They do not measure answer correctness.

## Harness notes

The Codex driver runs each session inside `bwrap`. It uses an allowlisted environment,
a private PID namespace, an isolated home, a read-only project, and a closed stdin.
Account connectors, plugins and web search are disabled. Any MCP or web tool item fails
the session's plumbing check. These controls were added after early runs exposed two
problems: an inherited shell environment and reachable account connectors. No scored
Codex receipt comes from a run without them.

## Provenance

The receipts were recorded with drivers carrying the author's private competing banner
and the original wording of the pointer's plugin name and registry path. Before
publication, those strings were replaced with the generic text in the current drivers.
Arms, cases, probes, fixtures, scorers and decision rules are unchanged. As a result:

- `banner_sha256` and `pointer_sha256` in the receipts identify the original text, not
  the published text;
- `harness_commit` values name pre-publication commits that are not in this repository;
- rerunning the published drivers repeats the design with the generic banner. It is
  comparable, but not byte-identical, so `--accumulate` refuses to extend these receipts.

Receipts hold counts, labels and digests only: no prompts, answers or hook output.
