# Customer metrics contract

Review the SQL against this complete fictional staging snapshot.
Produce one row for every customer, with a unique, non-null customer_id.
number_of_orders counts distinct source order entities for that customer,
regardless of how many payments an order has. customer_lifetime_value sums
all supplied payments attached to that customer's orders, in AUD. Payment
amounts are exact whole AUD here; no foreign exchange, refunds, tax allocation
or revenue-recognition policy is implied. The first and most recent order dates
come from source orders. Preserve NULL count, dates and value for a customer
with no orders, matching the upstream output contract. IDs are unique and all
foreign keys resolve in this fixture; these conditions must be checked.

Splitting one payment into two positive payments with the same combined amount
must not change any customer metric. This is a representation change, not an
additional order. Source completeness applies only to this supplied snapshot.

The upstream model is a public SQL artifact from dbt Labs' Jaffle Shop.
The data and the alternative implementation are authored synthetic examples.
Do not infer that the upstream query is defective or that this fixture represents
any real company's accounting requirements.
