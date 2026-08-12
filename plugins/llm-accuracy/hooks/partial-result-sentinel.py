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
    "incompletesearch": PARTIAL_PROVIDER_RESPONSE,
    "truncated": TRUNCATED_RESULT,
    "istruncated": TRUNCATED_RESULT,
    "rowcaphit": ROW_CAP_HIT,
    "partialproviderresponse": PARTIAL_PROVIDER_RESPONSE,
}

# Inside a page-info block, only the flags that describe PAGING count. A
# `pageInfo.truncated` on a document describes how the page was rendered, not a
# result that stopped early.
PAGE_INFO_TRUE_MEANS_PARTIAL = {
    "hasmore": PAGINATION_INCOMPLETE,
    "hasnextpage": PAGINATION_INCOMPLETE,
    "morerecords": PAGINATION_INCOMPLETE,
}

# Envelope keys whose value being exactly False is evidence of partiality.
FALSE_MEANS_PARTIAL = {
    "paginationcomplete": PAGINATION_INCOMPLETE,
}

# Keys whose populated value points at a further page, and whose NAME says so
# on its own. A bare "cursor" is excluded: it usually identifies the page
# already returned.
CURSOR_KEYS = {
    "nextcursor",
    "nextpagetoken",
    "nextpagecursor",
    "nextoffset",
    "nextpageurl",
    "nexttoken",
    "nextmarker",
    "continuationtoken",
    "paginghandle",
    "odatanextlink",
    "nextrecordsurl",
}

# Keys whose NAME suggests pagination but whose bare value is ordinary content:
# a CMS `next_page` holds a title or a slug, an Azure `nextLink` label could be
# a chapter name. They count only when the value has the SHAPE of a page
# reference too -- a link object, or a url or path string.
SHAPE_QUALIFIED_CURSOR_KEYS = {
    "nextlink",
    "nextpage",
}

# Keys that mean "the next page" only inside a pagination container. `next` and
# `after` are ordinary English at the root of a business object -- a meeting
# with an `after` field, a report with a `next` section -- so they count only
# under a container such as `links`, `paging`, or `response_metadata`.
CONTAINED_CURSOR_KEYS = {
    "next",
    "after",
}

# Envelope keys that establish a pagination context for the keys above. Only
# blocks whose own name means pagination qualify. `page`, `meta` and `metadata`
# are deliberately absent: they are generic containers, and a CMS `page.next`
# slug or a workflow's `metadata.next` step is ordinary business content.
PAGINATION_CONTAINER_KEYS = {
    "paging",
    "pagination",
    "cursor",
    "responsemetadata",
    "links",
}

# Keys whose populated value is itself a resume token for the NEXT page, rather
# than a scalar cursor. DynamoDB returns a whole key object; its presence is the
# documented signal that a scan or query stopped early.
RESUME_KEY_KEYS = {
    "lastevaluatedkey",
    "nextstartkey",
}

# Keys that hold a list of link objects, HAL / Atlas style, where a `next`
# relation is the pagination signal. Only the link objects themselves are read;
# this is never applied to record arrays.
LINK_COLLECTION_KEYS = {
    "links",
    "link",
}
MAX_LINKS_SCANNED = 32

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
# traversing it reads business fields as pagination metadata. `pageInfo` is
# absent too, and is owned by the connection pass instead: a Relay page-info
# block declares partiality only through its booleans, so reading the cursor
# vocabulary inside it turned an ordinary `page_info.next` page slug into a
# false signal.
ENVELOPE_KEYS = {
    "result",
    "response",
    "body",
    "page",
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
# A text body larger than this is left unparsed, so a pathological payload
# cannot stall the hook. The bound sits far above anything a host delivers
# intact: measured across 458 real MCP text bodies the largest was 47,620
# characters, because the host replaces anything over its own token budget with
# a truncation notice, which is detected separately. Parsing a 5 MB body costs
# about 45 ms against the 3 s hook timeout, so the headroom is deliberate --
# a lower bound would silently skip inspection of exactly the large results
# most likely to be paginated.
MAX_EMBEDDED_JSON_BYTES = 8_000_000
MAX_CONTENT_BLOCKS = 32
# One node can carry an unbounded number of fields; MAX_ENVELOPES bounds how
# many dictionaries are visited, not how wide any one of them is.
MAX_FIELDS_PER_NODE = 4096
# The host payload itself is bounded before it is parsed. Parsing is linear in
# input size, and a 50 MB payload measured 4.05 s against the 3 s hook timeout,
# so an oversized payload is dropped rather than parsed. stdin is a text
# stream, so this counts decoded characters rather than bytes.
MAX_INPUT_CHARS = 10_000_000

# The host replaces an over-budget MCP result with its own notice and saves the
# real output to a file. That notice is the most explicit partiality evidence
# available -- the model is provably not seeing the full result. The match is
# anchored on the host's structural prefix and both markers must appear within
# the notice head, so business prose that merely discusses token limits -- an
# export runbook, a support reply -- cannot trigger it.
HOST_TRUNCATION_PREFIX = "error: result ("
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


def absolute_url(value: object) -> bool:
    """Report whether a value is an absolute http(s) URL.

    This is what separates a real root-level `next` from an ordinary one.
    Django REST Framework puts an absolute next-page URL at the root of a page
    response, while a business object's `next` holds a title, a slug, or a
    relative path.
    """
    if not isinstance(value, str):
        return False
    candidate = value.strip().lower()
    for scheme in ("http://", "https://"):
        if candidate.startswith(scheme) and len(candidate) > len(scheme):
            return True
    return False


def url_like(value: object) -> bool:
    """Report whether a value has the shape of a link, absolute or rooted."""
    if not isinstance(value, str):
        return False
    candidate = value.strip().lower()
    return candidate.startswith(("http://", "https://", "/"))


def absolute_link(value: object) -> bool:
    """Report whether a value is an absolute url, or an object carrying one."""
    if absolute_url(value):
        return True
    if isinstance(value, dict):
        return any(absolute_url(value.get(f)) for f in ("href", "uri", "url"))
    return False


def collection_present(node: dict) -> bool:
    """Report whether this envelope returned a collection of records.

    Partiality is a statement about a RESULT SET, so an ambiguous page reference
    only means pagination when a returned collection sits beside it. Document
    navigation -- a chapter with a `next` link, or a link map -- carries no
    collection at all, which is what separates it from an API page response.
    Link collections and warning collections are excluded, because they are
    metadata about the response rather than the records it returned.

    A nested envelope inherits this from its ancestors and can also establish it
    itself, so a response wrapped in `result` or `structuredContent` -- where
    the root carries no list at all -- is still recognised.
    """
    for key, value in list(node.items())[:MAX_FIELDS_PER_NODE]:
        if not isinstance(value, list):
            continue
        name = normalize(key)
        if name in LINK_COLLECTION_KEYS or name in WARNING_CONTAINER_KEYS:
            continue
        return True
    return False


def populated_cursor(value: object) -> bool:
    """Report whether a cursor-shaped value points at a further page.

    An object is accepted because several APIs return one instead of a bare
    URL: JSON:API's `next` carries an `href`, Asana's `next_page` carries an
    `offset`, `path`, and `uri`.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, int):
        return value > 0
    if isinstance(value, dict):
        for field in ("href", "uri", "url", "path", "offset"):
            target = value.get(field)
            if isinstance(target, str) and target.strip():
                return True
            if isinstance(target, bool):
                continue
            if isinstance(target, int) and target > 0:
                return True
    return False


def populated_resume_key(value: object) -> bool:
    """Report whether a resume-key value actually carries a resume token."""
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    return False


def link_collection_codes(
    key: str, value: object, *, has_collection: bool = True
) -> set[str]:
    """Read a HAL-style link collection for a `next` relation.

    Scoped to keys that name a link collection, and the `next` relation must
    target an absolute URL. Document navigation carries the same `rel: next`
    with a relative path -- a chapter link -- so the relation alone is not
    enough to tell an API page link from ordinary content.
    """
    if not has_collection:
        return set()
    if normalize(key) not in LINK_COLLECTION_KEYS or not isinstance(value, list):
        return set()
    for entry in value[:MAX_LINKS_SCANNED]:
        if not isinstance(entry, dict):
            continue
        relation = entry.get("rel")
        if not isinstance(relation, str) or relation.strip().lower() != "next":
            continue
        if absolute_url(entry.get("href")):
            return {PAGINATION_INCOMPLETE}
    return set()


def boolean_codes(key: str, value: object) -> set[str]:
    """Return signal codes implied by an unambiguous boolean flag.

    Only booleans whose NAME already states partiality count here. Cursor keys
    are excluded on purpose: a key called `next` or `after` is only pagination
    evidence in an envelope that is known to be a pagination block, and reading
    them anywhere else turns ordinary strings into false signals.
    """
    name = normalize(key)
    codes: set[str] = set()
    if value is True and name in TRUE_MEANS_PARTIAL:
        codes.add(TRUE_MEANS_PARTIAL[name])
    if value is False and name in FALSE_MEANS_PARTIAL:
        codes.add(FALSE_MEANS_PARTIAL[name])
    return codes


def scalar_codes(
    key: str,
    value: object,
    *,
    in_pagination: bool = False,
    has_collection: bool = True,
) -> set[str]:
    """Return signal codes implied by one envelope key/value pair.

    `in_pagination` says whether this key sits inside a pagination container,
    which is what makes an ambiguous name like `next` or `after` readable as a
    cursor rather than as ordinary business vocabulary.
    """
    name = normalize(key)
    codes: set[str] = boolean_codes(key, value)
    if name in CURSOR_KEYS and populated_cursor(value):
        codes.add(PAGINATION_INCOMPLETE)
    if not has_collection:
        # Everything below is an ambiguous page reference, and means pagination
        # only when the envelope actually returned a collection to page through.
        return codes
    if name in SHAPE_QUALIFIED_CURSOR_KEYS and (
        isinstance(value, dict) and populated_cursor(value) or url_like(value)
    ):
        codes.add(PAGINATION_INCOMPLETE)
    if name in CONTAINED_CURSOR_KEYS:
        # Inside a pagination block, any populated value is a cursor. Outside
        # one, only an absolute link is unambiguous enough to act on.
        ambiguous = populated_cursor(value) if in_pagination else absolute_link(value)
        if ambiguous:
            codes.add(PAGINATION_INCOMPLETE)
    return codes


def warning_codes(node: dict) -> set[str]:
    """Read exact warning codes from envelope warning collections only."""
    codes: set[str] = set()
    for key, value in list(node.items())[:MAX_FIELDS_PER_NODE]:
        if normalize(key) not in WARNING_CONTAINER_KEYS:
            continue
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates[:MAX_FIELDS_PER_NODE]:
            if isinstance(candidate, dict):
                candidate = candidate.get("code")
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
    blocks = response.get("content") if isinstance(response, dict) else response
    if isinstance(blocks, list):
        texts: list[str] = []
        for block in blocks[:MAX_CONTENT_BLOCKS]:
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


def page_info_codes(block: dict) -> set[str]:
    """Read paging flags out of a page-info block, and nothing else."""
    codes: set[str] = set()
    for key, value in list(block.items())[:MAX_FIELDS_PER_NODE]:
        name = normalize(key)
        if value is True and name in PAGE_INFO_TRUE_MEANS_PARTIAL:
            codes.add(PAGE_INFO_TRUE_MEANS_PARTIAL[name])
        if value is False and name in FALSE_MEANS_PARTIAL:
            codes.add(FALSE_MEANS_PARTIAL[name])
    return codes


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
        for key, value in list(node.items())[:MAX_FIELDS_PER_NODE]:
            if not isinstance(value, dict):
                continue
            if normalize(key) == "pageinfo":
                codes |= page_info_codes(value)
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
    queue: list[tuple[dict, int, bool, bool]] = [
        (env, 0, False, collection_present(env)) for env in envelopes
    ]
    if not queue:
        return codes
    budget = MAX_ENVELOPES
    while queue:
        node, depth, in_pagination, has_collection = queue.pop(0)
        budget -= 1
        if budget < 0:
            break
        codes |= warning_codes(node)
        fields = list(node.items())[:MAX_FIELDS_PER_NODE]
        # A resume token means "the scan stopped early" only when records were
        # actually returned for it to resume. An empty list is not enough: it is
        # what an exhausted scan looks like, and it is also what an unrelated
        # business field such as `tags: []` looks like.
        returned_rows = any(
            isinstance(value, list)
            and value
            and normalize(key) not in LINK_COLLECTION_KEYS
            and normalize(key) not in WARNING_CONTAINER_KEYS
            for key, value in fields
        )
        for key, value in fields:
            name = normalize(key)
            codes |= scalar_codes(
                key,
                value,
                in_pagination=in_pagination,
                has_collection=has_collection,
            )
            codes |= link_collection_codes(key, value, has_collection=has_collection)
            if returned_rows and name in RESUME_KEY_KEYS and populated_resume_key(value):
                codes.add(PAGINATION_INCOMPLETE)
            if isinstance(value, dict) and name in ENVELOPE_KEYS and depth < MAX_DEPTH:
                queue.append(
                    (
                        value,
                        depth + 1,
                        in_pagination or name in PAGINATION_CONTAINER_KEYS,
                        has_collection or collection_present(value),
                    )
                )
        if depth < MAX_DEPTH:
            for parsed in embedded_envelopes(node):
                queue.append(
                    (parsed, depth + 1, in_pagination, collection_present(parsed))
                )
    return codes


def main() -> int:
    if os.environ.get(BYPASS_ENV):
        return 0
    try:
        raw = sys.stdin.read(MAX_INPUT_CHARS + 1)
        if len(raw) > MAX_INPUT_CHARS:
            return 0
        payload = json.loads(raw or "{}")
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
