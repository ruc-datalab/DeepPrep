## Demonstration 1

Input Table:

name | salary
---|---
"Manchester United" | 100000
"Manchester City" | 120000

Data Cleaning Operator: [op_replace_tag]

Output:

```python
target_df = input_table.copy()
target_df['first_name'] = target_df['name'].str.split(' ').str[0]
target_df['last_name'] = target_df['name'].str.split(' ').str[1]
target_df = target_df.drop(['name'], axis=1)
```

After executing the python code, we get a target_df contain dirty data:

first_name | last_name | salary
---|---|---
"Manchester" | "United" | 100000
"Manchester" | "City" | 120000

To restore, Concatenate(table_name="input_table", concatenate_columns=["first_name", "last_name"], target_column="name", func="""
def concat(row: pd.Series) -> str:
    return f"{row['first_name']} {row['last_name']}"
""")
