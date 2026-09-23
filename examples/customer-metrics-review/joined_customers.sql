-- Locally authored mutation for a controlled test; not an upstream bug.
select
    c.customer_id, c.first_name, c.last_name,
    min(o.order_date) as first_order, max(o.order_date) as most_recent_order,
    case when count(o.order_id) = 0 then null else count(o.order_id) end as number_of_orders,
    sum(p.amount) as customer_lifetime_value
from stg_customers c
left join stg_orders o on c.customer_id = o.customer_id
left join stg_payments p on o.order_id = p.order_id
group by c.customer_id, c.first_name, c.last_name
