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
`tool_use_id`, and the assistant turn that issued it names the tool; the two are joined to recover the
name. This matters more than it sounds: built-in tool results outnumber MCP ones
by roughly twenty to one locally, so scoring everything reports a denominator
that is mostly out of scope. `--scope all` is available for a deliberately wider
negative corpus, and labels itself as such. "All" means every record carrying a
top-level `toolUseResult`, including one recorded as null; some built-in results
are recorded only inside `message.content[].content` and are not collected, so
`all` is a wider corpus rather than an exhaustive one.

SAFETY. The corpus is real tool output and may contain anything a tool returned.
The guarantee is precise, and narrower than it first looks:

    THIS SCRIPT never writes a value derived from the CORPUS. Every report it
    prints goes through `safe_summary`, which accepts a fixed set of labels,
    this script's own canonical signal codes, and integers -- nothing else, in
    either the text or the JSON path.

Errors are the one other thing it prints, and they are about the command line
rather than the corpus: a bad `--hook` path is named so the mistake is fixable.
Argument-parsing failures print a fixed message, because argparse would otherwise
echo the offending value back, and someone could paste anything there.

To hold that up, four things the hook hands over are refused rather than trusted:
a code outside the known vocabulary becomes `<unrecognised-code>`; a code that
merely COMPARES equal to a known one is replaced by this script's own literal,
because a `str` subclass can render anything through `__str__`; an exception
becomes `<hook-error>` with its message discarded; and anything the hook prints
to Python's `sys.stdout`/`sys.stderr` during the call is captured and dropped.
The hook's returned object is also released before the capture closes, on every
branch including the one where it raised, so an ordinary finalizer runs inside
it.

What the guarantee does NOT extend to is the HOOK's own behaviour. A hook is
arbitrary imported code running in this process, and no in-process check can
contain it. Three separate escapes were found by review before this was written
down honestly -- an exception from `__iter__`, a `__str__` on a lookalike code,
and a `__del__` finalizer printing after the capture closed -- which is the
evidence for the general claim rather than an argument against a fourth. A hook
can still open a file, open a socket, spawn a thread, write below Python to file
descriptor 1, or defer a finalizer past any capture by holding a reference.

So: measure a hook you would run anyway. If this ever needs to measure a hook
that is not trusted, the fix is isolation, not another check -- run the hook in
a SANDBOXED subprocess with restricted filesystem and network permissions, and
read only its
structured summary. A bare subprocess captures its output but does not stop it
writing a file or opening a socket.

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

`unrecognised` must also be 0 to read `lost`/`gained` at face value. It counts
observations carrying either placeholder: a code outside the known vocabulary, or
a hook that raised. Unknown codes all collapse to the same placeholder, so a swap
between two of them is invisible, and a hook that fails is not measuring
anything. Either way the comparison is not trustworthy until it reads 0 -- fix
the hook, or update this script's vocabulary.

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
from collections.abc import Callable, Iterable, Iterator, Mapping
from pathlib import Path
from typing import NoReturn, Protocol


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
# Canonical instances for everything printable, so the report renders THIS
# script's strings rather than whichever object reached it. `_codes_for` already
# canonicalises what a hook returns; doing it again here means the chokepoint
# holds on its own rather than depending on an earlier stage having run.
CANONICAL_RENDERABLE = {code: str(code) for code in RENDERABLE}
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


SCOPES = ("mcp", "all")
# Canonical instances for every string this script is willing to print, so a
# report renders THIS script's objects rather than whichever ones reached it.
CANONICAL_LABEL = {label: str(label) for label in REPORT_LABELS}
CANONICAL_SCOPE = {scope: str(scope) for scope in SCOPES}


class CorpusError(Exception):
    """A caller error worth reporting without a traceback."""


class Hook(Protocol):
    """What this script needs from a hook: one function, returning codes.

    Deliberately narrower than "a module". A test can substitute a hostile stub
    to attack the safety boundary, which is the only way to prove the boundary
    holds against a hook that is not the shipped one.
    """

    collect_codes: Callable[[object], object]


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
            if TOOL_RESULT_KEY not in record:
                continue
            payload = record[TOOL_RESULT_KEY]
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

    The whole body sits inside the capture, including the `finally` that drops
    the hook's object, so a finalizer runs while output is still redirected --
    on the exception path as well as the ordinary one.
    """
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        found: object = None
        try:
            found = hook.collect_codes(payload)
            if isinstance(found, (set, frozenset, list, tuple)):
                codes = {
                    CANONICAL_CODE.get(code, UNRECOGNISED_CODE)
                    if isinstance(code, str)
                    else UNRECOGNISED_CODE
                    for code in found
                }
            else:
                codes = {UNRECOGNISED_CODE}
        except BaseException:  # noqa: BLE001 - a hook is arbitrary code
            codes = {HOOK_ERROR_CODE}
        finally:
            # Under refcounting this runs the object's `__del__` here, rather
            # than after the redirect closes, which is where a finalizer escaped
            # once. A `__del__` that raises is unraisable and Python reports it
            # on `sys.stderr`, which is still the sink at this point.
            del found
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
    """Return a report built only from this script's own strings and plain ints.

    The single chokepoint. Both the text report and `--json` go through it, so
    neither can become the path that prints something from the corpus.

    Nothing that arrives here is passed through. Labels, scope values and code
    names are all looked up and REPLACED by this script's own instances, and
    counts must be exactly `int`, and both the summary and any nested counts must
    be exact dicts -- a `Mapping` subclass can override `items()` and run its own
    code the moment this function reads it. Checking without replacing is not
    enough either: a
    subclass of `str` or `int` can satisfy every `in` test and every `isinstance`
    and still render anything at all through `__format__`, `__str__` or
    `__repr__`. Refusals name the field, never the value they refused.
    """
    # An exact dict, checked BEFORE anything is read out of it. A `Mapping`
    # subclass can override `items()`, and calling it would run code this script
    # does not own -- inside the function whose whole job is to be the one place
    # nothing unowned gets through.
    if type(summary) is not dict:
        raise CorpusError("refusing to report from a non-dict summary")
    checked: dict[str, object] = {}
    for key, value in summary.items():
        label = CANONICAL_LABEL.get(key) if type(key) is str else None
        if label is None:
            raise CorpusError("refusing to report an unrecognised field")
        if type(value) is dict:
            counts: dict[str, int] = {}
            for name, count in value.items():
                code = CANONICAL_RENDERABLE.get(name) if type(name) is str else None
                if code is None:
                    raise CorpusError(
                        f"refusing to report an unknown code under {label}"
                    )
                if type(count) is not int:
                    raise CorpusError(f"refusing to report a non-count under {label}")
                counts[code] = count
            checked[label] = counts
        elif type(value) is str:
            scope = CANONICAL_SCOPE.get(value)
            if scope is None:
                raise CorpusError(f"refusing to report free text for {label}")
            checked[label] = scope
        elif type(value) is int:
            checked[label] = value
        else:
            raise CorpusError(f"refusing to report an unsupported value for {label}")
    return checked


def render_report(summary: Mapping[str, object]) -> str:
    """Render a checked summary as text: labels, scope, code names and counts.

    Every one of those is a string this script owns or a plain int, because
    `safe_summary` replaced whatever arrived with its own instances first.
    """
    lines: list[str] = []
    for key, value in safe_summary(summary).items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for name, count in sorted(value.items()):
                lines.append(f"  {count:8d}  {name}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


class QuietParser(argparse.ArgumentParser):
    """An argument parser that does not echo the value it rejected.

    argparse's default diagnostic quotes the offending argument, which is a value
    someone could have pasted from anywhere. The mistake is still reported; the
    value is not.
    """

    def error(self, message: str) -> NoReturn:
        del message  # the whole point: the rejected value is not repeated
        self.exit(2, "error: invalid arguments\n")


def build_parser() -> argparse.ArgumentParser:
    parser = QuietParser(description=(__doc__ or "").splitlines()[0])
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
        choices=SCOPES,
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
