## Demonstration 1

Input Table:

name | age
---|---
"John" | 25
"Jane" | 30
"Mike" | 35

Data Cleaning Operator: [op_replace_tag]

Output:

```python
target_df = input_table.copy()
target_df['age'] = target_df['age'].apply(lambda x: f'"{x}"')
```

After executing the python code, we get a target_df contain dirty data:

name | age
---|---
"John" | "25"
"Jane" | "30"
"Mike" | "35"

To restore the original table from the target_df, we can execute the CastType operator: CastType(table_name="input_table", column="age", dtype="int")
