#!/usr/bin/env python3
"""Advisory hook: flag explicit partial-result evidence in an MCP tool result.

This hook detects *evidence of partiality* only. It runs on one tool result at a
time and keeps no state, so it can never observe that a later page was fetched
and can never certify that coverage is complete. Absence of a signal proves
nothing; only an explicit marker is reported.

It reads structured markers, never free text, and emits fixed signal codes. Tool
output is inspected in memory and is never echoed or persisted.
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

# Keys whose value being exactly True is explicit evidence of partiality.
TRUE_MEANS_PARTIAL = {
    "hasmore": PAGINATION_INCOMPLETE,
    "hasnextpage": PAGINATION_INCOMPLETE,
    "morerecords": PAGINATION_INCOMPLETE,
    "truncated": TRUNCATED_RESULT,
    "istruncated": TRUNCATED_RESULT,
    "rowcaphit": ROW_CAP_HIT,
    "partialproviderresponse": PARTIAL_PROVIDER_RESPONSE,
}

# Keys whose value being exactly False is explicit evidence of partiality.
FALSE_MEANS_PARTIAL = {
    "paginationcomplete": PAGINATION_INCOMPLETE,
}

# Keys whose non-empty string value is explicit evidence of a further page.
# A bare "cursor" is excluded: it usually identifies the current page.
CURSOR_KEYS = {
    "nextcursor",
    "nextpagetoken",
    "nextpagecursor",
    "nextoffset",
    "continuationtoken",
    "paginghandle",
}

# Exact machine warning codes, matched only as whole list/string values.
WARNING_CODES = {
    PAGINATION_INCOMPLETE: PAGINATION_INCOMPLETE,
    TRUNCATED_RESULT: TRUNCATED_RESULT,
    ROW_CAP_HIT: ROW_CAP_HIT,
    PARTIAL_PROVIDER_RESPONSE: PARTIAL_PROVIDER_RESPONSE,
}

# Authoritative record totals. Page/offset totals are deliberately excluded.
TOTAL_KEYS = {
    "total",
    "totalcount",
    "totalresults",
    "totalrows",
    "totalitems",
    "totalrecords",
}

# Traversal bounds keep a pathological payload from stalling the hook.
MAX_DEPTH = 8
MAX_NODES = 20000
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
    """Fold snake_case, camelCase, and kebab-case spellings onto one form."""
    return key.replace("_", "").replace("-", "").lower()


def scalar_codes(key: str, value: object) -> set[str]:
    """Return signal codes implied by one key/value pair."""
    name = normalize(key)
    codes: set[str] = set()
    if value is True and name in TRUE_MEANS_PARTIAL:
        codes.add(TRUE_MEANS_PARTIAL[name])
    if value is False and name in FALSE_MEANS_PARTIAL:
        codes.add(FALSE_MEANS_PARTIAL[name])
    if name in CURSOR_KEYS and isinstance(value, str) and value.strip():
        codes.add(PAGINATION_INCOMPLETE)
    if isinstance(value, str) and value.strip().lower() in WARNING_CODES:
        codes.add(WARNING_CODES[value.strip().lower()])
    return codes


def total_mismatch_codes(node: dict) -> set[str]:
    """Flag a declared record total that exceeds the rows present beside it."""
    totals = [
        value
        for key, value in node.items()
        if normalize(key) in TOTAL_KEYS
        and isinstance(value, int)
        and not isinstance(value, bool)
    ]
    if not totals:
        return set()
    longest = max(
        (len(value) for value in node.values() if isinstance(value, list)),
        default=None,
    )
    if longest is None or longest == 0:
        return set()
    return {PAGINATION_INCOMPLETE} if max(totals) > longest else set()


def embedded_payloads(node: dict) -> list[object]:
    """Parse MCP text content blocks that carry a JSON body."""
    text = node.get("text")
    if not isinstance(text, str):
        return []
    stripped = text.strip()
    if not stripped.startswith(("{", "[")):
        return []
    if len(stripped) > MAX_EMBEDDED_JSON_BYTES:
        return []
    try:
        return [json.loads(stripped)]
    except (ValueError, RecursionError):
        return []


def collect_codes(payload: object) -> set[str]:
    """Walk a tool result and return every explicit partial-result code found."""
    codes: set[str] = set()
    stack: list[tuple[object, int]] = [(payload, 0)]
    seen = 0
    while stack:
        node, depth = stack.pop()
        seen += 1
        if seen > MAX_NODES or depth > MAX_DEPTH:
            continue
        if isinstance(node, dict):
            codes |= total_mismatch_codes(node)
            for key, value in node.items():
                codes |= scalar_codes(key, value)
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
            for parsed in embedded_payloads(node):
                stack.append((parsed, depth + 1))
        elif isinstance(node, list):
            for value in node:
                if isinstance(value, str) and value.strip().lower() in WARNING_CODES:
                    codes.add(WARNING_CODES[value.strip().lower()])
                elif isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
    return codes


def main() -> int:
    if os.environ.get(BYPASS_ENV):
        return 0
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        if not isinstance(payload, dict):
            return 0
        response = payload.get("tool_response")
        if not isinstance(response, (dict, list)):
            return 0
        codes = collect_codes(response)
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
