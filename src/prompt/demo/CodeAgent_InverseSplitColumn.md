## Demonstration 1

Input Table:

sale_id | sale_date | product_id | count
---|---|---
1001 | "2025-01-01" | "PA01" | 3772
1022 | "2025-01-01" | "PA98" | 8466
1055 | "2024-12-2" | "PB97" | 16692

Data Cleaning Operator: [op_replace_tag]

Output:

```python
target_df = input_table.copy()
target_df['product_id_and_count'] = target_df['product_id'] + '-' + target_df['count'].astype(str)
target_df = target_df.drop(['product_id', 'count'], axis=1)
```

After executing the python code, we get a target_df contain dirty data:

sale_id | sale_date | product_id_and_count
---|---|---
1001 | "2025-01-01" | "PA01-3772"
1022 | "2025-01-01" | "PA98-8466"
1055 | "2024-12-2" | "PB97-16692"

To restore, SplitColumn(table_name="input_table", source_column="product_id_and_count", target_columns=["product_id", "count"], func="""def split(val): parts = val.split('-'); return {'product_id': parts[0], 'count': int(parts[1])}""")