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
    # Pin the membership, not only the behaviour of whatever is in the set: a
    # loop derived from the set cannot notice a key being REMOVED from it.
    assert hook.CURSOR_KEYS == {
        "nextcursor",
        "nextpagetoken",
        "nextpagecursor",
        "nextoffset",
        "nextpageurl",
        "nextpageuri",
        "nexttoken",
        "nextmarker",
        "continuationtoken",
        "paginghandle",
        "odatanextlink",
        "nextrecordsurl",
    }

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


# A connection nested under schema-specific container names is NOT found. Two
# passes tried and both fired on ordinary records; the second failed on a shape
# structurally identical to the GitHub connection below, so no discriminator
# exists. Kept as cases so the gap stays visible rather than becoming folklore.
DEEP_CONNECTION_NOW_EXCLUDED = [
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
        "a connection one unknown container below a known envelope key",
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
        "business fields under data are not reachable by the Relay pass either",
    ),
]


NEW_PROVIDER_FIRE_CASES = [
    (
        {"data": [], "next_page_url": "https://api.example.test/v2/x?page=2"},
        "next page url",
    ),
    ({"files": [{"id": "f1"}], "incompleteSearch": True}, "Drive incomplete search"),
    (
        {"total_count": 123, "incomplete_results": True, "items": [{"id": 1}]},
        "GitHub search exceeded its time limit",
    ),
    ({"nextToken": "opaque", "items": []}, "AWS next token"),
    ({"entries": [], "limit": 100, "next_marker": "opaque"}, "Box marker paging"),
    (
        {"calls": [{"sid": "CA1"}], "next_page_uri": "/2010-04-01/Calls.json?Page=1"},
        "Twilio's next page uri, the same self-describing name as next_page_url",
    ),
]


def test_partial_result_sentinel_reads_further_provider_declarations() -> None:
    """Unambiguous provider declarations found by the third fresh audit."""
    hook = load_hook("partial-result-sentinel.py")

    for response, label in NEW_PROVIDER_FIRE_CASES:
        assert hook.collect_codes(response), label
        assert hook.collect_codes(wrap(response)), label

    assert hook.collect_codes({"files": [], "incompleteSearch": False}) == set()
    assert hook.collect_codes({"items": [], "incomplete_results": False}) == set()


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

    Names that merely SUGGEST pagination are not read at all, whatever shape
    their value takes. An interim rule read them when they carried a url or a
    link object; rounds three to seven showed that a document linking to its
    next chapter carries exactly the same shape, so `next_page` and `nextLink`
    are now excluded outright rather than by shape.
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


PROVIDER_PAGE_MATRIX = [
    ({"object": "list", "results": [{"id": 1}], "has_more": True}, "Notion"),
    ({"data": [{"id": 1}], "meta": {"next_token": "7140"}}, "X/Twitter v2"),
    ({"values": [{"id": 1}], "nextPageToken": "tok"}, "Jira platform"),
    ({"files": [{"id": 1}], "nextPageToken": "tok"}, "Google Drive"),
    (
        {
            "value": [{"id": 1}],
            "@odata.nextLink": "https://graph.example.test/v1/u?$skip=20",
        },
        "Microsoft Graph",
    ),
]

# Documented exclusions: the page reference is real, but its name and shape are
# indistinguishable from ordinary document content, so it is not read. Measured
# across 459 real MCP results, none of these mechanisms ever fired, while each
# of them produced false positives in review.
PROVIDER_PAGE_EXCLUDED = [
    ({"records": [{"id": 1}], "offset": "itrX"}, "Airtable's bare offset"),
    ({"data": {"after": "t3_x", "children": [{"id": 1}]}}, "Reddit's after under data"),
    (
        {"data": [{"id": "1"}], "links": {"next": "https://api.example.test/x?page=2"}},
        "JSON:API links.next, identical to a document's next-chapter link",
    ),
    (
        {"results": [{"id": 1}], "_links": {"next": "/rest/api/content?start=25"}},
        "Confluence _links.next, the same shape",
    ),
    (
        {
            "results": [{"id": 1}],
            "links": [{"rel": "next", "href": "https://cloud.example.test/api?p=2"}],
        },
        "a HAL link collection, which document navigation also uses",
    ),
    (
        {"data": [{"gid": "1"}], "next_page": {"path": "/tasks?offset=opaque"}},
        "Asana's next_page object, which a document's next section also uses",
    ),
    (
        {
            "count": 9,
            "previous": None,
            "results": [{"id": 1}],
            "next": "https://x.test",
        },
        "a Django REST Framework page, whose bare next is ordinary English",
    ),
    (
        {"title": "Q1 chapter 1", "next_page": "https://docs.example.test/q1/ch2"},
        "a url-shaped next_page, which Zendesk and a document both return",
    ),
    (
        {"title": "Q1 chapter 1", "nextLink": "/reports/q1/chapter-2"},
        "a url-shaped nextLink, which Azure and a document both return",
    ),
    (
        {"page": {"title": "Annual report", "truncated": True}},
        "rendering truncation inside a generic page container",
    ),
    (
        {"response_metadata": {"next": "review-step-2"}},
        "a generic metadata bag holding a workflow step",
    ),
    (
        {
            "title": "Quarterly report",
            "next": {"title": "Chapter 2", "truncated": True},
        },
        "a root next object describing the next document",
    ),
    (
        {"Items": [{"id": 1}], "LastEvaluatedKey": {"pk": {"S": "a"}}},
        "a DynamoDB resume key, which a business object can also carry",
    ),
]


def test_partial_result_sentinel_across_real_provider_page_shapes() -> None:
    """A breadth check over documented page responses from many providers.

    The narrow fixtures elsewhere pin individual rules; this one guards against
    a rule change that satisfies its own test while silencing a provider nobody
    happened to write a case for. Every exclusion is deliberate: an ambiguous
    page reference is indistinguishable from ordinary document navigation, and
    `data` is never traversed because it is as often the record as an envelope.
    """
    hook = load_hook("partial-result-sentinel.py")

    for response, provider in PROVIDER_PAGE_MATRIX:
        assert hook.collect_codes(response), provider
        assert hook.collect_codes(wrap(response)), provider

    for response, provider in PROVIDER_PAGE_EXCLUDED:
        assert hook.collect_codes(response) == set(), provider


def test_partial_result_sentinel_reads_only_paging_flags_in_a_generic_block() -> None:
    """A `page` or `metadata` block describes the thing returned, not the result.

    Regression for the sixth fresh audit: `page.truncated` on a document preview
    raised `truncated_result`. Inside a generic container the BOOLEAN vocabulary
    narrows to the paging flags. It does not silence the other mechanisms: a
    self-describing cursor there is still read.
    """
    hook = load_hook("partial-result-sentinel.py")

    assert hook.collect_codes({"page": {"title": "Annual", "truncated": True}}) == set()
    assert hook.collect_codes({"metadata": {"row_cap_hit": True}}) == set()
    assert hook.collect_codes({"page": {"hasMore": True}}) == {"pagination_incomplete"}
    # At the envelope root the same flag IS about the result set.
    assert hook.collect_codes({"rows": [], "truncated": True}) == {"truncated_result"}


def test_partial_result_sentinel_accepts_an_object_valued_cursor() -> None:
    """A self-describing cursor name may wrap its token in an object.

    Regression for the sixth fresh audit. The KEY already states this is the
    next page, so a token wrapped under a token-bearing member counts; an empty
    object does not.
    """
    hook = load_hook("partial-result-sentinel.py")

    items = [{"id": 1}]
    assert hook.collect_codes({"items": items, "next_cursor": {"value": "p2"}}) == {
        "pagination_incomplete"
    }
    assert hook.collect_codes({"items": items, "next_cursor": {}}) == set()
    # Present but tokenless is an exhausted cursor, not a further page.
    assert hook.collect_codes({"items": items, "next_cursor": {"value": None}}) == set()
    assert hook.collect_codes({"items": items, "next_cursor": {"value": ""}}) == set()
    assert hook.collect_codes({"items": items, "next_cursor": {"done": False}}) == set()


def test_partial_result_sentinel_leaves_a_providers_own_content_array_alone() -> None:
    """A `content` array below the wire boundary is a document body, not protocol.

    Regression for the thirteenth fresh audit: every traversed envelope had its
    `content` key reparsed as MCP content blocks, so a CMS article quoting a
    JSON example in one of its blocks raised `pagination_incomplete`. Content
    blocks are read only off `tool_response` itself, and only when the block type
    is `text`; depth cannot tell the two apart, as round fourteen then showed.
    """
    hook = load_hook("partial-result-sentinel.py")

    article = {
        "document": {"id": "doc-1", "title": "Pagination guide"},
        "content": [
            {
                "type": "paragraph",
                "text": '{"has_more": true, "example": "quoted in the article"}',
            }
        ],
    }
    assert hook.collect_codes(wrap(article)) == set()
    # Even when the provider happens to name its block type `text`, it is not
    # the wire form, so it is still the document's content. Regression for the
    # fourteenth audit: an Anthropic Messages response carries exactly this
    # shape at its own root, and a depth test could not tell it apart, because
    # a provider envelope decoded from the host's bare list also starts at 0.
    message = {
        "id": "msg_01Example",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": '{"has_more": true, "eg": "quoted"}'}],
        "stop_reason": "end_turn",
    }
    assert hook.collect_codes(wrap(message)) == set()
    assert hook.collect_codes(json.dumps(message)) == set()
    nested = {"result": {"content": [{"type": "text", "text": '{"has_more": true}'}]}}
    assert hook.collect_codes(wrap(nested)) == set()
    # Provider content carried inside a dict-wire body is still the provider's.
    assert hook.collect_codes({"content": wrap(message)}) == set()
    # The protocol's own blocks at the boundary are still read, in both the dict
    # wire form and the list the host actually delivers.
    wire = {"content": [{"type": "text", "text": '{"rows": [], "has_more": true}'}]}
    assert hook.collect_codes(wire) == {"pagination_incomplete"}
    assert hook.collect_codes(wire["content"]) == {"pagination_incomplete"}
    # A block without the text type is not a text block, whatever it carries.
    untyped = [{"text": '{"rows": [], "has_more": true}'}]
    assert hook.collect_codes(untyped) == set()
    # The host's over-budget notice obeys the same rule. Round fifteen found it
    # read off an image block that merely carried a `text` property.
    notice = (
        "Error: result (94,455 characters across 1 line) exceeds maximum "
        "allowed tokens. Output has been saved to /tmp/tool-results/x.txt."
    )
    image = {"type": "image", "mimeType": "image/png", "data": "AA==", "text": notice}
    assert hook.collect_codes([image]) == set()
    assert hook.collect_codes({"content": [image]}) == set()
    # On a real text block, and as a bare string, the notice still fires.
    assert hook.collect_codes([{"type": "text", "text": notice}]) == {"truncated_result"}
    assert hook.collect_codes(notice) == {"truncated_result"}


def test_partial_result_sentinel_reads_only_token_members_of_a_cursor_object() -> None:
    """A cursor object's unrelated metadata is not a page token.

    Regression for the eighth fresh audit: every populated member counted, so an
    explicitly exhausted cursor fired because it carried a `status` string
    beside its null token. Delivered in the real host shape, which the existing
    object-cursor negatives do not cover.
    """
    hook = load_hook("partial-result-sentinel.py")

    exhausted = {
        "items": [{"id": 1}],
        "next_cursor": {"value": None, "status": "exhausted"},
    }
    assert hook.collect_codes(exhausted) == set()
    assert hook.collect_codes(wrap(exhausted)) == set()
    # A non-token member cannot stand in for the token on its own.
    assert hook.collect_codes(wrap({"next_cursor": {"status": "exhausted"}})) == set()
    assert hook.collect_codes(wrap({"next_cursor": {"expires_in": 0}})) == set()
    # Pin the membership, so a token-bearing member cannot be dropped silently.
    assert hook.CURSOR_OBJECT_TOKEN_FIELDS == {
        "token",
        "value",
        "cursor",
        "after",
        "offset",
        "marker",
        "key",
        "id",
        "href",
        "uri",
        "url",
        "path",
        "next",
        "start",
    }
    # The token itself still fires through every member that can carry one.
    for field in sorted(hook.CURSOR_OBJECT_TOKEN_FIELDS):
        populated = {"items": [{"id": 1}], "next_cursor": {field: "p2", "status": "ok"}}
        assert hook.collect_codes(wrap(populated)) == {"pagination_incomplete"}, field
    # HubSpot's object cursor depends on this path, because `next` was removed
    # from the traversed envelope keys.
    hubspot = {
        "results": [{"id": 1}],
        "paging": {"next": {"after": "52", "link": "/x"}},
    }
    assert hook.collect_codes(wrap(hubspot)) == {"pagination_incomplete"}


def test_partial_result_sentinel_reads_any_pagination_named_container() -> None:
    """A `pagination`-named block is reached; only an enumerated one is trusted.

    Regression for the ninth fresh audit: Alexa returns its token under
    `paginationContext`, which no envelope key reached, so an explicit further
    page went undetected. And for the tenth, which found the first fix went too
    far: granting every `pagination*` name pagination CONTEXT made a
    `paginationLabels` block's button copy read as a cursor. The prefix now
    grants traversal alone, so a self-describing cursor inside any such block is
    found, while a bare `next` or `after` counts only inside one of the
    enumerated PAGINATION_CONTAINER_KEYS.
    """
    hook = load_hook("partial-result-sentinel.py")

    # Pin the membership itself. Iterating the set proves each member behaves,
    # but a member REMOVED from it takes its case away with it, so the loop
    # below would still pass while Twilio's `pagination.next` went silent.
    assert hook.PAGINATION_CONTAINER_KEYS == {
        "paging",
        "pagination",
        "cursor",
        "paginationcontext",
    }
    # Every enumerated container makes a bare `next`/`after` a cursor.
    for container in sorted(hook.PAGINATION_CONTAINER_KEYS):
        enumerated = {"apps": [{"id": "AP1"}], container: {"next": "page-token"}}
        assert hook.collect_codes(wrap(enumerated)) == {"pagination_incomplete"}, (
            container
        )

    alexa = {"paginationContext": {"nextToken": "opaque"}, "results": [{"id": 1}]}
    assert hook.collect_codes(alexa) == {"pagination_incomplete"}
    assert hook.collect_codes(wrap(alexa)) == {"pagination_incomplete"}
    # `paginationContext` is a named pagination block, so a bare `after` counts.
    contained = {"items": [{"id": 1}], "pagination_context": {"after": "52"}}
    assert hook.collect_codes(wrap(contained)) == {"pagination_incomplete"}
    # An unenumerated `pagination`-named block is only TRAVERSED, so a
    # self-describing cursor inside it is found...
    unnamed = {"rows": [{"id": 1}], "paginationDetails": {"next_cursor": "p2"}}
    assert hook.collect_codes(wrap(unnamed)) == {"pagination_incomplete"}
    # ...while a bare `next` inside it stays button copy, not cursor state.
    labels = {"paginationLabels": {"previous": "Back", "next": "Next"}}
    assert hook.collect_codes(labels) == set()
    assert hook.collect_codes(wrap(labels)) == set()
    # The prefix reaches dicts only, so an ordinary scalar is untouched.
    assert hook.collect_codes(wrap({"rows": [], "paginationEnabled": False})) == set()
    # And it does not turn a generic container into a pagination one.
    for container in ("page", "meta", "metadata", "response_metadata"):
        generic = {"items": [{"id": 1}], container: {"next": "review-step-2"}}
        assert hook.collect_codes(wrap(generic)) == set(), container


def test_partial_result_sentinel_reports_a_singular_record_as_a_known_limit() -> None:
    """A bare singular record is indistinguishable from a response envelope.

    Raised by the ninth fresh audit and accepted as a limit rather than fixed:
    PostgREST can return one record as a bare object, so a business column named
    `has_more` fires. The only available tell -- whether a collection sits
    beside the flag -- would silence real envelopes: measured across 8,499 real
    local tool results a root partiality flag appeared 46 times, always beside a
    collection, and this shape appeared zero times. Pinned so a later round
    cannot quietly trade the 46 for the 0.
    """
    hook = load_hook("partial-result-sentinel.py")

    singular = {"id": 1, "name": "Feature preference", "has_more": True}
    assert hook.collect_codes(wrap(singular)) == {"pagination_incomplete"}
    # The shape this limit protects: a real envelope whose collection is nested,
    # so no list sits beside the flag either.
    nested = {"result": {"items": [{"id": 1}]}, "has_more": True}
    assert hook.collect_codes(wrap(nested)) == {"pagination_incomplete"}
    # Inside a collection the same column is still ignored, which is the
    # protection that does hold.
    assert hook.collect_codes(wrap({"rows": [singular]})) == set()


def test_partial_result_sentinel_ignores_rendering_flags_in_response_metadata() -> None:
    """`response_metadata` is generic, so its BOOLEAN vocabulary narrows to paging.

    Regression for the eighth fresh audit: `response_metadata` was removed from
    the pagination containers but never added to the generic ones, so a
    rendering flag inside it still raised `truncated_result`.
    """
    hook = load_hook("partial-result-sentinel.py")

    rendering = {
        "document": {"title": "Annual report"},
        "response_metadata": {"rendering": "preview", "truncated": True},
    }
    assert hook.collect_codes(rendering) == set()
    assert hook.collect_codes(wrap(rendering)) == set()
    # A self-describing cursor in the same block is still read.
    slack = {
        "members": [{"id": "U1"}],
        "response_metadata": {"next_cursor": "dXNlcjo="},
    }
    assert hook.collect_codes(wrap(slack)) == {"pagination_incomplete"}
    # And a paging boolean is still read, because that one is about the result.
    paging_flag = {"items": [{"id": 1}], "response_metadata": {"has_more": True}}
    assert hook.collect_codes(wrap(paging_flag)) == {"pagination_incomplete"}


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

    Regression for a false positive introduced by the Relay pass: the
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


def test_partial_result_sentinel_reads_page_info_only_where_traversal_reaches() -> None:
    """`pageInfo` counts where the envelope traversal already goes, nowhere else.

    Rounds sixteen and eighteen killed two attempts to chase a connection under
    schema-specific containers. The first descended on `pageInfo` alone and
    fired on a keyed map of records. The second required the Relay spec sibling,
    an `edges`/`nodes` list, and fired on a CMS record whose `nodes` are document
    blocks -- a shape structurally identical to a real GitHub connection, so no
    discriminator exists. A same-snapshot control over 9,231 real tool results
    scored the hook with and without the chase and got identical detection sets,
    29 each. The gap is accepted; do not restore it without new evidence. What
    still works is a `pageInfo` directly at the root or directly under a
    recognised key -- not a raw GraphQL `{"data": ...}` body, wrapped or not.
    """
    hook = load_hook("partial-result-sentinel.py")

    # Round sixteen's blocker: a keyed record map.
    keyed = {"pages_by_slug": {"home": {"pageInfo": {"hasNextPage": True}}}}
    # Round eighteen's: the same, holding document blocks under `nodes`.
    cms = {
        "pages_by_slug": {
            "home": {
                "title": "Home",
                "nodes": [{"type": "heading", "text": "Welcome"}],
                "page_info": {"has_next_page": True, "next_label": "About us"},
            }
        }
    }
    for response in (keyed, cms):
        assert hook.collect_codes(response) == set()
        assert hook.collect_codes(wrap(response)) == set()

    # The recall this deliberately gives up, and the already-silent cases.
    for response, label in DEEP_CONNECTION_NOW_EXCLUDED + DEEP_CONNECTION_SILENT_CASES:
        assert hook.collect_codes(response) == set(), label
        assert hook.collect_codes(wrap(response)) == set(), label

    # Where traversal reaches it, a page-info block still declares partiality,
    # so a GraphQL result delivered in an ordinary envelope still works.
    assert hook.collect_codes(wrap({"pageInfo": {"hasNextPage": True}})) == {
        "pagination_incomplete"
    }
    assert hook.collect_codes(wrap({"result": {"pageInfo": {"hasMore": True}}})) == {
        "pagination_incomplete"
    }
    # Being generic narrows its BOOLEAN vocabulary to paging, and its ambiguous
    # page slugs stay unread. A self-describing cursor is still read, as in any
    # block traversal reaches -- generic is not the same as silent.
    assert hook.collect_codes(wrap({"pageInfo": {"truncated": True}})) == set()
    assert hook.collect_codes(wrap({"pageInfo": {"next": "about-us"}})) == set()
    assert hook.collect_codes(wrap({"pageInfo": {"next_cursor": "p2"}})) == {
        "pagination_incomplete"
    }


def test_partial_result_sentinel_pins_the_stored_host_notice_limit() -> None:
    """A stored COPY of the host notice is indistinguishable from a live one.

    Raised by the nineteenth fresh audit and accepted as a limit. A log search,
    a transcript reader or a ticket body that returns the notice verbatim is
    byte-for-byte identical to the host having replaced the result. Weakening
    the match would give up the most explicit and most common real partiality
    evidence there is, so the collision is accepted. Unlike the other two limits
    this one is plain text, not structure.
    """
    hook = load_hook("partial-result-sentinel.py")

    stored = (
        "Error: result (94,455 characters across 1 line) exceeds maximum "
        "allowed tokens. Output has been saved to /tmp/tool-results/x.txt."
    )
    assert hook.collect_codes(stored) == {"truncated_result"}
    assert hook.collect_codes(wrap(stored)) == {"truncated_result"}
    # Prose that merely discusses token limits is not the notice: the match is
    # anchored on the host's structural prefix, so this stays silent.
    discussion = (
        "Our export runbook explains that a result which exceeds maximum "
        "allowed tokens has been saved to a file for later download."
    )
    assert hook.collect_codes(wrap(discussion)) == set()


def test_partial_result_sentinel_pins_the_namespace_collision_limit() -> None:
    """A record keyed with a recognised name IS read as envelope metadata.

    Raised by the seventeenth fresh audit and accepted as a limit, alongside the
    bare singular record: a provider that stores a record under `next_cursor`,
    `paging` or `warnings` puts it exactly where envelope metadata would sit.
    Firebase's user-chosen keys permit it. The heuristics that could guess --
    are the sibling values all dicts, do the keys look like ids -- would silence
    real envelopes; measured across 9,180 real local tool results no keyed map
    collided with a recognised name, while all 26 real detections came from
    genuine envelopes. Pinned so a later round cannot trade the 26 for the 0.
    """
    hook = load_hook("partial-result-sentinel.py")

    collision = {
        "next_cursor": {"id": "customer-17", "name": "Saved cursor preference"},
        "customer-18": {"id": "customer-18", "name": "Ordinary customer"},
    }
    assert hook.collect_codes(wrap(collision)) == {"pagination_incomplete"}
    # A keyed map whose keys are ordinary ids is unaffected, which is the case
    # that actually occurs: zero collisions in the measured corpus.
    ordinary = {
        "customer-17": {"id": "customer-17", "has_more": True},
        "customer-18": {"id": "customer-18", "name": "Ordinary customer"},
    }
    assert hook.collect_codes(wrap(ordinary)) == set()


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

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
    assert "pagination_incomplete" in context

    # Checked against the COMPLETE streams, not only the advisory field: an
    # earlier version searched `additionalContext` alone, which would have
    # missed a leak printed anywhere else.
    for stream in (captured.out, captured.err):
        assert marker not in stream
        assert "person@example.test" not in stream


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


# Real provider envelopes carry the records they are paging through, and the
# fixtures say so. The collection is not a gate -- a flag or a self-describing
# cursor counts on its own -- it is here because that is the shape a real
# response has, so these cases stay honest about what production delivers.
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
    ({"rows": [{"id": 1}], "cursor": {"after": "abc"}}, "a cursor block"),
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
