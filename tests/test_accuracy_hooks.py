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
        "backwards paging only",
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


PROVIDER_ENVELOPES = [
    (
        {
            "content": [{"type": "text", "text": "1 row"}],
            "structuredContent": {"has_more": True, "rows": [1]},
        },
        "MCP structuredContent",
    ),
    ({"response_metadata": {"next_cursor": "dXNlcjpXMDdRQzA1"}}, "Slack"),
    ({"paging": {"next": {"after": "52"}}}, "HubSpot"),
    ({"links": {"next": "https://api.example.test/records?page=2"}}, "JSON:API"),
    ({"@odata.nextLink": "https://graph.example.test/v1/users?$skip=20"}, "OData"),
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
