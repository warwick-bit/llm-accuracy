"""Behaviour checks for the advisory hooks."""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / "plugins" / "llm-accuracy" / "hooks"

ANALYSIS_FIRE_PROMPTS = [
    "Analyze churn by segment this quarter and tell me what's driving it.",
    "Break down revenue by cohort and explain the patterns.",
    "Find which customers have the strongest activation signals in our data.",
]

ANALYSIS_SILENT_PROMPTS = [
    "How many customers churned last week?",
    "Fix the CRM sync endpoint in app/api/crm.py.",
    "Investigate PR #164 for CI failures.",
    "Explore docs/plugin-maintenance.md.",
    "Analyze churn by segment. # analysis-ok",
    "Analyze churn by segment. # Analysis-OK",
]

FUSION_FIRE_PROMPTS = [
    (
        "What is this account's current MRR? Source A says $100, "
        "Source B says $130, and Source C is blank."
    ),
    (
        "How many enterprise leads converted last week? The CRM query returned "
        "HTTP 400 and the data warehouse returned zero rows because a join key "
        "was missing."
    ),
    (
        "Did this account ever pause? Current lifecycle says paying, while "
        "historical events say paused on April 10 and resumed May 1."
    ),
    (
        "Paste the account email and phone from the transcript. Metadata says "
        "identifiers are redacted and the permission row lacks support_pii.read."
    ),
    (
        "Which customers churned because of low usage? The data warehouse query "
        "returned LIMIT 100 capped rows and cancellation reason is null for many rows."
    ),
]

FUSION_SILENT_PROMPTS = [
    "Review this unified diff for bugs. It touches billing retry handling.",
    "Fix the CRM sync endpoint in app/api/crm.py.",
    "Analyze churn by segment this quarter.",
    "Forecast next month's MRR from the current pipeline.",
    "What is this account's current MRR?",
    "What is the current status?",
    "What is this account's current billing-system MRR?",
    "What is the current lifecycle in the CRM?",
    "Should we use Fusion for model benchmarking?",
    (
        "What is this account's current MRR? Source A says $100, "
        "Source B says $130. # fusion-ok"
    ),
    (
        "What is this account's current MRR? Source A says $100, "
        "Source B says $130. # Fusion-OK"
    ),
]


def load_hook(filename: str) -> ModuleType:
    path = HOOKS / filename
    spec = importlib.util.spec_from_file_location(path.stem.replace("-", "_"), path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analysis_hook_precision_battery() -> None:
    hook = load_hook("analysis-contract-injector.py")

    for prompt in ANALYSIS_FIRE_PROMPTS:
        assert hook.should_fire(prompt), prompt
    for prompt in ANALYSIS_SILENT_PROMPTS:
        assert not hook.should_fire(prompt), prompt


def test_analysis_hook_emits_advisory_context(monkeypatch, capsys) -> None:
    hook = load_hook("analysis-contract-injector.py")
    monkeypatch.delenv("CC_SKIP_ANALYSIS", raising=False)
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"prompt": "Analyse customer retention by cohort."})),
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert (
        "analysis contract" in output["hookSpecificOutput"]["additionalContext"].lower()
    )


def test_fusion_hook_precision_battery() -> None:
    hook = load_hook("fusion-evidence-trigger.py")

    for prompt in FUSION_FIRE_PROMPTS:
        assert hook.should_fire(prompt), prompt
    for prompt in FUSION_SILENT_PROMPTS:
        assert not hook.should_fire(prompt), prompt


def test_fusion_hook_emits_advisory_context(monkeypatch, capsys) -> None:
    hook = load_hook("fusion-evidence-trigger.py")
    monkeypatch.delenv("CC_SKIP_FUSION_EVIDENCE", raising=False)
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "prompt": (
                        "The data warehouse is stale and the CRM has missing rows. "
                        "Can you reconcile the conflict?"
                    )
                }
            )
        ),
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert (
        "fusion evidence trigger"
        in output["hookSpecificOutput"]["additionalContext"].lower()
    )


def test_post_compact_hook_emits_freshness_nudge(monkeypatch, capsys) -> None:
    hook = load_hook("post-compact-accuracy.py")
    monkeypatch.setattr(
        hook.sys, "stdin", io.StringIO(json.dumps({"source": "compact"}))
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "re-read exact values" in output["hookSpecificOutput"]["additionalContext"]


def test_post_compact_hook_is_silent_for_non_compact_sources(
    monkeypatch, capsys
) -> None:
    hook = load_hook("post-compact-accuracy.py")
    monkeypatch.setattr(
        hook.sys, "stdin", io.StringIO(json.dumps({"source": "startup"}))
    )

    assert hook.main() == 0
    assert capsys.readouterr().out == ""


SENTINEL_FIRE_CASES = [
    ({"has_more": True, "results": [{"id": 1}]}, "pagination_incomplete"),
    ({"hasNextPage": True}, "pagination_incomplete"),
    ({"pagination_complete": False}, "pagination_incomplete"),
    ({"truncated": True}, "truncated_result"),
    ({"isTruncated": True}, "truncated_result"),
    ({"row_cap_hit": True}, "row_cap_hit"),
    ({"partial_provider_response": True}, "partial_provider_response"),
    ({"source_warnings": ["pagination_incomplete"]}, "pagination_incomplete"),
    ({"source_warnings": ["truncated_result"]}, "truncated_result"),
    ({"page": {"hasMore": True}}, "pagination_incomplete"),
    (
        {"content": [{"type": "text", "text": '{"has_more": true, "data": [1]}'}]},
        "pagination_incomplete",
    ),
]

# Mandatory negatives: shapes that must never produce an advisory.
SENTINEL_SILENT_CASES = [
    {},
    {"results": []},
    {"results": [{"id": 1}, {"id": 2}]},
    {"has_more": False, "results": [{"id": 1}]},
    {"hasNextPage": False},
    {"pagination_complete": True},
    {"truncated": False},
    {"isTruncated": False},
    {"row_cap_hit": False},
    {"partial_provider_response": False},
    {"cursor": "identifies-the-current-page"},
    {"total_count": 2, "rows": [{"id": 1}, {"id": 2}]},
    {"total_count": 0, "rows": []},
    {"total_pages": 9, "rows": [{"id": 1}]},
    {"limit": 100, "rows": [{"id": n} for n in range(100)]},
    {"top_n": 10, "rows": [{"id": n} for n in range(10)]},
    {"sample_size": 50, "rows": [{"id": n} for n in range(50)]},
    {"aggregate": {"sum": 42, "count": 7}},
    {"mrr": 12345, "currency": "AUD"},
    {"rows": [{"id": 1, "note": None}, {"id": 2, "note": None}]},
    {"status": "ok", "warnings": []},
    {"source_warnings": ["stale_source"]},
    {"source_warnings": ["permission_limited"]},
    {"text": "This endpoint supports pagination via has_more and next_cursor."},
    {
        "content": [
            {
                "type": "text",
                "text": "Docs: set has_more to true when another page exists.",
            }
        ]
    },
    {"content": [{"type": "text", "text": '{"has_more": false, "data": [1]}'}]},
    {"content": [{"type": "text", "text": "not json at all {{{"}]},
    {"has_more_info_url": "https://example.test/docs"},
    {"truncated_at": None},
]


def sentinel_advisory(hook: ModuleType, response: object) -> str:
    """Run the sentinel over one tool_response and return its advisory text."""
    codes = hook.collect_codes(response)
    return ", ".join(sorted(codes))


def test_partial_result_sentinel_detects_explicit_signals() -> None:
    hook = load_hook("partial-result-sentinel.py")

    for response, expected_code in SENTINEL_FIRE_CASES:
        codes = hook.collect_codes(response)
        assert expected_code in codes, (response, codes)


RECORD_CONTENT_MUST_NOT_FIRE = [
    {"rows": [{"has_more": True}]},
    {"rows": [{"next_cursor": "a-business-value"}]},
    {"rows": [{"status": "row_cap_hit"}]},
    {"rows": [{"truncated": True}, {"truncated": True}]},
    {"results": [{"pagination_complete": False}]},
    {"items": [{"text": '{"has_more": true}'}]},
    {"records": [{"warnings": ["pagination_incomplete"]}]},
    {"data": [{"is_truncated": True}]},
]


def test_partial_result_sentinel_ignores_record_content() -> None:
    """Row data must never be read as envelope pagination metadata.

    Regression for the fresh audit of PR #18: a database result whose column is
    named `has_more`, or whose cell value is `row_cap_hit`, is ordinary content
    and must not raise a partial-result advisory.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response in RECORD_CONTENT_MUST_NOT_FIRE:
        assert hook.collect_codes(response) == set(), response


def test_partial_result_sentinel_detects_numeric_next_offset() -> None:
    """A populated numeric next-page offset counts; zero and False do not."""
    hook = load_hook("partial-result-sentinel.py")

    assert hook.collect_codes({"next_offset": 100}) == {"pagination_incomplete"}
    assert hook.collect_codes({"next_offset": 0}) == set()
    assert hook.collect_codes({"next_offset": False}) == set()


def test_partial_result_sentinel_bound_is_order_independent() -> None:
    """A signal is found wherever it sits among many real envelope siblings.

    Regression for the fresh audits: the earlier version of this test filled the
    payload with keys that are not envelope keys, so nothing was ever queued and
    the budget was never exercised. These fixtures use real ENVELOPE_KEYS so the
    traversal budget is genuinely under test.
    """
    hook = load_hook("partial-result-sentinel.py")

    def chain(depth: int, leaf: dict) -> dict:
        node = leaf
        for _ in range(depth):
            node = {"result": node}
        return node

    signal_first = {"result": {"has_more": True}, "response": chain(4, {"note": 1})}
    signal_last = {"response": chain(4, {"note": 1}), "result": {"has_more": True}}
    deep_ok = chain(4, {"has_more": True})
    too_deep = chain(40, {"has_more": True})

    assert hook.collect_codes(signal_first) == {"pagination_incomplete"}
    assert hook.collect_codes(signal_last) == {"pagination_incomplete"}
    assert hook.collect_codes(deep_ok) == {"pagination_incomplete"}
    assert hook.collect_codes(too_deep) == set()


def test_partial_result_sentinel_traversal_budget_is_a_real_limit() -> None:
    """Order independence holds within the budget, and not beyond it.

    The third fresh audit showed the claim above is only true while the queue
    stays inside MAX_ENVELOPES. Past that the position of the signal decides
    whether it is seen, so the limit is pinned here rather than left implied.
    This needs a payload with more envelope-keyed siblings than any real result
    carries -- key spellings that all fold onto `result` -- so it bounds a
    pathological input, not a realistic one.
    """
    hook = load_hook("partial-result-sentinel.py")

    spellings = ["result", "RESULT", "_result", "re_sult", "res-ult", "resu_lt"]
    padding = {}
    while len(padding) <= hook.MAX_ENVELOPES:
        for spelling in spellings:
            padding[f"{spelling}{'_' * (len(padding) + 1)}"] = {"note": 1}
            if len(padding) > hook.MAX_ENVELOPES:
                break

    signal = {"result": {"has_more": True}}
    assert hook.collect_codes({**signal, **padding}) == {"pagination_incomplete"}
    assert hook.collect_codes({**padding, **signal}) == set()


def test_partial_result_sentinel_reads_a_bounded_number_of_content_blocks() -> None:
    """Only the first MAX_CONTENT_BLOCKS blocks are read, and that is pinned."""
    hook = load_hook("partial-result-sentinel.py")

    filler = [{"type": "text", "text": "no signal here"}]
    signal = [{"type": "text", "text": '{"rows": [], "has_more": true}'}]

    within = filler * (hook.MAX_CONTENT_BLOCKS - 1) + signal
    beyond = filler * hook.MAX_CONTENT_BLOCKS + signal

    assert hook.collect_codes(within) == {"pagination_incomplete"}
    assert hook.collect_codes(beyond) == set()


def test_partial_result_sentinel_drops_an_oversized_payload_before_parsing(
    monkeypatch, capsys
) -> None:
    """The whole stdin payload is bounded, not just the embedded text.

    Regression for the third fresh audit, which measured 4.05 s on a 50 MB
    payload against a 3 s hook timeout. Parsing is linear in input size, so the
    payload is now dropped unread rather than parsed.
    """
    hook = load_hook("partial-result-sentinel.py")
    monkeypatch.delenv("CC_SKIP_PARTIAL_RESULT", raising=False)

    oversized = (
        '{"tool_response": {"has_more": true, "pad": "'
        + ("x" * hook.MAX_INPUT_CHARS)
        + '"}}'
    )
    assert len(oversized) > hook.MAX_INPUT_CHARS
    monkeypatch.setattr(hook.sys, "stdin", io.StringIO(oversized))

    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_partial_result_sentinel_never_parses_an_oversized_payload(
    monkeypatch, capsys
) -> None:
    """The oversized payload is dropped unread, not parsed and then discarded.

    The third fresh audit noted that asserting silence alone would also pass if
    the payload were parsed first, which is exactly the cost being avoided. This
    fails if `json.loads` is reached at all.
    """
    hook = load_hook("partial-result-sentinel.py")
    monkeypatch.delenv("CC_SKIP_PARTIAL_RESULT", raising=False)

    def explode(*args, **kwargs):
        raise AssertionError("oversized payload reached json.loads")

    monkeypatch.setattr(hook.json, "loads", explode)
    monkeypatch.setattr(
        hook.sys, "stdin", io.StringIO("x" * (hook.MAX_INPUT_CHARS + 1))
    )

    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_partial_result_sentinel_covers_every_declared_cursor_key() -> None:
    """Each declared cursor key fires when populated and stays silent when not.

    Derived from the hook's own key set so a newly declared cursor key cannot
    ship without coverage.
    """
    hook = load_hook("partial-result-sentinel.py")
    assert hook.CURSOR_KEYS

    for key in hook.CURSOR_KEYS:
        assert hook.collect_codes({key: "page-two"}) == {"pagination_incomplete"}, key
        for absent in (None, "", "   ", 0, False):
            assert hook.collect_codes({key: absent}) == set(), (key, absent)


def wrap(body: object) -> list[dict]:
    """Deliver a body the way a host delivers an MCP tool result."""
    text = body if isinstance(body, str) else json.dumps(body)
    return [{"type": "text", "text": text}]


# Negatives modelled on the response SHAPES seen across real MCP servers, kept
# vendor-neutral on purpose: the contract under test is the host's delivery
# shape and generic pagination vocabulary, not any one provider's payload.
REAL_SHAPE_NEGATIVES = [
    # Complete envelopes in every delivered shape.
    wrap({"items": [{"id": 1}], "has_more": False}),
    wrap({"results": [{"id": 1}], "hasNextPage": False, "cursor": "current-page"}),
    wrap({"records": [{"id": 1}], "pagination_complete": True}),
    wrap({"ok": True, "messages": [{"user": "U1"}], "response_metadata": {}}),
    '{"data": [{"id": 1}], "has_more": false}',
    {"status": "ok", "message": "connected", "authUrl": "https://example.test/auth"},
    # Prose and markdown blocks, which many servers return instead of JSON.
    wrap("# Report\n\nAll rows returned. Pagination uses has_more and next_cursor."),
    wrap("No results found."),
    "Query executed successfully. 42 rows.",
    # A top-level JSON array is record content, never an envelope.
    wrap([{"id": 1, "has_more": True}, {"id": 2, "truncated": True}]),
    # GraphQL connections that are exhausted.
    wrap(
        {
            "data": {
                "org": {
                    "repos": {
                        "nodes": [{"id": 1}],
                        "pageInfo": {"hasNextPage": False, "endCursor": "Y3Vyc29yOjE="},
                    }
                }
            }
        }
    ),
    wrap(
        {
            "data": {
                "org": {
                    "repos": {
                        "pageInfo": {"hasNextPage": False, "hasPreviousPage": True}
                    }
                }
            }
        }
    ),
    # Adversarial business payloads: money, aggregates, series, flags, audits.
    wrap({"invoice": {"total": 12500, "currency": "AUD"}, "lines": [{"sku": "a"}]}),
    wrap({"aggregate": {"sum": 98765, "count": 431, "total": 431}}),
    wrap({"series": [{"x": "2026-01", "y": 12}], "total": 12, "limit": 1000}),
    wrap({"flags": [{"key": "has_more", "enabled": True}]}),
    wrap({"feature_flags": {"has_more": {"enabled": True, "rollout": 100}}}),
    wrap({"audit": [{"field": "status", "new_value": "row_cap_hit"}]}),
    wrap({"rows": [{"warning": "truncated_result", "id": 7}]}),
    wrap({"settings": {"truncated": True}, "note": "a saved user preference"}),
    wrap({"columns": ["has_more", "next_cursor"], "rows": [[True, "abc"]]}),
    wrap({"query": "select has_more from flags", "rows": [{"has_more": True}]}),
]


def test_partial_result_sentinel_false_positive_budget() -> None:
    """Zero fires across the mandatory negatives and real-shape negatives.

    Replaces an earlier sweep of 200 generated cases that varied only harmless
    numbers: they were structurally identical, so they proved almost nothing.
    These fixtures instead vary the delivered SHAPE and the adversarial business
    vocabulary that earlier review rounds showed was the real precision risk.
    """
    hook = load_hook("partial-result-sentinel.py")

    battery = SENTINEL_SILENT_CASES + REAL_SHAPE_NEGATIVES
    fired = [case for case in battery if hook.collect_codes(case)]
    assert fired == [], fired


DEEP_CONNECTION_FIRE_CASES = [
    (
        {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [{"number": 1}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "Y3Vyc29yOjE="},
                    }
                }
            }
        },
        "GraphQL connection nested under schema-specific containers",
    ),
    (
        {"result": {"search": {"pageInfo": {"hasNextPage": True}}}},
        "connection under a known envelope key",
    ),
]

DEEP_CONNECTION_SILENT_CASES = [
    (
        {
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [{"number": 1}],
                        "pageInfo": {"hasNextPage": False, "endCursor": "Y3Vyc29yOjE="},
                    }
                }
            }
        },
        "exhausted connection",
    ),
    (
        {
            "data": {
                "repository": {
                    "pullRequests": {
                        "pageInfo": {"hasPreviousPage": True, "startCursor": "abc"}
                    }
                }
            }
        },
        # Deliberate: hasPreviousPage says an EARLIER page exists, which is true
        # of every page after the first in ordinary forward pagination. Firing
        # on it would raise an advisory on each page of a walk the caller is
        # already completing, so only forward partiality is reported.
        "backwards paging is not reported",
    ),
    (
        {"rows": [{"pageInfo": {"hasNextPage": True}}]},
        "pageInfo inside a record array is row content",
    ),
    (
        {"data": {"node": {"has_more": True, "next_cursor": "x"}}},
        "business fields under data are not reachable by the connection pass",
    ),
]


AMBIGUOUS_CURSOR_AT_ROOT_MUST_NOT_FIRE = [
    ({"next": "Quarterly review", "owner": "Ops"}, "report section named next"),
    ({"after": "Lunch", "agenda": "Board meeting"}, "agenda field named after"),
    ({"next": "chapter-two", "title": "Chapter one"}, "document navigation"),
    ({"next": "/accounts/?page=5", "results": []}, "relative path is not enough"),
]

ROOT_URL_CURSOR_MUST_FIRE = [
    (
        {
            "count": 1023,
            "next": "https://api.example.test/accounts/?page=5",
            "previous": None,
            "results": [{"id": 1}],
        },
        "Django REST Framework page response",
    ),
]

AMBIGUOUS_CURSOR_IN_CONTAINER_MUST_FIRE = [
    ({"results": [{"id": 1}], "paging": {"next": {"after": "52"}}}, "HubSpot"),
    (
        {"data": [{"id": "1"}], "links": {"next": "https://api.example.test/x?page=2"}},
        "JSON:API",
    ),
    (
        {
            "data": [{"id": "1"}],
            "links": {
                "self": "a",
                "next": {"href": "https://api.example.test/x?page=2"},
            },
        },
        "JSON:API next as a link object",
    ),
    ({"rows": [{"id": 1}], "cursor": {"after": "abc123"}}, "cursor block"),
]


def test_partial_result_sentinel_reads_bare_next_only_inside_a_container() -> None:
    """`next` and `after` are ordinary English outside a pagination block.

    Regression for a false positive found by the third fresh audit: a business
    object whose root carries `next` or `after` -- an agenda, a report section,
    a document's navigation -- raised a partial-result advisory.

    Inside a pagination container any populated value counts. At the root, where
    real APIs do sometimes put a next-page link, only an ABSOLUTE link counts:
    Django REST Framework returns one there, while business content holds a
    title, a slug, or a relative path. An earlier version of this test claimed
    every real API nests these names inside a container, which DRF disproves.

    Every fixture that must fire also carries a returned collection, because an
    ambiguous page reference only means pagination beside one. That rule is what
    keeps a chapter's absolute `next` link silent, and it is covered separately.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in AMBIGUOUS_CURSOR_AT_ROOT_MUST_NOT_FIRE:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label

    for response, label in AMBIGUOUS_CURSOR_IN_CONTAINER_MUST_FIRE:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label

    for response, label in ROOT_URL_CURSOR_MUST_FIRE:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label
        assert hook.collect_codes(wrap(response)) == {"pagination_incomplete"}, label


def test_partial_result_sentinel_covers_every_contained_cursor_key() -> None:
    """Each contained cursor key fires in a container and stays silent at root.

    Derived from the hook's own key set so a newly declared one cannot ship
    without coverage on both sides of the boundary.
    """
    hook = load_hook("partial-result-sentinel.py")
    assert hook.CONTAINED_CURSOR_KEYS

    for key in hook.CONTAINED_CURSOR_KEYS:
        paged = {"rows": [{"id": 1}], "paging": {key: "page-two"}}
        assert hook.collect_codes(paged) == {"pagination_incomplete"}, key
        assert hook.collect_codes({"rows": [{"id": 1}], key: "page-two"}) == set(), key


NEW_PROVIDER_FIRE_CASES = [
    (
        {"data": [], "next_page_url": "https://api.example.test/v2/x?page=2"},
        "next page url",
    ),
    ({"files": [{"id": "f1"}], "incompleteSearch": True}, "Drive incomplete search"),
    ({"nextToken": "opaque", "items": []}, "AWS next token"),
    ({"entries": [], "limit": 100, "next_marker": "opaque"}, "Box marker paging"),
    (
        {"value": [{"id": 1}], "nextLink": "/api/books?$after=opaque"},
        "Azure next link",
    ),
    (
        {
            "data": [{"gid": "1"}],
            "next_page": {
                "offset": "opaque",
                "path": "/tasks?offset=opaque",
                "uri": "https://app.example.test/api/tasks",
            },
        },
        "Asana next-page object",
    ),
]


def test_partial_result_sentinel_reads_further_provider_declarations() -> None:
    """Three more unambiguous declarations found by the third fresh audit."""
    hook = load_hook("partial-result-sentinel.py")

    for response, label in NEW_PROVIDER_FIRE_CASES:
        assert hook.collect_codes(response), label
        assert hook.collect_codes(wrap(response)), label

    assert hook.collect_codes({"files": [], "incompleteSearch": False}) == set()


AMBIGUOUS_NAMES_MUST_NOT_FIRE = [
    ({"tasks": [{"id": 1}], "done": False}, "Salesforce done, and every task list"),
    ({"questions": [{"q": "a"}], "isLast": False}, "Jira isLast, and every survey"),
    ({"job_id": "j1", "timed_out": True}, "search timed out, and every job record"),
    ({"step": 2, "continue": "user confirmed"}, "Kubernetes continue, and any wizard"),
    ({"title": "Home", "next_page": "About Us"}, "a next_page holding a page title"),
    ({"next_page": 3, "questions": []}, "a next_page holding a page number"),
    ({"nextLink": "Chapter 2"}, "a nextLink holding a label"),
    ({"page": {"next": "about-us"}}, "generic page container holding a slug"),
    ({"metadata": {"next": "review-step-2"}}, "generic metadata holding a step"),
]


def test_partial_result_sentinel_excludes_ambiguous_business_vocabulary() -> None:
    """Names that are ordinary business vocabulary stay out, by decision.

    `done`, `isLast` and `timed_out` really do declare partiality at Salesforce,
    Jira and Elasticsearch, and are still excluded: the same field names sit on
    task lists, survey questions and job records, where an advisory would be
    wrong. Detection relies on the paired unambiguous signal instead --
    `nextRecordsUrl`, `nextPageToken`. Kubernetes' `continue` is excluded on the
    same ground: its value is an opaque string, indistinguishable from a wizard
    step. Generic containers are excluded too, because only a block whose own
    name means pagination can make a bare `next` readable as a cursor.

    Names that merely SUGGEST pagination must also carry the shape of a page
    reference. A `next_page` holding a title, a slug, or a page number, and a
    `nextLink` holding a label, are ordinary content; only a link object or a
    url/path counts.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in AMBIGUOUS_NAMES_MUST_NOT_FIRE:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label


HOST_NOTICE_LOOKALIKES = [
    "Error: the runbook says this export exceeds maximum allowed tokens and "
    "has been saved to the compliance archive.",
    "Error: your upload exceeds maximum allowed tokens; a copy has been saved "
    "to your drive.",
    "Error: upstream 502 from provider",
]


def test_partial_result_sentinel_anchors_the_host_notice_on_its_prefix() -> None:
    """Business prose about token limits is not the host's own notice.

    Regression for the third fresh audit: matching on loose substrings fired on
    ordinary returned prose. The match is anchored on the host's structural
    prefix, which was identical across every real occurrence observed.
    """
    hook = load_hook("partial-result-sentinel.py")

    for text in HOST_NOTICE_LOOKALIKES:
        assert hook.collect_codes(text) == set(), text

    real = (
        "Error: result (94,455 characters across 1 line) exceeds maximum "
        "allowed tokens. Output has been saved to /tmp/tool-results/x.txt."
    )
    assert hook.collect_codes(real) == {"truncated_result"}


DOCUMENT_NAVIGATION_MUST_NOT_FIRE = [
    (
        {"title": "Chapter 1", "next": "https://docs.example.test/chapter-2"},
        "a chapter's absolute next link",
    ),
    (
        {
            "title": "Chapter 1",
            "links": [{"rel": "next", "href": "https://docs.example.test/ch2"}],
        },
        "absolute rel: next navigation",
    ),
    (
        {"title": "Chapter 1", "links": {"next": {"href": "/chapter-2"}}},
        "a link map with no records",
    ),
    (
        {"title": "Chapter 1", "next_page": {"path": "/chapter-2"}},
        "a next-page object that is navigation",
    ),
    (
        {"evaluation": "Q3 review", "last_evaluated_key": {"score": 4}, "tags": []},
        "a resume-key name legitimised only by an empty unrelated list",
    ),
]

PAGINATION_BESIDE_RECORDS_MUST_FIRE = [
    (
        {
            "count": 12,
            "previous": None,
            "results": [{"id": 1}],
            "next": "https://api.example.test/accounts/?page=2",
        },
        "the same absolute next link in a page response",
    ),
    (
        {
            "results": [{"id": 1}],
            "links": [{"rel": "next", "href": "https://api.example.test/x?page=2"}],
        },
        "the same rel: next beside a returned collection",
    ),
    (
        {"items": [{"id": 1}], "next_page": {"offset": 100}},
        "a numeric next-page offset beside records",
    ),
    (
        {"Items": [{"id": 1}], "LastEvaluatedKey": {"pk": {"S": "a"}}},
        "a resume key beside returned rows",
    ),
]


def test_partial_result_sentinel_requires_a_returned_collection() -> None:
    """An ambiguous page reference means pagination only beside a result set.

    Regression for the fourth fresh audit, which showed that absolute-versus-
    relative is not the boundary between an API page link and document
    navigation: a chapter can perfectly well link to the next chapter by
    absolute url. Partiality is a claim about a RESULT SET, so an ambiguous
    reference is read only when the envelope returned a collection. Link
    collections and warning collections do not count as that collection, since
    they describe the response rather than the records in it.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in DOCUMENT_NAVIGATION_MUST_NOT_FIRE:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label

    for response, label in PAGINATION_BESIDE_RECORDS_MUST_FIRE:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label
        assert hook.collect_codes(wrap(response)) == {"pagination_incomplete"}, label


WRAPPED_ENVELOPES_MUST_FIRE = [
    (
        {"result": {"rows": [{"id": 1}], "links": {"next": "https://x.test?p=2"}}},
        "response wrapped in result",
    ),
    (
        {"response": {"data": [{"id": 1}], "paging": {"next": {"after": "52"}}}},
        "response wrapped in response",
    ),
    (
        {"structuredContent": {"rows": [{"id": 1}], "next_page": {"offset": 100}}},
        "response wrapped in structuredContent",
    ),
]


def test_partial_result_sentinel_inherits_the_collection_from_a_wrapper() -> None:
    """A wrapped envelope still counts as having returned a collection.

    The collection gate is what keeps document navigation silent, but computing
    it only at the envelope root silenced every response wrapped in `result`,
    `response`, `body`, or `structuredContent`, where the root carries no list
    at all. A nested envelope now inherits the gate and can establish it itself,
    while navigation nested in the same wrappers stays silent.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in WRAPPED_ENVELOPES_MUST_FIRE:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label
        assert hook.collect_codes(wrap(response)) == {"pagination_incomplete"}, label

    nested_navigation = {"result": {"title": "Ch 1", "links": {"next": {"href": "/ch-2"}}}}
    assert hook.collect_codes(nested_navigation) == set()


COLLECTION_GATE_FIRE_CASES = [
    (
        {
            "Items": [],
            "Count": 0,
            "ScannedCount": 100,
            "LastEvaluatedKey": {"pk": {"S": "next"}},
        },
        "a filtered DynamoDB page returns no items and still must be resumed",
    ),
    (
        {
            "_links": {"next": {"href": "http://localhost/persons?page=1&size=5"}},
            "_embedded": {"persons": [{"id": 1}]},
            "page": {"size": 5, "number": 0},
        },
        "HAL keeps records under _embedded and paging under _links",
    ),
]

COLLECTION_GATE_SILENT_CASES = [
    (
        {
            "title": "Chapter 1",
            "tags": ["reference"],
            "next": "https://docs.example.test/chapter-2",
        },
        "a document with tags is still navigation, not a page response",
    ),
    (
        {"title": "Chapter 1", "tags": [], "next": "https://docs.example.test/ch2"},
        "an empty unrelated list establishes nothing",
    ),
]


def test_partial_result_sentinel_gate_reads_counts_not_just_lists() -> None:
    """An empty page can be real, and an unrelated list proves nothing.

    Two findings from the fourth fresh audit pulled in opposite directions. A
    filtered DynamoDB scan returns an EMPTY `Items` with a resume key and must
    still be reported, so requiring a non-empty list lost real recall. Yet any
    list at all opening the gate let document navigation fire again as soon as
    the document carried tags or authors.

    A record COUNT resolves both: a collection response declares how many
    records it counted even when the page is empty, and a document does not. A
    bare root `next` additionally needs corroborating pagination vocabulary --
    a count or a named previous page -- because it is the most ambiguous signal
    there is. Records nested one level inside a container also count, which is
    how HAL's `_embedded` layout is recognised.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in COLLECTION_GATE_FIRE_CASES:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label
        assert hook.collect_codes(wrap(response)) == {"pagination_incomplete"}, label

    for response, label in COLLECTION_GATE_SILENT_CASES:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label


def test_partial_result_sentinel_reads_object_form_warning_codes() -> None:
    """A warning collection may carry objects, not only bare strings."""
    hook = load_hook("partial-result-sentinel.py")

    assert hook.collect_codes({"source_warnings": [{"code": "row_cap_hit"}]}) == {
        "row_cap_hit"
    }
    assert hook.collect_codes({"warnings": [{"code": "truncated_result"}]}) == {
        "truncated_result"
    }
    assert hook.collect_codes({"warnings": [{"code": "stale_source"}]}) == set()
    assert hook.collect_codes({"warnings": [{"message": "row_cap_hit"}]}) == set()


def test_partial_result_sentinel_requires_a_host_in_an_absolute_url() -> None:
    """A bare scheme is not a next-page link."""
    hook = load_hook("partial-result-sentinel.py")

    page = {"count": 3, "previous": None, "results": [{"id": 1}]}
    assert hook.collect_codes({**page, "next": "https://"}) == set()
    assert hook.collect_codes({**page, "next": "https:///page/2"}) == set()
    assert hook.collect_codes({**page, "next": "https://x.test"}) == {
        "pagination_incomplete"
    }


PAGE_INFO_MUST_NOT_FIRE = [
    (
        {"document": {"pageInfo": {"truncated": True, "title": "Annual report"}}},
        "page display metadata, not a result that stopped early",
    ),
    ({"page_info": {"views": 10, "next": "about-us"}}, "CMS nav slug named next"),
    ({"page_info": {"after": "intro"}}, "ordering field named after"),
    ({"pageInfo": {"title": "Home", "slug": "home"}}, "page metadata block"),
    ({"rows": [{"pageInfo": {"hasNextPage": True}}]}, "page info inside a record"),
]


def test_partial_result_sentinel_reads_only_booleans_from_page_info() -> None:
    """A page-info block declares partiality through booleans, never cursors.

    Regression for a false positive introduced by the connection pass: the
    cursor vocabulary was being applied inside `pageInfo`, so an ordinary
    `page_info.next` page slug raised an advisory. A Relay page-info block never
    signals a further page with `next` or `after`, so reading them there only
    ever produced noise.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in PAGE_INFO_MUST_NOT_FIRE:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label

    assert hook.collect_codes({"pageInfo": {"hasNextPage": True}}) == {
        "pagination_incomplete"
    }


RESUME_AND_LINK_FIRE_CASES = [
    (
        {"Items": [{"id": 1}], "LastEvaluatedKey": {"id": {"S": "a"}}},
        "DynamoDB stopped early and returned a resume key",
    ),
    (
        {
            "done": False,
            "nextRecordsUrl": "/services/data/v59.0/query/01g",
            "records": [],
        },
        "Salesforce next records url",
    ),
    (
        {
            "results": [{"id": 1}],
            "links": [
                {"rel": "self", "href": "https://api.example.test/x?page=1"},
                {"rel": "next", "href": "https://api.example.test/x?page=2"},
            ],
        },
        "HAL link collection with a next relation",
    ),
]

RESUME_AND_LINK_SILENT_CASES = [
    (
        {"Items": [{"id": 1}], "LastEvaluatedKey": {}},
        "empty resume key means exhausted",
    ),
    ({"Items": [{"id": 1}], "LastEvaluatedKey": None}, "absent resume key"),
    ({"links": [{"rel": "self", "href": "https://x.test"}]}, "no next relation"),
    ({"links": [{"rel": "author", "href": "https://x.test"}]}, "business relation"),
    ({"links": [{"rel": "next", "href": ""}]}, "next relation with no target"),
    (
        {"title": "Chapter 1", "links": [{"rel": "next", "href": "/chapter-2"}]},
        "document navigation carries rel: next with a relative path",
    ),
    (
        {"evaluation": "Q3 review", "last_evaluated_key": {"score": 4}},
        "resume-key name with no returned collection beside it",
    ),
    ({"rows": [{"rel": "next", "href": "b"}]}, "record array is not a link collection"),
]


def test_partial_result_sentinel_reads_resume_keys_and_link_relations() -> None:
    """Two provider families declare a further page without a scalar cursor.

    DynamoDB returns a whole key object, and HAL-style APIs put the signal in a
    link collection. Both are read narrowly. A resume key counts only beside a
    returned collection, so a business object carrying the same name stays
    silent. A link entry counts only when its `next` relation targets an
    ABSOLUTE url: document navigation carries the identical `rel: next` with a
    relative path, which disproves the earlier claim that records simply do not
    carry `rel`.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in RESUME_AND_LINK_FIRE_CASES:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label
        assert hook.collect_codes(wrap(response)) == {"pagination_incomplete"}, label

    for response, label in RESUME_AND_LINK_SILENT_CASES:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label


def test_partial_result_sentinel_inspects_large_paginated_results() -> None:
    """A large result must still be inspected -- it is the likeliest to be partial.

    The parse bound was previously low enough that a multi-megabyte paginated
    body was skipped in silence, which is the worst place to lose recall. The
    bound now sits above anything a host delivers intact; oversized results are
    replaced by the host notice and caught by that path instead.
    """
    hook = load_hook("partial-result-sentinel.py")

    rows = [{"id": n, "name": f"row-{n}", "blob": "x" * 200} for n in range(20000)]
    body = json.dumps({"rows": rows, "has_more": True})
    assert len(body) > 4_000_000

    assert hook.collect_codes(wrap(body)) == {"pagination_incomplete"}
    complete = json.dumps({"rows": rows, "has_more": False})
    assert hook.collect_codes(wrap(complete)) == set()


def test_partial_result_sentinel_still_bounds_pathological_input() -> None:
    """The parse bound remains, so an absurd body is skipped rather than parsed."""
    hook = load_hook("partial-result-sentinel.py")

    oversized = (
        '{"has_more": true, "pad": "' + "x" * (hook.MAX_EMBEDDED_JSON_BYTES) + '"}'
    )
    assert len(oversized) > hook.MAX_EMBEDDED_JSON_BYTES
    assert hook.collect_codes(wrap(oversized)) == set()


def test_partial_result_sentinel_detects_deep_graphql_connections() -> None:
    """Relay `pageInfo` is found at depth, without widening general traversal.

    T4 of the hardening plan: the connection pass descends through dict values
    only and reads signals solely from the `pageInfo` dict, so record arrays and
    ordinary nested business fields stay unreachable.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, label in DEEP_CONNECTION_FIRE_CASES:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, label
        assert hook.collect_codes(wrap(response)) == {"pagination_incomplete"}, label

    for response, label in DEEP_CONNECTION_SILENT_CASES:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label


def test_partial_result_sentinel_emits_advisory_without_echoing_output(
    monkeypatch, capsys
) -> None:
    hook = load_hook("partial-result-sentinel.py")
    monkeypatch.delenv("CC_SKIP_PARTIAL_RESULT", raising=False)
    marker = "row-payload-marker-42"
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(
            json.dumps(
                {
                    "hook_event_name": "PostToolUse",
                    "tool_name": "mcp__example__list_rows",
                    "tool_response": {
                        "has_more": True,
                        "rows": [{"email": "person@example.test", "note": marker}],
                    },
                }
            )
        ),
    )

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "pagination_incomplete" in context
    assert marker not in context
    assert "person@example.test" not in context


def test_partial_result_sentinel_is_silent_without_signals(monkeypatch, capsys) -> None:
    hook = load_hook("partial-result-sentinel.py")
    monkeypatch.delenv("CC_SKIP_PARTIAL_RESULT", raising=False)
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_response": {"rows": [{"id": 1}]}})),
    )

    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_partial_result_sentinel_honours_bypass_env(monkeypatch, capsys) -> None:
    hook = load_hook("partial-result-sentinel.py")
    monkeypatch.setenv("CC_SKIP_PARTIAL_RESULT", "1")
    monkeypatch.setattr(
        hook.sys,
        "stdin",
        io.StringIO(json.dumps({"tool_response": {"has_more": True}})),
    )

    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_partial_result_sentinel_survives_hostile_payloads() -> None:
    hook = load_hook("partial-result-sentinel.py")

    deep: dict[str, object] = {"has_more": True}
    for _ in range(500):
        deep = {"nested": deep}

    assert hook.collect_codes(deep) == set()
    assert hook.collect_codes({"tool_response": None}) == set()
    assert sentinel_advisory(hook, []) == ""


# Real provider envelopes always carry the records they are paging through, and
# the fixtures say so: an ambiguous page reference only counts beside a returned
# collection, because document navigation carries a link and no records.
PROVIDER_ENVELOPES = [
    (
        {
            "content": [{"type": "text", "text": "1 row"}],
            "structuredContent": {"has_more": True, "rows": [1]},
        },
        "MCP structuredContent",
    ),
    (
        {
            "messages": [{"ts": "1"}],
            "response_metadata": {"next_cursor": "dXNlcjpXMDdRQzA1"},
        },
        "Slack",
    ),
    ({"results": [{"id": 1}], "paging": {"next": {"after": "52"}}}, "HubSpot"),
    (
        {
            "data": [{"id": "1"}],
            "links": {"next": "https://api.example.test/records?page=2"},
        },
        "JSON:API",
    ),
    (
        {
            "value": [{"id": 1}],
            "@odata.nextLink": "https://graph.example.test/v1/users?$skip=20",
        },
        "OData",
    ),
    ({"pageInfo": {"hasNextPage": True}}, "GraphQL pageInfo at envelope level"),
]


def test_partial_result_sentinel_reads_real_provider_envelopes() -> None:
    """Regression for the second fresh audit: real provider shapes must fire."""
    hook = load_hook("partial-result-sentinel.py")

    for response, provider in PROVIDER_ENVELOPES:
        assert hook.collect_codes(response) == {"pagination_incomplete"}, provider


# The shapes a Claude Code host actually delivers as `tool_response`, observed
# live in a running session against a registered MCP server. The provider's JSON
# object is NOT what arrives.
HOST_DELIVERY_FIRE_CASES = [
    (
        [{"type": "text", "text": '{"issues": [{"id": 1}], "hasNextPage": true}'}],
        "pagination_incomplete",
        "bare content-block list -- the production MCP shape",
    ),
    (
        [
            {"type": "text", "text": "A human-readable preamble."},
            {"type": "text", "text": '{"rows": [{"id": 1}], "has_more": true}'},
        ],
        "pagination_incomplete",
        "signal in a later content block",
    ),
    (
        '{"rows": [{"id": 1}], "next_cursor": "page-two"}',
        "pagination_incomplete",
        "bare JSON string",
    ),
    (
        "Error: result (94,455 characters across 1 line) exceeds maximum allowed "
        "tokens. Output has been saved to /tmp/tool-results/example.txt.",
        "truncated_result",
        "host over-budget notice as a bare string",
    ),
    (
        [
            {
                "type": "text",
                "text": "Error: result (2,000,000 characters) exceeds maximum "
                "allowed tokens. Output has been saved to /tmp/x.txt.",
            }
        ],
        "truncated_result",
        "host over-budget notice inside a content block",
    ),
]

HOST_DELIVERY_SILENT_CASES = [
    ([], "empty content-block list"),
    ("", "empty string"),
    ("Just some prose about has_more and next_cursor.", "bare prose string"),
    (
        [{"type": "text", "text": "no json here, has_more is discussed only"}],
        "prose block",
    ),
    (
        [{"type": "text", "text": '[{"id": 1, "has_more": true}]'}],
        "top-level JSON array is record content",
    ),
    (
        [{"type": "text", "text": '{"rows": [{"id": 1}], "has_more": false}'}],
        "complete provider response",
    ),
    (
        [{"type": "text", "text": '{"rows": [{"has_more": true}]}'}],
        "row column named has_more",
    ),
    (
        "The docs explain that a result which exceeds maximum allowed tokens "
        "has been saved to a file for later reading.",
        "prose mentioning the notice wording but not the host notice",
    ),
    ([{"type": "image", "data": "..."}], "non-text content block"),
    ([None, 42, "loose"], "malformed block list"),
]


def test_partial_result_sentinel_reads_the_shape_the_host_delivers() -> None:
    """Regression: the hook was a no-op for every real MCP result.

    `collect_codes` previously returned immediately unless `tool_response` was a
    dict. Observed live in a running Claude Code session, an MCP result arrives
    as a bare list of content blocks or as a bare string, so the hook never fired
    in production -- 446 real tool results across 13 servers produced zero
    advisories, including payloads carrying `hasNextPage: true`.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, expected_code, label in HOST_DELIVERY_FIRE_CASES:
        assert expected_code in hook.collect_codes(response), label

    for response, label in HOST_DELIVERY_SILENT_CASES:
        assert hook.collect_codes(response) == set(), label


def test_partial_result_sentinel_host_truncation_notice_is_tightly_matched() -> None:
    """The host notice must match on all three markers, not on loose wording."""
    hook = load_hook("partial-result-sentinel.py")

    notice = (
        "Error: result (94,455 characters across 1 line) exceeds maximum allowed "
        "tokens. Output has been saved to /tmp/tool-results/example.txt."
    )
    assert hook.collect_codes(notice) == {"truncated_result"}

    # Each marker removed in turn must silence it.
    assert hook.collect_codes(notice.replace("Error:", "Notice:", 1)) == set()
    assert (
        hook.collect_codes(notice.replace("exceeds maximum allowed", "is under"))
        == set()
    )
    assert (
        hook.collect_codes(notice.replace("has been saved to", "was discarded at"))
        == set()
    )

    # The markers must sit in the notice head, not anywhere in a long document.
    buried = (
        "Error: something failed.\n"
        + ("filler. " * 400)
        + ("exceeds maximum allowed tokens ... has been saved to /tmp/x.txt")
    )
    assert hook.collect_codes(buried) == set()


AMBIGUOUS_TOTALS_MUST_NOT_FIRE = [
    {"total": 500, "currency": "AUD", "items": [{"sku": "a"}, {"sku": "b"}]},
    {"total": 500, "values": [100, 200]},
    {"total_rows": 3, "rows": [1], "values": [10, 20, 30]},
    {"total_count": 3241, "rows": [{"id": 1}, {"id": 2}]},
    {"data": {"id": "feature-1", "has_more": True}},
]


def test_partial_result_sentinel_ignores_ambiguous_totals() -> None:
    """A declared total is never treated as pagination evidence.

    An invoice total, an aggregate, and a chart series are indistinguishable
    from a record count, and associating a total with the right list is not
    solvable generically, so the comparison was removed. A singleton `data`
    record is likewise business content, not envelope metadata.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response in AMBIGUOUS_TOTALS_MUST_NOT_FIRE:
        assert hook.collect_codes(response) == set(), response
