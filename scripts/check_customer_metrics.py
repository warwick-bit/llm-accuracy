#!/usr/bin/env python3
"""Executable checks for one public SQL example and authored synthetic fixtures.

This is an example-specific checker, not a general SQL correctness certificate.
"""

from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sqlite3

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/customer-metrics-review"
FIELDS = ("customer_id", "first_name", "last_name", "first_order", "most_recent_order",
          "number_of_orders", "customer_lifetime_value")


def validate_fixture(fixture: dict) -> None:
    """Reject source key/relationship problems before trusting the oracle."""
    for name, key in (("customers", "customer_id"), ("orders", "order_id"), ("payments", "payment_id")):
        ids = [r[key] for r in fixture[name]]
        if any(type(i) is not int for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("source_keys")
    customers = {r["customer_id"] for r in fixture["customers"]}
    orders = {r["order_id"] for r in fixture["orders"]}
    if any(r["customer_id"] not in customers for r in fixture["orders"]):
        raise ValueError("order_customer_relationship")
    if any(r["order_id"] not in orders for r in fixture["payments"]):
        raise ValueError("payment_order_relationship")
    if any(type(r["amount"]) is not int or r["amount"] <= 0 for r in fixture["payments"]):
        raise ValueError("example_requires_positive_whole_aud")


def expected_rows(fixture: dict) -> list[dict]:
    """Independent Python grouping over source entities, never candidate output."""
    validate_fixture(fixture)
    result = []
    for customer in fixture["customers"]:
        orders = [o for o in fixture["orders"] if o["customer_id"] == customer["customer_id"]]
        ids = {o["order_id"] for o in orders}
        amounts = [p["amount"] for p in fixture["payments"] if p["order_id"] in ids]
        dates = [o["order_date"] for o in orders]
        result.append({**customer, "first_order": min(dates) if dates else None,
                       "most_recent_order": max(dates) if dates else None,
                       "number_of_orders": len(ids) if ids else None,
                       "customer_lifetime_value": sum(amounts) if amounts else None})
    return sorted(result, key=lambda r: r["customer_id"])


def render(sql: str) -> str:
    """Render only the three audited refs; no template/code execution."""
    for name in ("customers", "orders", "payments"):
        sql = sql.replace("{{ ref('stg_" + name + "') }}", "stg_" + name)
    if "{{" in sql or "{%" in sql:
        raise ValueError("unsupported_template")
    return sql


def execute(sql: str, fixture: dict) -> list[dict]:
    validate_fixture(fixture)
    connection = sqlite3.connect(":memory:")
    try:
        connection.row_factory = sqlite3.Row
        connection.executescript(
            "CREATE TABLE stg_customers(customer_id INTEGER, first_name TEXT, last_name TEXT);"
            "CREATE TABLE stg_orders(order_id INTEGER, customer_id INTEGER, order_date TEXT);"
            "CREATE TABLE stg_payments(payment_id INTEGER, order_id INTEGER, amount INTEGER);"
        )
        for name, fields in (("customers", ("customer_id", "first_name", "last_name")),
                             ("orders", ("order_id", "customer_id", "order_date")),
                             ("payments", ("payment_id", "order_id", "amount"))):
            connection.executemany("INSERT INTO stg_" + name + " VALUES (?,?,?)",
                                   [tuple(r[k] for k in fields) for r in fixture[name]])
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                   sqlite3.SQLITE_RECURSIVE}

        def authorize(action, first, second, database, trigger):
            if action == sqlite3.SQLITE_FUNCTION and second not in {"count", "sum", "min", "max", "coalesce"}:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        remaining = 1000

        def bounded():
            nonlocal remaining
            remaining -= 1
            return remaining <= 0

        connection.set_progress_handler(bounded, 1000)
        cursor = connection.execute(render(sql))
        if tuple(c[0] for c in cursor.description or []) != FIELDS:
            raise ValueError("output_schema")
        rows = cursor.fetchmany(101)
        if len(rows) > 100:
            raise ValueError("output_limit")
        return [dict(row) for row in rows]
    finally:
        connection.close()


def split_payment(fixture: dict) -> dict:
    changed = copy.deepcopy(fixture)
    payment = next(p for p in changed["payments"] if p["amount"] >= 2)
    payment["amount"] -= 1
    changed["payments"].append({**payment, "payment_id": max(p["payment_id"] for p in changed["payments"]) + 1,
                                "amount": 1})
    return changed


def canonical(rows: list[dict]) -> list[str]:
    return sorted(json.dumps(row, sort_keys=True) for row in rows)


def check(sql: str, fixture: dict) -> dict:
    expected = expected_rows(fixture)
    actual = execute(sql, fixture)
    keys = [r["customer_id"] for r in actual]
    ids = [r["customer_id"] for r in expected]
    expected_by_id = {r["customer_id"]: r for r in expected}
    mismatches = Counter()
    for row in actual:
        if row["customer_id"] in expected_by_id:
            reference = expected_by_id[row["customer_id"]]
            mismatches.update(k for k in FIELDS if row[k] != reference[k])
    grain_ok = None not in keys and len(set(keys)) == len(keys)
    membership_ok = set(keys) == set(ids)
    reference_ok = canonical(actual) == canonical(expected)
    invariant_ok = canonical(actual) == canonical(execute(sql, split_payment(fixture)))
    return {"source_contract": "passed", "row_grain_pass": grain_ok,
            "customer_membership_pass": membership_ok,
            "metric_mismatch_counts": dict(sorted(mismatches.items())),
            "independent_reference_pass": reference_ok, "payment_split_invariance_pass": invariant_ok,
            "all_checks_pass": grain_ok and membership_ok and reference_ok and invariant_ok,
            "scope": "supplied_synthetic_fixture_only"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(args.query.read_text(), json.loads((EXAMPLE / "fixture.json").read_text()))
    except (OSError, ValueError, sqlite3.Error, KeyError, TypeError, StopIteration):
        print(json.dumps({"status": "check_error", "all_checks_pass": False}))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
