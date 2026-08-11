#!/usr/bin/env python3
"""Advisory hook: flag explicit partial-result evidence in an MCP tool result.

This hook detects *evidence of partiality* only. It runs on one tool result at a
time and keeps no state, so it can never observe that a later page was fetched
and can never certify that coverage is complete. Absence of a signal proves
nothing; only an explicit marker is reported.

Detection is scoped to the response ENVELOPE. Record contents are never
inspected, because a row may legitimately hold a column called ``has_more`` or a
cell whose value is ``row_cap_hit``; treating row data as pagination metadata
would fire on ordinary database results. Only envelope dictionaries are read;
record arrays are never walked into.

Declared record totals are deliberately NOT compared against returned rows. A
bare total is ambiguous -- an invoice total, an aggregate, or a chart series all
look identical to a record count -- and associating a total with the right list
is not solvable generically. That comparison produced false positives in review
and was removed rather than special-cased.

Tool output is inspected in memory and is never echoed or persisted.
"""

from __future__ import annotations

import json
import os
import sys


# Signal codes shared with the evidence vocabulary in the reference doc.
PAGINATION_INCOMPLETE = "pagination_incomplete"
TRUNCATED_RESULT = "truncated_result"
ROW_CAP_HIT = "row_cap_hit"
PARTIAL_PROVIDER_RESPONSE = "partial_provider_response"

# Envelope keys whose value being exactly True is evidence of partiality.
TRUE_MEANS_PARTIAL = {
    "hasmore": PAGINATION_INCOMPLETE,
    "hasnextpage": PAGINATION_INCOMPLETE,
    "morerecords": PAGINATION_INCOMPLETE,
    "truncated": TRUNCATED_RESULT,
    "istruncated": TRUNCATED_RESULT,
    "rowcaphit": ROW_CAP_HIT,
    "partialproviderresponse": PARTIAL_PROVIDER_RESPONSE,
}

# Envelope keys whose value being exactly False is evidence of partiality.
FALSE_MEANS_PARTIAL = {
    "paginationcomplete": PAGINATION_INCOMPLETE,
}

# Envelope keys whose populated value points at a further page. A bare "cursor"
# is excluded: it usually identifies the page already returned.
CURSOR_KEYS = {
    "nextcursor",
    "nextpagetoken",
    "nextpagecursor",
    "nextoffset",
    "continuationtoken",
    "paginghandle",
    "odatanextlink",
    "next",
    "after",
}

# Exact machine warning codes, read only from envelope warning collections.
WARNING_CODES = {
    PAGINATION_INCOMPLETE: PAGINATION_INCOMPLETE,
    TRUNCATED_RESULT: TRUNCATED_RESULT,
    ROW_CAP_HIT: ROW_CAP_HIT,
    PARTIAL_PROVIDER_RESPONSE: PARTIAL_PROVIDER_RESPONSE,
}
WARNING_CONTAINER_KEYS = {
    "warnings",
    "sourcewarnings",
    "notices",
    "datawarnings",
    "resultwarnings",
}

# Dict-valued keys that carry more envelope, rather than record content.
# `data` is deliberately absent: it is just as often the returned record, and
# traversing it reads business fields as pagination metadata.
ENVELOPE_KEYS = {
    "result",
    "response",
    "body",
    "page",
    "pageinfo",
    "paging",
    "pagination",
    "meta",
    "metadata",
    "cursor",
    "structuredcontent",
    "responsemetadata",
    "links",
    "next",
}

# Traversal bounds keep a pathological payload from stalling the hook.
MAX_DEPTH = 6
MAX_ENVELOPES = 256
MAX_EMBEDDED_JSON_BYTES = 1_000_000

BYPASS_ENV = "CC_SKIP_PARTIAL_RESULT"

ADVICE = (
    "PARTIAL RESULT SIGNAL: {codes}. This tool result carries explicit evidence that it does "
    "not cover the full set. Continue paginating until the source is exhausted, or report the "
    "answer as partial and name what you actually read (rows seen, pages fetched, cursor state). "
    "Do not present this page as the complete set, and do not infer completeness from the "
    "absence of a further warning: this check only detects declared partiality, it cannot "
    "confirm coverage. Mute with `{env}=1`."
)


def normalize(key: str) -> str:
    """Fold snake_case, camelCase, kebab-case, and OData spellings onto one form.

    `@` and `.` are stripped so an OData annotation such as `@odata.nextLink`
    folds onto the same form as its plainer spellings.
    """
    for character in ("_", "-", "@", "."):
        key = key.replace(character, "")
    return key.lower()


def populated_cursor(value: object) -> bool:
    """Report whether a cursor-shaped value points at a further page."""
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, int):
        return value > 0
    return False


def scalar_codes(key: str, value: object) -> set[str]:
    """Return signal codes implied by one envelope key/value pair."""
    name = normalize(key)
    codes: set[str] = set()
    if value is True and name in TRUE_MEANS_PARTIAL:
        codes.add(TRUE_MEANS_PARTIAL[name])
    if value is False and name in FALSE_MEANS_PARTIAL:
        codes.add(FALSE_MEANS_PARTIAL[name])
    if name in CURSOR_KEYS and populated_cursor(value):
        codes.add(PAGINATION_INCOMPLETE)
    return codes


def warning_codes(node: dict) -> set[str]:
    """Read exact warning codes from envelope warning collections only."""
    codes: set[str] = set()
    for key, value in node.items():
        if normalize(key) not in WARNING_CONTAINER_KEYS:
            continue
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, str):
                code = WARNING_CODES.get(candidate.strip().lower())
                if code:
                    codes.add(code)
    return codes


def embedded_envelopes(node: dict) -> list[dict]:
    """Parse MCP text content blocks whose body is a JSON envelope."""
    found: list[dict] = []
    content = node.get("content")
    blocks = content if isinstance(content, list) else []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str):
            continue
        stripped = text.strip()
        if not stripped.startswith("{") or len(stripped) > MAX_EMBEDDED_JSON_BYTES:
            continue
        try:
            parsed = json.loads(stripped)
        except (ValueError, RecursionError):
            continue
        if isinstance(parsed, dict):
            found.append(parsed)
    return found


def collect_codes(payload: object) -> set[str]:
    """Return every explicit partial-result code found in a result envelope.

    Only envelope dictionaries are inspected. Record arrays are never walked
    into, so row content cannot be mistaken for pagination metadata.
    """
    if not isinstance(payload, dict):
        return set()

    codes: set[str] = set()
    queue: list[tuple[dict, int]] = [(payload, 0)]
    budget = MAX_ENVELOPES
    while queue:
        node, depth = queue.pop(0)
        budget -= 1
        if budget < 0:
            break
        codes |= warning_codes(node)
        for key, value in node.items():
            codes |= scalar_codes(key, value)
            if (
                isinstance(value, dict)
                and normalize(key) in ENVELOPE_KEYS
                and depth < MAX_DEPTH
            ):
                queue.append((value, depth + 1))
        if depth < MAX_DEPTH:
            for parsed in embedded_envelopes(node):
                queue.append((parsed, depth + 1))
    return codes


def main() -> int:
    if os.environ.get(BYPASS_ENV):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        codes = collect_codes(payload.get("tool_response"))
        if not codes:
            return 0
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": ADVICE.format(
                            codes=", ".join(sorted(codes)), env=BYPASS_ENV
                        ),
                    }
                }
            )
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
