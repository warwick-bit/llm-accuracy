"""Independent synthetic everyday review cases, with hidden gold and local oracles.

These six authored cases are a development set, not a formal holdout. Sources
are ordinary review artifacts. Claim inventories exist only in the gold field.
"""
from __future__ import annotations

import sqlite3
from decimal import Decimal


def _gold(key, claim, status, value, requirement):
    units = {"rate": "percentage", "profit": "signed profit", "duplicate": "total charges"}
    return dict(id=key, claim=claim, status=status, value=value, requirement=requirement,
                numeric_unit=units.get(key, "as stated in claim"))


def _case(key, domain, sources, setup_sql, gold):
    return dict(id=key, domain=domain,
                fixture=dict(sources=sources, setup_sql=setup_sql), gold=gold)


ORDER_SQL = """
CREATE TABLE orders(id TEXT PRIMARY KEY, paid_day TEXT, amount_cents INTEGER);
CREATE TABLE shipments(id TEXT PRIMARY KEY, order_id TEXT);
INSERT INTO orders VALUES ('A','2026-04-03',12000),('B','2026-04-04',8000),
 ('C','2026-04-05',5000);
INSERT INTO shipments VALUES ('s1','A'),('s2','A'),('s3','B');
"""
ORDER_QUERY = """SELECT COUNT(DISTINCT o.id) AS paid_orders,
 SUM(o.amount_cents)/100.0 AS paid_sales
FROM orders o LEFT JOIN shipments s ON s.order_id=o.id
WHERE o.paid_day >= '2026-04-01' AND o.paid_day < '2026-05-01';"""
COHORT_SQL = """
CREATE TABLE signups(user_id TEXT PRIMARY KEY, signup_day TEXT);
CREATE TABLE purchases(user_id TEXT, paid_day TEXT, order_id TEXT);
INSERT INTO signups VALUES ('u1','2026-04-01'),('u2','2026-04-02'),
 ('u3','2026-04-03'),('u4','2026-04-30'),('u5','2026-05-01');
INSERT INTO purchases VALUES ('u1','2026-04-02','p1'),('u1','2026-04-03','p2'),
 ('u2','2026-04-09','p3'),('u4','2026-05-02','p4'),('u5','2026-05-02','p5');
"""
COHORT_QUERY = """SELECT COUNT(*) AS users,
 SUM(CASE WHEN EXISTS (
   SELECT 1 FROM purchases p WHERE p.user_id=s.user_id
   AND p.paid_day >= s.signup_day
   AND p.paid_day < date(s.signup_day, '+7 days')
 ) THEN 1 ELSE 0 END) AS converted
FROM signups s WHERE s.signup_day >= '2026-04-01'
 AND s.signup_day < '2026-05-01';"""
RETRY_SOURCE = '''# Small reproduction of the worker's timeout/retry path.
# Gateway accepts every submit; it does not deduplicate request IDs.
def run():
    submissions = []
    for attempt in range(3):
        started = attempt * 2
        submissions.append({"id": "invoice-7", "accepted_at": started,
                            "commits_at": started + 3})
        # Caller stops waiting after 2s. Server work is not cancelled.
    return submissions
'''
FENCE_SOURCE = '''# Reference model used for this rollout's lease-race rehearsal.
def apply(events):
    current_token = 0
    value = None
    accepted = []
    for kind, token, payload in events:
        if kind == "grant":
            current_token = token
        elif kind == "write" and token == current_token:
            value = payload
            accepted.append(token)
    return {"value": value, "accepted": accepted}

EVENTS = [("grant", 41, None), ("grant", 42, None),
          ("write", 42, "fresh"), ("write", 41, "stale")]
'''


def cases():
    """Return fresh case dictionaries; no external services or model calls."""
    return [
        _case("everyday_sql_shipments", "data", {
            "handoff.md": """April sales tile review
The export includes every paid order in April; amount_cents is the full order
value, inclusive of shipping. Shipments are optional and an order can have more
than one. This tile measures paid sales, not recognized revenue or shipped sales.
I added the shipment join for a future shipping filter. The preview gives 3 paid
orders and $370 paid sales. Both figures are ready for the April board table.
No shipping filter is enabled yet. Currency is USD throughout.
""",
            "tile.sql": ORDER_QUERY,
        }, ORDER_SQL, [
            _gold("sales", "April paid sales are $370.", "refuted", "250",
                  "Compute order-grain sales $250; identify repeated $120 order A from two shipments."),
            _gold("count", "The tile's paid-order count of 3 is correct.", "supported", "3",
                  "Confirm COUNT(DISTINCT) preserves three orders, including unshipped C."),
            _gold("shipping_filter", "The unused shipment join is safe for the current paid-sales sum.",
                  "refuted", None, "Explain fanout and remove/preaggregate shipment join for this unfiltered tile."),
        ]),
        _case("everyday_sql_cohort", "data", {
            "analysis.md": """April signup cohort conversion
Metric: fraction of April signups with at least one purchase on signup day or
one of the next six calendar days. All dates are UTC calendar dates. The data
extract is complete through 10 May, including purchases by April signups in May.
The attached query reports 4 users and 2 conversions, so the conversion rate is
50%. Repeat purchases do not count twice. The user who bought on 9 April after
signing up on 2 April is outside this metric's window. Product also asked for
the mobile-only rate; the extract has no device data, so that cut is pending.
""",
            "cohort.sql": COHORT_QUERY,
        }, COHORT_SQL, [
            _gold("rate", "April cohort conversion is 50% (2 of 4).", "supported", "50",
                  "Confirm u1 and u4 convert, and include u4's May purchase in the April signup cohort."),
            _gold("boundary", "u2's 9 April purchase is outside the specified window.",
                  "supported", None, "Respect the explicit half-open seven-calendar-day interval."),
            _gold("mobile", "Mobile-only conversion rate.",
                  "unresolved", None, "Device membership is absent; request device classification before calculating."),
        ]),
        _case("everyday_finance_prepaid", "finance", {
            "close-note.md": """April management close — USD
Our management reporting convention recognizes service revenue equally by full
calendar month. These contracts start on 1 April and each covers April through
March inclusive. There are no setup fees, tax, refunds, receivables, or other
sales. Ten customers each prepaid $1,200 on 1 April for twelve months of service.
The opening deferred-revenue balance was zero. The draft April P&L books the
$12,000 bank receipt as April service revenue and leaves deferred revenue at $0.
Costs paid and incurred in April are $4,000, with no other costs. On that basis
the draft reports $8,000 April operating profit. The treasury sheet separately
reports a positive April cash movement of $8,000.
""",
            "receipts.csv": "contracts,annual_usd,start,months\n10,1200,2026-04-01,12\n",
        }, "", [
            _gold("revenue", "April service revenue is $12,000.", "refuted", "1000",
                  "Apply the supplied monthly convention: 10*1200/12 = $1000, not all cash received."),
            _gold("deferred", "Closing deferred revenue is $0.", "refuted", "11000",
                  "Opening zero + $12000 receipts - $1000 earned = $11000 deferred."),
            _gold("profit", "April operating profit is $8,000.", "refuted", "-3000",
                  "April earned revenue $1000 less April costs $4000 gives a $3000 loss."),
            _gold("cash", "April cash movement is positive $8,000.", "supported", "8000",
                  "Keep correct cash movement distinct from the incorrect accrual profit."),
        ]),
        _case("everyday_finance_reconcile", "finance", {
            "treasury.md": """April treasury tie-out
Scope is the combined USD operating and USD reserve bank accounts, cash basis,
with no other USD accounts or transactions. Opening balances were $8,000 and
$2,000. Operating received $6,000 from customers and paid vendors $3,500. We also
moved $2,000 from operating to reserve; this is an internal transfer. Closing
operating is $8,500 and closing reserve is $4,000: combined closing USD cash is
$12,500, a $2,500 external net inflow. The transfer does not change combined cash.
There is a separate EUR account with a closing balance of EUR 900. Management
has not yet supplied the required month-end EUR/USD translation rate. The global
USD-equivalent closing balance is left pending for that rate.
""",
            "movements.csv": "account,kind,usd\noperating,customer,6000\noperating,vendor,-3500\noperating,transfer,-2000\nreserve,transfer,2000\n",
        }, "", [
            _gold("closing", "Combined closing cash in the two USD accounts is $12,500.",
                  "supported", "12500", "Reconcile operating $8500 plus reserve $4000."),
            _gold("net", "The USD accounts have an external net inflow of $2,500.",
                  "supported", "2500", "Exclude the offsetting internal transfer from external movement."),
            _gold("global", "Global USD-equivalent closing cash.",
                  "unresolved", None, "EUR 900 cannot be translated without the required closing FX rate."),
        ]),
        _case("everyday_systems_retry", "systems", {
            "incident.md": """Invoice worker retry patch review
The reproduction uses a gateway that accepts every submit and commits exactly
3 seconds later. Client waiting stops after 2 seconds, but that does not cancel
accepted server work. There is no server deduplication or idempotency table.
The same invoice ID is sent each time. The worker below allows three total
attempts, with no backoff. Every call times out from the caller's perspective.
The proposed rollout note says reusing the invoice ID prevents double charging,
and that the worker finishes waiting by t=6 seconds. It also says that by t=6 all
remote work is finished. We only have this reproduction; production timeout
frequency and invoice traffic volumes have not been collected yet. Estimated
monthly duplicate-charge count is pending those measurements.
""",
            "worker.py": RETRY_SOURCE,
        }, "", [
            _gold("duplicate", "The gateway commits only one charge for this invoice in the reproduction.",
                  "refuted", "3", "Three accepted submissions commit at t=3,5,7; ID reuse alone provides no deduplication."),
            _gold("wait", "The worker finishes its client-side waiting by t=6 seconds.",
                  "supported", "6", "Three sequential two-second waits end at t=6."),
            _gold("remote", "All remote work is complete by t=6 seconds.", "refuted", "7",
                  "Last accepted submission at t=4 commits at t=7, after client completion."),
            _gold("monthly", "Monthly production duplicate-charge count.",
                  "unresolved", None, "Require production traffic/timeout measurements; do not extrapolate a count from one reproduction."),
        ]),
        _case("everyday_systems_fencing", "systems", {
            "rollout.md": """Lease fencing rehearsal
The storage API applies grants and writes atomically in the order listed in
EVENTS. All writers in this rehearsal go through that API. A write is accepted
only when its token equals the current granted token. Tokens increase on each
grant, and a grant changes no stored value. Starting state has no stored value.
In this trace, worker 42 writes fresh after taking over the lease; worker 41's
late stale write then arrives. The rehearsal result should retain fresh and
accept exactly one write. This validates stale-write rejection for the supplied
trace. We still need the storage configuration and a crash/restart test before
claiming the accepted write survives a storage host crash; neither is included.
""",
            "rehearsal.py": FENCE_SOURCE,
        }, "", [
            _gold("value", "The final value in the supplied trace is fresh.", "supported", None,
                  "Simulate grants 41 then 42; reject late write with token 41."),
            _gold("accepted", "Exactly one write is accepted in the supplied trace.", "supported", "1",
                  "Only token 42 matches the granted token when its write arrives."),
            _gold("durability", "The accepted write survives a storage host crash.", "unresolved", None,
                  "The in-memory trace proves ordering/fencing, not durability; need storage configuration and crash evidence."),
        ]),
    ]


def oracle_values():
    """Executable independent calculations used to validate the hidden answers."""
    order_db = sqlite3.connect(":memory:")
    cohort_db = sqlite3.connect(":memory:")
    try:
        order_db.executescript(ORDER_SQL)
        cohort_db.executescript(COHORT_SQL)
        preview_count, preview_sales = order_db.execute(ORDER_QUERY).fetchone()
        true_sales = order_db.execute("SELECT SUM(amount_cents)/100 FROM orders").fetchone()[0]
        users, converted = cohort_db.execute(COHORT_QUERY).fetchone()
    finally:
        order_db.close()
        cohort_db.close()
    receipts = Decimal(10) * Decimal(1200)
    revenue = receipts / Decimal(12)
    retry_ns, fence_ns = {}, {}
    exec(RETRY_SOURCE, retry_ns)  # Authored static synthetic code only.
    exec(FENCE_SOURCE, fence_ns)
    submissions = retry_ns["run"]()
    fenced = fence_ns["apply"](fence_ns["EVENTS"])
    return {
        "preview_count": preview_count, "preview_sales": preview_sales,
        "true_sales": true_sales, "users": users, "converted": converted,
        "conversion_pct": 100 * converted / users,
        "revenue": revenue, "deferred": receipts - revenue,
        "profit": revenue - Decimal(4000), "cash_movement": receipts - Decimal(4000),
        "operating": 8000 + 6000 - 3500 - 2000, "reserve": 2000 + 2000,
        "external_net": 6000 - 3500,
        "submissions": submissions, "fenced": fenced,
    }
