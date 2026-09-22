"""Deterministic oracle and mutation checks for the fresh development cases."""
import importlib.util
from pathlib import Path
import sqlite3

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "review_everyday_cases.py"
_SPEC = importlib.util.spec_from_file_location("review_everyday_cases", _PATH)
cases_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cases_module)


def test_case_contract_and_balance():
    cases = cases_module.cases()
    assert len(cases) == 6
    assert len({case["id"] for case in cases}) == 6
    for domain in ("data", "finance", "systems"):
        subset = [case for case in cases if case["domain"] == domain]
        assert len(subset) == 2
        assert any(all(g["status"] != "refuted" for g in case["gold"]) for case in subset)
        assert any(any(g["status"] == "refuted" for g in case["gold"]) for case in subset)
    for case in cases:
        assert case["fixture"]["sources"]
        assert len({g["id"] for g in case["gold"]}) == len(case["gold"])
        for gold in case["gold"]:
            assert gold["status"] in {"supported", "refuted", "unresolved"}
            assert gold["requirement"]
            assert gold["value"] is None or isinstance(gold["value"], str)


def test_order_fanout_and_corrected_query():
    values = cases_module.oracle_values()
    assert (values["preview_count"], values["preview_sales"]) == (3, 370)
    assert values["true_sales"] == 250
    with sqlite3.connect(":memory:") as db:
        db.executescript(cases_module.ORDER_SQL)
        corrected = cases_module.ORDER_QUERY.replace(
            " LEFT JOIN shipments s ON s.order_id=o.id", "")
        assert db.execute(corrected).fetchone() == (3, 250)


def test_cohort_clean_control_and_boundary_mutation():
    values = cases_module.oracle_values()
    assert (values["users"], values["converted"], values["conversion_pct"]) == (4, 2, 50)
    with sqlite3.connect(":memory:") as db:
        db.executescript(cases_module.COHORT_SQL)
        wrong_boundary = cases_module.COHORT_QUERY.replace(
            "p.paid_day < date", "p.paid_day <= date")
        assert db.execute(wrong_boundary).fetchone() == (4, 3)


def test_accrual_correction_preserves_cash_control():
    values = cases_module.oracle_values()
    assert values["revenue"] == 1000
    assert values["deferred"] == 11000
    assert values["profit"] == -3000
    assert values["cash_movement"] == 8000
    # Corrected recognition balances the receipt without changing actual cash.
    assert values["revenue"] + values["deferred"] == 12000
    assert values["profit"] != values["cash_movement"]


def test_treasury_clean_control_and_transfer_mutation():
    values = cases_module.oracle_values()
    assert (values["operating"], values["reserve"]) == (8500, 4000)
    assert values["operating"] + values["reserve"] == 12500
    assert values["external_net"] == 2500
    assert 10000 + values["external_net"] == 12500
    assert 10000 + values["external_net"] - 2000 != 12500


def test_retry_events_and_deduplicated_correction():
    events = cases_module.oracle_values()["submissions"]
    assert [event["accepted_at"] for event in events] == [0, 2, 4]
    assert [event["commits_at"] for event in events] == [3, 5, 7]
    assert len(events) == 3
    assert sum(event["commits_at"] <= 6 for event in events) == 2
    # A gateway enforcing a single accepted request per invoice would commit once.
    accepted = {}
    for event in events:
        accepted.setdefault(event["id"], event)
    assert len(accepted) == 1
    assert next(iter(accepted.values()))["commits_at"] == 3


def test_fencing_clean_control_and_removed_check_mutation():
    assert cases_module.oracle_values()["fenced"] == {"value": "fresh", "accepted": [42]}
    namespace = {}
    exec(cases_module.FENCE_SOURCE.replace(
        'kind == "write" and token == current_token', 'kind == "write"'), namespace)
    assert namespace["apply"](namespace["EVENTS"]) == {
        "value": "stale", "accepted": [42, 41]}


def test_missing_inputs_remain_explicitly_unresolved():
    unresolved = {(case["id"], gold["id"]) for case in cases_module.cases()
                  for gold in case["gold"] if gold["status"] == "unresolved"}
    assert unresolved == {
        ("everyday_sql_cohort", "mobile"),
        ("everyday_finance_reconcile", "global"),
        ("everyday_systems_retry", "monthly"),
        ("everyday_systems_fencing", "durability"),
    }


def test_gold_values_match_numeric_only_extraction_contract():
    from decimal import Decimal

    for case in cases_module.cases():
        for gold in case["gold"]:
            if gold["value"] is not None:
                assert Decimal(gold["value"]).is_finite()
    fencing = next(case for case in cases_module.cases()
                   if case["id"] == "everyday_systems_fencing")
    assert fencing["gold"][0]["value"] is None
