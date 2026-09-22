"""Synthetic cases and executable answer keys, never exposed to reviewer tools."""

from __future__ import annotations

from decimal import Decimal

from review_eval_tools import query


def case(name: str, domain: str, split: str, document: str, setup: str,
         verdict: str, value: str | None, oracle_sql: str | None = None) -> dict:
    if oracle_sql:
        value = str(query({"setup_sql": setup}, oracle_sql)["rows"][0][0])
    return {"id": name, "domain": domain, "split": split,
            "fixture": {"document": document, "setup_sql": setup},
            "gold": {"verdict": verdict, "value": value}}


def cases() -> list[dict]:
    joins = """
CREATE TABLE invoices(id TEXT, amount INTEGER);
INSERT INTO invoices VALUES ('i1',120),('i2',80),('i3',120);
CREATE TABLE lines(invoice_id TEXT, item TEXT);
INSERT INTO lines VALUES ('i1','a'),('i1','b'),('i2','a'),('i3','a');
"""
    eligibility = """
CREATE TABLE people(id TEXT, activated INTEGER);
INSERT INTO people VALUES ('a',1),('b',0),('c',1),('d',0);
CREATE TABLE exclusions(id TEXT);
INSERT INTO exclusions VALUES ('b'),(NULL);
"""
    return [
        case("join-total", "data", "development",
             "Review the reported total invoiced amount, counting each invoice once. "
             "Query: SELECT SUM(DISTINCT i.amount) AS total FROM invoices i "
             "JOIN lines l ON l.invoice_id=i.id; Report: total invoiced is 200. "
             "All invoices and lines are supplied. Return the correct total as value.",
             joins, "needs_correction", None, "SELECT SUM(amount) FROM invoices"),
        case("weighted-rate", "finance", "development",
             "Report: overall gross margin is 50 percent, the average of segment margins. "
             "The complete ledger has segment A revenue 900 and cost 810, segment B revenue "
             "100 and cost 10, same currency and period. Policy: consolidated gross margin "
             "is total revenue minus total cost, divided by total revenue. Return the "
             "correct percentage as value, not a fraction.", "", "needs_correction",
             str((Decimal(1000)-Decimal(820))/Decimal(1000)*100)),
        case("retry-safe", "systems", "development",
             "Review the claim: final balance is 70 after duplicate delivery. Initial "
             "balance 100. Event e1 debits 30. In one database transaction the worker "
             "inserts e1 into a UNIQUE processed_events table and debits the balance; "
             "on duplicate-key it rolls back and does not debit. Commit is durable; "
             "ack is lost; e1 is retried. No other events or external side effects. "
             "Return final balance as value. Review only the stated transaction model.",
             "", "supported", str(100 - 30 * len({"e1", "e1"}))),
        case("membership", "systems", "development",
             "Report: synchronization membership is correct because both systems count "
             "three records. Complete source IDs: a,b,c. Complete destination IDs: a,b,d. "
             "Required contract: exactly the same IDs. Return the number of IDs in the "
             "symmetric difference as value. No eventual consistency grace is allowed.",
             "", "needs_correction", str(len({"a", "b", "c"} ^ {"a", "b", "d"}))),
        case("missing-fx", "finance", "development",
             "Report: consolidated USD revenue is 150. Complete sales: USD 100 and EUR 50. "
             "Policy requires translation at the approved period-average EUR-to-USD rate. "
             "The supplied packet contains no rate schedule. Review the USD total.",
             "", "insufficient_evidence", None),
        case("null-exclusion", "data", "development",
             "Review: eligible population is 3. Query: SELECT COUNT(*) FROM people p "
             "WHERE NOT EXISTS (SELECT 1 FROM exclusions x WHERE x.id=p.id). "
             "Policy excludes matching non-null IDs; null exclusion IDs are ignored. "
             "Tables are complete. Return eligible count as value.", eligibility,
             "supported", None, "SELECT COUNT(*) FROM people p WHERE NOT EXISTS "
             "(SELECT 1 FROM exclusions x WHERE x.id=p.id)"),
        case("null-trap", "data", "holdout",
             "Review: eligible population is 0. Query: SELECT COUNT(*) FROM people "
             "WHERE id NOT IN (SELECT id FROM exclusions). Policy excludes matching "
             "non-null IDs; null exclusion IDs are ignored. Tables are complete. "
             "Return the correct eligible count as value.", eligibility,
             "needs_correction", None, "SELECT COUNT(*) FROM people p WHERE NOT EXISTS "
             "(SELECT 1 FROM exclusions x WHERE x.id=p.id)"),
        case("accrual-clean", "finance", "holdout",
             "Review: April recognized revenue is 240. A customer pays 2880 on April 1 "
             "for service April 1 through March 31 next year. Supplied policy recognizes "
             "equal amounts in each of 12 service months; no tax, refunds or other sales. "
             "Return April recognized revenue as value. This is the stated company policy, "
             "not a request to determine accounting-standard compliance.", "", "supported",
             str(Decimal(2880)/Decimal(12))),
        case("retry-gap", "systems", "holdout",
             "Review: exactly-once debit leaves balance 70. Initial balance 100. Worker "
             "checks e1 is absent from processed_events, commits debit 30, then writes "
             "e1 to processed_events in a separate transaction. It crashes after the debit "
             "commit and before that write. On retry it repeats these steps and succeeds. "
             "No unique debit key or compensating operation exists. Return final balance "
             "after this specified execution as value.", "", "needs_correction", str(100-30-30)),
        case("cohort-gap", "data", "holdout",
             "Review: 30-day activation is 60 percent for the September signup cohort. "
             "As of September 20, the complete snapshot has 100 September signups, "
             "60 activated so far. Activation is any first qualifying event within 30 days "
             "of signup. There is no forecast model or subsequent observation. Review the "
             "final 30-day cohort rate, not activation so far.",
             "", "insufficient_evidence", None),
        case("fx-direction", "finance", "holdout",
             "Review: consolidated USD revenue is 150. Complete period sales are USD 100 "
             "and EUR 60. The approved rate is 1 EUR = 1.20 USD, same period and basis. "
             "The analyst computed 100 + 60 / 1.20. Return the correct USD total as value.",
             "", "needs_correction", str(Decimal(100)+Decimal(60)*Decimal('1.20'))),
        case("watermark-gap", "systems", "holdout",
             "Review: the warehouse is fully synchronized at 12:00. Observations: job "
             "completed successfully at 12:00 and max business event timestamp in the "
             "warehouse is 12:00. No source offset, extraction watermark, source snapshot, "
             "row identities or late-arrival guarantee is available. Can completeness "
             "be established? Classify the evidence, not hypothetical bugs.",
             "", "insufficient_evidence", None),
    ]


def score(case_item: dict, answer: dict) -> dict:
    """Score verdict and numeric correction only; prose support needs inspection."""
    gold = case_item["gold"]
    if (not isinstance(answer, dict) or not {"verdict", "value", "reason", "checks"} <= set(answer)
            or not isinstance(answer["reason"], str) or not answer["reason"].strip()
            or not isinstance(answer["checks"], list)):
        return {"verdict_correct": False, "value_correct": False,
                "objective_pass": False, "explanation_review": "not_measured"}
    verdict_ok = answer.get("verdict") == gold["verdict"]
    value = answer.get("value")
    try:
        value_ok = value is None if gold["value"] is None else (
            not isinstance(value, bool) and value is not None
            and Decimal(str(value)).is_finite()
            and abs(Decimal(str(value)) - Decimal(gold["value"])) <= Decimal("0.000001")
        )
    except Exception:
        value_ok = False
    return {"verdict_correct": verdict_ok, "value_correct": value_ok,
            "objective_pass": verdict_ok and value_ok,
            "explanation_review": "not_measured"}
