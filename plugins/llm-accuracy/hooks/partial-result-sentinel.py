#!/usr/bin/env python3
"""Advisory hook: flag explicit partial-result evidence in an MCP tool result.

This hook detects *evidence of partiality* only. It runs on one tool result at a
time and keeps no state, so it can never observe that a later page was fetched
and can never certify that coverage is complete. Absence of a signal proves
nothing; only an explicit marker is reported.

The host does not hand this hook the provider's JSON object. Observed live in a
running Claude Code session, ``tool_response`` for an MCP tool arrives either as
a bare LIST of content blocks (``[{"type": "text", "text": "<json>"}]``) or as a
bare STRING. A dict is the MCP wire form and is still accepted. Every shape is
normalised to a list of envelope dictionaries before inspection; an earlier
version rejected anything that was not already a dict, which made the hook a
no-op for every real MCP result.

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
MAX_CONTENT_BLOCKS = 32

# The host replaces an over-budget MCP result with its own notice and saves the
# real output to a file. That notice is the most explicit partiality evidence
# available -- the model is provably not seeing the full result. Both markers
# must appear within the notice head, so prose that merely discusses token
# limits somewhere in a long document cannot trigger it.
HOST_TRUNCATION_PREFIX = "error:"
HOST_TRUNCATION_MARKERS = ("exceeds maximum allowed tokens", "has been saved to")
MAX_TRUNCATION_NOTICE_SCAN = 600

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


def json_envelope(text: str) -> dict | None:
    """Parse one text body that is a JSON envelope object, else return None.

    A top-level JSON array is deliberately rejected: that is record content, and
    walking it would read row fields as pagination metadata.
    """
    stripped = text.strip()
    if not stripped.startswith("{") or len(stripped) > MAX_EMBEDDED_JSON_BYTES:
        return None
    try:
        parsed = json.loads(stripped)
    except (ValueError, RecursionError):
        return None
    return parsed if isinstance(parsed, dict) else None


def content_block_envelopes(blocks: object) -> list[dict]:
    """Parse MCP text content blocks whose body is a JSON envelope."""
    found: list[dict] = []
    if not isinstance(blocks, list):
        return found
    for block in blocks[:MAX_CONTENT_BLOCKS]:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str):
            continue
        parsed = json_envelope(text)
        if parsed is not None:
            found.append(parsed)
    return found


def embedded_envelopes(node: dict) -> list[dict]:
    """Parse MCP text content blocks carried under a dict's ``content`` key."""
    return content_block_envelopes(node.get("content"))


def host_envelopes(response: object) -> list[dict]:
    """Normalise a host ``tool_response`` into the envelopes worth inspecting.

    Live observation of a running Claude Code session: an MCP result is handed
    over as a bare list of content blocks, or as a bare string. The dict form is
    the MCP wire shape and is accepted unchanged.
    """
    if isinstance(response, dict):
        return [response]
    if isinstance(response, list):
        return content_block_envelopes(response)
    if isinstance(response, str):
        parsed = json_envelope(response)
        return [parsed] if parsed is not None else []
    return []


def response_texts(response: object) -> list[str]:
    """Return the top-level text bodies the host delivered, bounded."""
    if isinstance(response, str):
        return [response]
    if isinstance(response, list):
        texts: list[str] = []
        for block in response[:MAX_CONTENT_BLOCKS]:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str):
                texts.append(text)
        return texts
    return []


def host_truncation_codes(response: object) -> set[str]:
    """Detect the host's own over-budget notice standing in for a real result."""
    for text in response_texts(response):
        head = text[:MAX_TRUNCATION_NOTICE_SCAN].strip().lower()
        if head.startswith(HOST_TRUNCATION_PREFIX) and all(
            marker in head for marker in HOST_TRUNCATION_MARKERS
        ):
            return {TRUNCATED_RESULT}
    return set()


def connection_codes(envelope: dict) -> set[str]:
    """Find GraphQL connection page info nested under arbitrary container keys.

    A Relay connection puts its pagination flags in a dict named ``pageInfo``
    that sits under schema-specific containers -- ``data.repository.
    pullRequests.pageInfo`` -- which the envelope-key traversal cannot reach.

    This pass descends through dict values ONLY. Record arrays are never walked,
    so row content still cannot be read as pagination metadata, and signals are
    read only out of the ``pageInfo`` dict itself. Widening the general traversal
    instead is what produced false positives in earlier review rounds.
    """
    codes: set[str] = set()
    queue: list[tuple[dict, int]] = [(envelope, 0)]
    budget = MAX_ENVELOPES
    while queue:
        node, depth = queue.pop(0)
        budget -= 1
        if budget < 0:
            break
        for key, value in node.items():
            if not isinstance(value, dict):
                continue
            if normalize(key) == "pageinfo":
                for inner_key, inner_value in value.items():
                    codes |= scalar_codes(inner_key, inner_value)
            elif depth < MAX_DEPTH:
                queue.append((value, depth + 1))
    return codes


def collect_codes(payload: object) -> set[str]:
    """Return every explicit partial-result code found in a tool result.

    Accepts the shapes a host actually delivers -- a bare content-block list, a
    bare string, or a dict. Only envelope dictionaries are inspected. Record
    arrays are never walked into, so row content cannot be mistaken for
    pagination metadata.
    """
    codes: set[str] = host_truncation_codes(payload)
    envelopes = host_envelopes(payload)
    for envelope in envelopes:
        codes |= connection_codes(envelope)
    queue: list[tuple[dict, int]] = [(envelope, 0) for envelope in envelopes]
    if not queue:
        return codes
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
