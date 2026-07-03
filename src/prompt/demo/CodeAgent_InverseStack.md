## Demonstration 1

Input Table:

Product | Region | Sales
---|---|---
A | US | 100
B | EU | 150
C | ASIA | 200

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
wide_table = input_table.pivot(
    index='Product',
    columns='Region',
    values='Sales'
)
wide_table.columns.name = None
wide_table = wide_table.reset_index()

# This creates the "dirty" wide format table
target_df = wide_table
```

After executing the python code, we get a target_df contain dirty data:

Product | ASIA | EU | US
---|---|---|---
A | NaN | NaN | 100
B | NaN | 150 | NaN
C | 200 | NaN | NaN

To restore the original table from the target_df, we can execute the Stack operator: Stack(
    table_name="target_df",
    id_vars=["Product"],
    value_vars=["ASIA", "EU", "US"],
    var_name="Region",
    value_name="Sales"
)