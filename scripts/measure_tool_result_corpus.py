#!/usr/bin/env python3
"""Score a hook against a corpus of real tool results, and report counts only.

The partial-result sentinel makes two kinds of mistake: it can miss a genuinely
partial result, or it can fire on ordinary business data. Argument alone cannot
settle which mechanisms are worth their precision cost, because both failures are
invisible in a fixture suite that was written by the same person as the rule. So
this measures instead: it replays a corpus of REAL tool results, captured from
local host transcripts, through the hook and reports how often each signal fires.

Every mechanism removed from the sentinel during review was removed on evidence
produced this way -- it fired zero times across thousands of real results while
causing reproduced false positives.

SAFETY. The corpus is real tool output and may contain anything a tool returned.
This script therefore emits COUNTS and normalised KEY NAMES only. Payload values
never leave the process: no record content, no prose, no identifiers, no field
values. `render_report` is the only formatting path and is covered by a test that
asserts payload values cannot reach it.

TWO MODES.

Absolute, "how often does this fire":

    python3 scripts/measure_tool_result_corpus.py \\
        --hook plugins/llm-accuracy/hooks/partial-result-sentinel.py

Same-snapshot control, "what did this change cost", which is the one that
matters. A raw count compared against a count taken earlier is NOT a control: the
corpus grows while you work, because every session appends to it, so an unchanged
hook can appear to gain detections. Score both versions over ONE snapshot:

    git show <old-sha>:plugins/llm-accuracy/hooks/partial-result-sentinel.py \\
        > /tmp/old-sentinel.py
    python3 scripts/measure_tool_result_corpus.py \\
        --hook plugins/llm-accuracy/hooks/partial-result-sentinel.py \\
        --compare-hook /tmp/old-sentinel.py

`lost` is what the change stopped detecting. For a precision fix that claims to
cost nothing, `lost` must be 0.

SELF-CONTAMINATION. A session that works ON the sentinel writes its own test
payloads into its own transcript, which then enters the corpus. Exclude the
sessions doing the work before drawing a conclusion:

    --exclude-session <session-id> [--exclude-session <session-id> ...]
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import ModuleType


DEFAULT_TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"

# A transcript line records a tool result under this key. Anything else on the
# line is conversation, which this script never reads.
TOOL_RESULT_KEY = "toolUseResult"


def load_hook(path: Path, name: str = "sentinel_under_measurement") -> ModuleType:
    """Import a hook module from a file path, without installing it."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"not an importable module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transcript_paths(
    roots: list[Path], exclude_sessions: frozenset[str] = frozenset()
) -> Iterator[Path]:
    """Yield transcript files, skipping any whose name names an excluded session."""
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.jsonl")):
            if any(session and session in path.name for session in exclude_sessions):
                continue
            yield path


def tool_results(paths: Iterator[Path]) -> Iterator[object]:
    """Yield each tool result payload found in the given transcripts.

    Unreadable files and unparseable lines are skipped rather than raised: a
    corpus is a pile of other sessions' logs, and one truncated line mid-write
    should not abort a measurement over thousands of results.
    """
    for path in paths:
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            payload = record.get(TOOL_RESULT_KEY)
            if payload is not None:
                yield payload


def score(payloads: list[object], hook: ModuleType) -> tuple[list[int], dict[str, int]]:
    """Return the indices of firing payloads, and a count per signal code.

    Indices rather than payloads: the caller needs to compare two scorings of the
    same snapshot, and an index says which result differed without carrying the
    result itself.
    """
    firing: list[int] = []
    codes: collections.Counter[str] = collections.Counter()
    for index, payload in enumerate(payloads):
        found = hook.collect_codes(payload)
        if found:
            firing.append(index)
            codes[",".join(sorted(found))] += 1
    return firing, dict(codes)


def compare(
    payloads: list[object], baseline: ModuleType, candidate: ModuleType
) -> dict[str, int]:
    """Score one snapshot with two hook versions and report the difference.

    This is the control that a raw count cannot give. `lost` is the number of
    results the baseline detected and the candidate does not; `gained` is the
    reverse. A precision fix claiming to cost no recall must show `lost` of 0.
    """
    before, _ = score(payloads, baseline)
    after, _ = score(payloads, candidate)
    return {
        "results": len(payloads),
        "baseline_firing": len(before),
        "candidate_firing": len(after),
        "lost": len(set(before) - set(after)),
        "gained": len(set(after) - set(before)),
    }


def render_report(summary: Mapping[str, object]) -> str:
    """Render a summary as text. Counts and code names only, by construction.

    Every value written here is an int or a signal-code string produced by the
    hook's own closed vocabulary. No payload-derived value reaches this function,
    which is what keeps a corpus of real tool output safe to measure.
    """
    lines: list[str] = []
    for key, value in summary.items():
        if isinstance(value, Mapping):
            lines.append(f"{key}:")
            for name, count in sorted(value.items()):
                lines.append(f"  {count:8d}  {str(name)}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        else:  # pragma: no cover - only ints and code counts are ever summarised
            raise TypeError(f"refusing to render a non-count value for {key!r}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
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
        help="skip transcripts naming this session id (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args(argv)

    roots = args.transcript_root or [DEFAULT_TRANSCRIPT_ROOT]
    paths = transcript_paths(roots, frozenset(args.exclude_session))
    payloads = list(tool_results(paths))

    candidate = load_hook(args.hook, "candidate_hook")
    summary: dict[str, object] = {}
    if args.compare_hook is not None:
        baseline = load_hook(args.compare_hook, "baseline_hook")
        summary.update(compare(payloads, baseline, candidate))
    else:
        firing, codes = score(payloads, candidate)
        summary["results"] = len(payloads)
        summary["firing"] = len(firing)
        summary["codes"] = codes

    print(json.dumps(summary, indent=2) if args.json else render_report(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
