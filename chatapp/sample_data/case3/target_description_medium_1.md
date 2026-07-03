````markdown
# Medium case 1: Subscription metrics by plan (March 2024)

## High level task description
Using the uploaded tables, build a target table with **subscription metrics by plan** for **March 2024**.

Rules:
1. A subscription is considered **active in March 2024** if:
   - `start_date` <= 2024-03-31
   - and (`end_date` is empty OR `end_date` >= 2024-03-01)
2. Payments:
   - Only include payments whose `paid_date` is in March 2024.
   - Deduplicate duplicated `payment_id` rows (keep one).
3. Refunds reduce revenue:
   - Only include refunds whose `refund_date` is in March 2024.
   - Ignore refunds outside March.
   - Refund amounts are in the same currency as recorded in `refunds.csv`.
4. Currency conversion:
   - Convert payment/refund money to USD using `fx_rates.csv` by matching on (`date`, `currency`) to get `to_usd`.
   - USD has `to_usd=1`.
5. Net paid (USD) by plan = sum(payments_usd_in_march) - sum(refunds_usd_in_march).
6. `paying_users` counts distinct `user_id` whose **net paid in March for that plan** is > 0.
7. Round `net_paid_usd` to 2 decimals.

Output columns (one row per plan):
- `plan`
- `active_sub_cnt`
- `net_paid_usd`
- `paying_users`

Input tables:
- `subscriptions.csv`
- `payments.csv`
- `refunds.csv`
- `fx_rates.csv`

## schemaJson (paste into UI)

```json
{
  "plan": {"description": "Subscription plan", "requirements": ["distinct"]},
  "active_sub_cnt": {"description": "Number of subscriptions active at any time in March 2024", "requirements": []},
  "net_paid_usd": {"description": "Net paid amount in USD in March 2024 (payments - refunds)", "requirements": []},
  "paying_users": {"description": "Number of distinct users with net paid > 0 in March for this plan", "requirements": []}
}
```

````
