#!/usr/bin/env python3
"""Score a hook against a corpus of real tool results, and report counts only.

The partial-result sentinel makes two kinds of mistake: it can miss a genuinely
partial result, or it can fire on ordinary business data. Argument alone cannot
settle which mechanisms are worth their precision cost, because both failures are
invisible in a fixture suite written by the same person as the rule. So this
measures instead: it replays real tool results, captured from local host
transcripts, through the hook and counts what fires.

SCOPE. The sentinel is wired to `mcp__.*`, so only MCP results are in scope. A
transcript records a result under a top-level `toolUseResult` with a
`tool_use_id`, and the
assistant turn that issued it names the tool; the two are joined to recover the
name. This matters more than it sounds: built-in tool results outnumber MCP ones
by roughly twenty to one locally, so scoring everything reports a denominator
that is mostly out of scope. `--scope all` is available for a deliberately wider
negative corpus, and labels itself as such. "All" means every record carrying a
top-level `toolUseResult`; some built-in results are recorded only inside
`message.content[].content` and are not collected, so `all` is a wider corpus
rather than an exhaustive one.

SAFETY, AND ITS LIMITS. The corpus is real tool output and may contain anything a
tool returned. Counts and signal codes are the only things emitted, and the codes
are checked against a vocabulary this script owns: a hook that returned a
payload-derived string would be counted as `<unrecognised-code>`, never printed.
A hook that raises is counted as `<hook-error>` and its message is discarded,
because an exception message can carry payload. Hook output printed through
Python's `sys.stdout`/`sys.stderr` is captured and dropped.

What that does NOT cover: a hook is arbitrary imported code. It can write files,
open sockets, or write to file descriptor 1 below Python. Measure a hook you
trust; this boundary protects against a hook that is careless, not one that is
hostile.

TWO MODES.

Absolute, "how often does this fire":

    python3 scripts/measure_tool_result_corpus.py

Same-snapshot control, "what did this change cost", which is the one that
matters. A count compared against a count taken earlier is NOT a control: the
corpus grows while you work, because every concurrent session appends to it, so
an unchanged hook can appear to gain detections. Score both versions over ONE
snapshot:

    git show <old-sha>:plugins/llm-accuracy/hooks/partial-result-sentinel.py \\
        > /tmp/old-sentinel.py
    python3 scripts/measure_tool_result_corpus.py --compare-hook /tmp/old-sentinel.py

The unit compared is an OBSERVATION, one (result, signal code) pair, not merely
whether a result fired. A rule change that swaps one code for another leaves the
firing count identical while changing every observation, and reporting `lost: 0`
there would be a false all-clear.

`lost` is what the change stopped detecting. For a precision fix claiming to cost
no recall, `lost` must be 0. That is evidence about THIS corpus, not proof of
recall in general: a shape absent here is unmeasured, not absent in the world.

`unrecognised` must also be 0 to read `lost`/`gained` at face value. Codes outside
the known vocabulary all collapse to one placeholder, so a swap between two
UNKNOWN codes is invisible; a non-zero count means this script's vocabulary is
behind the hook's and must be updated before the comparison means anything.

SELF-CONTAMINATION. A session working ON the sentinel writes its own test
payloads into its own transcript, which then enters the corpus. Exclude it by id;
subagent transcripts are covered too, because the record carries its session:

    --exclude-session <session-id> [--exclude-session <session-id> ...]
"""

from __future__ import annotations

import argparse
import collections
import contextlib
import importlib.util
import io
import json
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Protocol


DEFAULT_TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"

# A transcript line records a tool result under this key, and the matching
# assistant turn names the tool. Everything else on the line is conversation.
TOOL_RESULT_KEY = "toolUseResult"
SESSION_KEY = "sessionId"
MCP_TOOL_PREFIX = "mcp__"

# The vocabulary this script is willing to print. A hook returns a set of codes;
# anything outside this set is a payload-derived string as far as the report is
# concerned, and is counted under a fixed placeholder instead of being rendered.
SIGNAL_CODES = frozenset(
    {
        "pagination_incomplete",
        "truncated_result",
        "row_cap_hit",
        "partial_provider_response",
    }
)
# Canonical instances OWNED BY THIS SCRIPT. A hook may return a `str` subclass
# that compares equal to a known code while rendering something else through
# `__str__`, so a recognised code is replaced by this script's own literal rather
# than kept. Equality is not identity, and only identity is safe to print.
CANONICAL_CODE = {code: str(code) for code in SIGNAL_CODES}
UNRECOGNISED_CODE = "<unrecognised-code>"
HOOK_ERROR_CODE = "<hook-error>"
UNRESOLVED_TOOL = "<unresolved>"

RENDERABLE = SIGNAL_CODES | {UNRECOGNISED_CODE, HOOK_ERROR_CODE}
REPORT_LABELS = frozenset(
    {
        "scope",
        "results",
        "firing",
        "observations",
        "codes",
        "baseline_firing",
        "candidate_firing",
        "baseline_observations",
        "candidate_observations",
        "lost",
        "gained",
        "unrecognised",
    }
)


class CorpusError(Exception):
    """A caller error worth reporting without a traceback."""


class Hook(Protocol):
    """What this script needs from a hook: one function, returning codes.

    Deliberately narrower than "a module". A test can substitute a hostile stub
    to attack the safety boundary, which is the only way to prove the boundary
    holds against a hook that is not the shipped one.
    """

    def collect_codes(self, payload: object) -> object: ...


def load_hook(path: Path, name: str = "sentinel_under_measurement") -> Hook:
    """Import a hook module from a file path, without installing it."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CorpusError(f"not an importable module: {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except OSError as error:
        raise CorpusError(f"cannot read hook: {path}") from error
    return module


def transcript_paths(
    roots: Iterable[Path], exclude_sessions: frozenset[str] = frozenset()
) -> Iterator[Path]:
    """Yield each transcript file once, skipping excluded sessions by path.

    Roots may overlap or repeat, so a file is yielded at most once. The path
    check is a coarse first pass; the authoritative exclusion is per record,
    because a subagent transcript is named for the agent, not its parent session.
    """
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.jsonl")):
            resolved = path.resolve() if hasattr(path, "resolve") else path
            if resolved in seen:
                continue
            seen.add(resolved)
            parts = set(path.parts)
            if any(
                session and (session in path.name or session in parts)
                for session in exclude_sessions
            ):
                continue
            yield path


def _records(path: Path) -> list[dict]:
    """Parse one transcript into records, skipping anything unreadable.

    A corpus is a pile of other sessions' logs, and one truncated line mid-write
    must not abort a measurement over thousands of results. `RecursionError` is
    caught alongside `ValueError` because the JSON decoder raises it on a deeply
    nested array, which would otherwise escape and end the run.
    """
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return []
    records: list[dict] = []
    for line in lines:
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _content_blocks(record: Mapping) -> list[dict]:
    message = record.get("message")
    if not isinstance(message, Mapping):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _tool_names(records: Iterable[Mapping]) -> dict[str, str]:
    """Map tool_use id to tool name, so a result can be scoped to its tool."""
    names: dict[str, str] = {}
    for record in records:
        for block in _content_blocks(record):
            block_id = block.get("id")
            if block.get("type") == "tool_use" and block_id:
                names[str(block_id)] = str(block.get("name") or "")
    return names


def tool_results(
    paths: Iterable[Path],
    *,
    mcp_only: bool = True,
    exclude_sessions: frozenset[str] = frozenset(),
) -> Iterator[object]:
    """Yield tool result payloads, scoped to the tools the hook actually runs on.

    A result names only its `tool_use_id`; the tool name lives on the assistant
    turn that issued it, so each transcript is read once to build that map before
    results are emitted. A result whose name cannot be resolved is treated as out
    of scope under `mcp_only`, because guessing would silently widen the
    denominator this script exists to keep honest.
    """
    for path in paths:
        records = _records(path)
        names = _tool_names(records)
        for record in records:
            payload = record.get(TOOL_RESULT_KEY)
            if payload is None:
                continue
            session = record.get(SESSION_KEY)
            if isinstance(session, str) and any(
                excluded and excluded in session for excluded in exclude_sessions
            ):
                continue
            if mcp_only:
                tool = UNRESOLVED_TOOL
                for block in _content_blocks(record):
                    if block.get("type") == "tool_result":
                        tool = names.get(str(block.get("tool_use_id", "")), tool)
                if not tool.startswith(MCP_TOOL_PREFIX):
                    continue
            yield payload


def _codes_for(payload: object, hook: Hook) -> set[str]:
    """Return the hook's codes for one payload, sanitised and quarantined.

    Three things are deliberately thrown away: a code outside the known
    vocabulary, which could be a payload-derived string; an exception message,
    which could quote the payload; and anything the hook printed.
    """
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            found = hook.collect_codes(payload)
            # Iteration happens INSIDE the guard on purpose. A returned object
            # can raise from `__iter__`, and that exception carries whatever the
            # hook put in it -- which is how the payload escaped once already.
            if not isinstance(found, (set, frozenset, list, tuple)):
                return {UNRECOGNISED_CODE}
            codes = {
                CANONICAL_CODE.get(code, UNRECOGNISED_CODE)
                if isinstance(code, str)
                else UNRECOGNISED_CODE
                for code in found
            }
    except BaseException:  # noqa: BLE001 - a hook is arbitrary code; never trust it
        return {HOOK_ERROR_CODE}
    return codes


def score(
    payloads: list[object], hook: Hook
) -> tuple[set[tuple[int, str]], dict[str, int]]:
    """Return every (result index, signal code) observation, and a count per code.

    An OBSERVATION rather than a verdict per result: two hooks can fire on the
    same results while reporting different codes, and a per-result comparison
    would call that unchanged. Counts are per code as well, not per combination,
    so a result carrying two signals adds one to each.
    """
    observations: set[tuple[int, str]] = set()
    counts: collections.Counter[str] = collections.Counter()
    for index, payload in enumerate(payloads):
        for code in _codes_for(payload, hook):
            observations.add((index, code))
            counts[code] += 1
    return observations, dict(counts)


def compare(payloads: list[object], baseline: Hook, candidate: Hook) -> dict[str, int]:
    """Score one snapshot with two hook versions and report the difference.

    This is the control a raw count cannot give. `lost` counts observations the
    baseline made and the candidate does not; `gained` is the reverse. A
    precision fix claiming to cost no recall must show `lost` of 0 -- which is
    evidence about this corpus, not proof about shapes it never contained.
    """
    before, _ = score(payloads, baseline)
    after, _ = score(payloads, candidate)
    # Every code outside the known vocabulary collapses to one placeholder, so
    # two DIFFERENT unknown codes are indistinguishable here and a swap between
    # them would read as no change. Rather than guess, say how many observations
    # are in that state: a non-zero count means the vocabulary is out of date and
    # `lost`/`gained` cannot be trusted for those observations.
    unrecognised = sum(
        1 for _, code in before | after if code in (UNRECOGNISED_CODE, HOOK_ERROR_CODE)
    )
    return {
        "results": len(payloads),
        "unrecognised": unrecognised,
        "baseline_firing": len({index for index, _ in before}),
        "candidate_firing": len({index for index, _ in after}),
        "baseline_observations": len(before),
        "candidate_observations": len(after),
        "lost": len(before - after),
        "gained": len(after - before),
    }


def safe_summary(summary: Mapping[str, object]) -> dict[str, object]:
    """Return the summary if every key and value is safe to print, else raise.

    The single chokepoint. Both the text report and `--json` go through it, so
    neither can become the path that leaks a payload value. Labels come from a
    fixed set, code names from the known vocabulary, and every leaf is an int.
    """
    checked: dict[str, object] = {}
    for key, value in summary.items():
        if key not in REPORT_LABELS:
            raise CorpusError(f"refusing to report an unknown field: {key!r}")
        if isinstance(value, Mapping):
            for name, count in value.items():
                if name not in RENDERABLE:
                    raise CorpusError(f"refusing to report an unknown code: {name!r}")
                if not isinstance(count, int) or isinstance(count, bool):
                    raise CorpusError(f"refusing to report a non-count for {name!r}")
            checked[key] = dict(value)
        elif isinstance(value, str):
            if value not in {"mcp", "all"}:
                raise CorpusError(f"refusing to report free text for {key!r}")
            checked[key] = value
        elif isinstance(value, int) and not isinstance(value, bool):
            checked[key] = value
        else:
            raise CorpusError(f"refusing to report a non-count value for {key!r}")
    return checked


def render_report(summary: Mapping[str, object]) -> str:
    """Render a checked summary as text. Counts and code names only."""
    lines: list[str] = []
    for key, value in safe_summary(summary).items():
        if isinstance(value, Mapping):
            lines.append(f"{key}:")
            for name, count in sorted(value.items()):
                lines.append(f"  {count:8d}  {name}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument(
        "--hook",
        type=Path,
        default=Path("plugins/llm-accuracy/hooks/partial-result-sentinel.py"),
        help="hook to measure",
    )
    parser.add_argument(
        "--compare-hook",
        type=Path,
        default=None,
        help="baseline hook to score over the SAME snapshot, for a control",
    )
    parser.add_argument(
        "--transcript-root",
        type=Path,
        action="append",
        default=None,
        help="directory of *.jsonl transcripts (repeatable)",
    )
    parser.add_argument(
        "--exclude-session",
        action="append",
        default=[],
        help="skip results recorded by this session id (repeatable)",
    )
    parser.add_argument(
        "--scope",
        choices=("mcp", "all"),
        default="mcp",
        help="mcp: only results the hook is wired to; all: a wider negative corpus",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    roots = args.transcript_root or [DEFAULT_TRANSCRIPT_ROOT]
    excluded = frozenset(args.exclude_session)

    try:
        payloads = list(
            tool_results(
                transcript_paths(roots, excluded),
                mcp_only=args.scope == "mcp",
                exclude_sessions=excluded,
            )
        )
        candidate = load_hook(args.hook, "candidate_hook")
        summary: dict[str, object] = {"scope": args.scope}
        if args.compare_hook is not None:
            baseline = load_hook(args.compare_hook, "baseline_hook")
            summary.update(compare(payloads, baseline, candidate))
        else:
            observations, counts = score(payloads, candidate)
            summary["results"] = len(payloads)
            summary["firing"] = len({index for index, _ in observations})
            summary["observations"] = len(observations)
            summary["codes"] = counts
        checked = safe_summary(summary)
    except CorpusError as error:
        print(f"error: {error}")
        return 2

    print(json.dumps(checked, indent=2) if args.json else render_report(checked))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
