"""Recovery cannot select a better completed answer or hide failed attempts."""

import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "paired_probe", Path(__file__).resolve().parents[1] / "scripts/paired_probe.py"
)
paired = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(paired)


def valid(result):
    return result.get("status") == "ok" and result.get("identity", True)


def test_recovery_discards_both_prior_answers_and_alternates_order():
    calls = []

    def probe(arm):
        calls.append(arm)
        status = "timeout" if len(calls) == 1 else "ok"
        return {"status": status, "answers": [str(len(calls))]}

    result = paired.run_pair(probe, valid, max_attempts=3)
    assert calls == ["baseline", "candidate", "candidate", "baseline"]
    assert result["results"]["candidate"]["answers"] == ["3"]
    assert result["results"]["baseline"]["answers"] == ["4"]
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["baseline"]["status"] == "timeout"
    assert result["status"] == "complete"


def test_completed_wrong_answers_are_never_retried():
    calls = []

    def probe(arm):
        calls.append(arm)
        return {"status": "ok", "answers": ["WRONG_PRIVATE_SENTINEL"]}

    result = paired.run_pair(probe, valid, max_attempts=3)
    assert len(calls) == 2
    assert result["status"] == "complete"
    assert "PRIVATE_SENTINEL" not in json.dumps(result["attempts"])


@pytest.mark.parametrize("status", ["ok", "authentication", "rate_limit", "oversized_output", "SECRET_SENTINEL"])
def test_nontransport_failures_do_not_retry(status):
    calls = []

    def probe(arm):
        calls.append(arm)
        return {"status": status, "identity": False}

    result = paired.run_pair(probe, valid, max_attempts=3)
    assert len(calls) == 2
    assert result["status"] == "invalid_result"
    assert "SECRET_SENTINEL" not in json.dumps(result["attempts"])


def test_retry_limit_is_exact_and_default_is_one_pair():
    for maximum in (1, 3):
        calls = []

        def probe(arm):
            calls.append(arm)
            return {"status": "timeout"}

        kwargs = {} if maximum == 1 else {"max_attempts": maximum}
        result = paired.run_pair(probe, valid, **kwargs)
        assert len(calls) == 2 * maximum
        assert result["status"] == "transport_exhausted"
        assert result["results"] == {}
        assert len(result["attempts"]) == maximum


@pytest.mark.parametrize("maximum", [0, 4, True, 1.5])
def test_invalid_budget_never_starts_model(maximum):
    with pytest.raises(ValueError):
        paired.run_pair(lambda _: pytest.fail("must not run"), valid, max_attempts=maximum)


def test_cancellation_propagates_without_retry():
    calls = []

    def probe(arm):
        calls.append(arm)
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        paired.run_pair(probe, valid, max_attempts=3)
    assert calls == ["baseline"]


def test_mixed_failure_stops_and_discards_surviving_answers():
    calls = []

    def probe(arm):
        calls.append(arm)
        return {"status": "timeout" if arm == "baseline" else "ok", "identity": False}

    result = paired.run_pair(probe, valid, max_attempts=3)
    assert result["status"] == "invalid_result"
    assert result["results"] == {}
    assert len(calls) == 2


def test_programming_error_is_not_retried_as_a_host_failure():
    def probe(arm):
        raise RuntimeError("synthetic programming error")

    with pytest.raises(RuntimeError, match="synthetic programming error"):
        paired.run_pair(probe, valid, max_attempts=3)


@pytest.mark.parametrize("receipts", [
    [{"case": "a", "status": "complete"}],
    [{"case": "a", "status": "complete"}, {"case": "b", "status": "transport_exhausted"}],
    [{"case": "a", "status": "complete"}, {"case": "a", "status": "complete"}],
    [],
])
def test_partial_or_duplicate_stage_cannot_be_scored(receipts):
    assert not paired.complete_cases(receipts, ["a", "b"])


def test_all_declared_pairs_are_required():
    assert paired.complete_cases(
        [{"case": "a", "status": "complete"}, {"case": "b", "status": "complete"}],
        ["a", "b"],
    )


@pytest.mark.parametrize("count", [True, 1.5, "PRIVATE_SENTINEL", {}])
def test_receipt_count_rejects_nonintegers(count):
    receipt = paired.attempt_receipt({"baseline": {"status": "ok", "result_count": count}}, {"baseline": True})
    assert receipt["baseline"]["result_count"] == 0
