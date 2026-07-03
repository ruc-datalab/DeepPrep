````markdown
# Simple case 2: Revenue by category (Feb 2024)

## High level task description
Using the uploaded tables, build a target table that shows **total revenue by product category** for **completed orders in Feb 2024**.

Rules:
1. Only include orders where `status == "completed"`.
2. Only include orders where `order_date` is in **2024-02-01 .. 2024-02-29**.
3. Revenue for an order item = `qty * unit_price`.
4. Group by `category` and sum revenue.
5. Output revenue rounded to 2 decimals.

Output columns:
- `category`
- `revenue`

Input tables:
- `orders.csv`
- `order_items.csv`
- `products.csv`

## schemaJson (paste into UI)

```json
{
  "category": {"description": "Product category", "requirements": ["distinct"]},
  "revenue": {"description": "Total revenue for completed Feb 2024 orders", "requirements": []}
}
```

````
