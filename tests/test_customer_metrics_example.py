import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("customer_check", ROOT / "scripts/check_customer_metrics.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
EXAMPLE = module.EXAMPLE


@pytest.fixture
def fixture():
    return json.loads((EXAMPLE / "fixture.json").read_text())


def test_upstream_provenance_and_correct_counterpart(fixture):
    source = EXAMPLE / "upstream_customers.sql"
    provenance = json.loads((EXAMPLE / "provenance.json").read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == provenance["sha256"]
    assert module.check(source.read_text(), fixture)["all_checks_pass"]


def test_join_mutation_survives_grain_and_total_checks_but_fails_reference(fixture):
    sql = (EXAMPLE / "joined_customers.sql").read_text()
    report = module.check(sql, fixture)
    assert report["row_grain_pass"] and report["customer_membership_pass"]
    assert report["metric_mismatch_counts"] == {"number_of_orders": 1}
    assert not report["independent_reference_pass"]
    assert not report["payment_split_invariance_pass"]
    actual = module.execute(sql, fixture)
    expected = module.expected_rows(fixture)
    assert [r["customer_lifetime_value"] for r in actual] == [90, 70, None]
    assert [r["number_of_orders"] for r in actual] == [3, 1, None]
    assert [r["number_of_orders"] for r in expected] == [2, 1, None]


def test_split_preserves_independent_truth_and_correct_query(fixture):
    changed = module.split_payment(fixture)
    assert module.expected_rows(changed) == module.expected_rows(fixture)
    assert module.check((EXAMPLE / "upstream_customers.sql").read_text(), changed)["all_checks_pass"]


@pytest.mark.parametrize("alteration", ["duplicate", "omit", "money", "zero_for_null"])
def test_negative_controls_cannot_receive_a_pass(fixture, alteration):
    sql = module.render((EXAMPLE / "upstream_customers.sql").read_text())
    if alteration == "duplicate":
        sql = "SELECT * FROM (" + sql + ") UNION ALL SELECT * FROM (" + sql + ")"
    elif alteration == "omit":
        sql = "SELECT * FROM (" + sql + ") WHERE customer_id != 102"
    elif alteration == "money":
        sql = sql.replace("sum(amount)", "sum(amount) + 1")
    else:
        sql = sql.replace("customer_orders.number_of_orders,", "coalesce(customer_orders.number_of_orders, 0) as number_of_orders,")
    assert not module.check(sql, fixture)["all_checks_pass"]


@pytest.mark.parametrize("table,key", [("customers", "customer_id"), ("orders", "order_id"), ("payments", "payment_id")])
def test_bad_source_keys_rejected_before_scoring(fixture, table, key):
    fixture[table].append(copy.deepcopy(fixture[table][0]))
    with pytest.raises(ValueError, match="source_keys"):
        module.expected_rows(fixture)


@pytest.mark.parametrize("table,key", [("orders", "customer_id"), ("payments", "order_id")])
def test_bad_source_relationship_rejected(fixture, table, key):
    fixture[table][0][key] = -1
    with pytest.raises(ValueError, match="relationship"):
        module.expected_rows(fixture)


@pytest.mark.parametrize("query", ["DELETE FROM stg_orders", "ATTACH DATABASE ':memory:' AS other", "SELECT load_extension('x')"])
def test_queries_cannot_write_attach_or_load_extensions(fixture, query):
    with pytest.raises(sqlite3.DatabaseError):
        module.execute(query, fixture)


def test_no_arbitrary_template_execution():
    with pytest.raises(ValueError, match="unsupported_template"):
        module.render("select {{ arbitrary_function() }}")
