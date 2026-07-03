## Demonstration 1

Input Table:

date | sales
---|---
"2023-01-01" | 100
"2023-01-02" | 200

Data Cleaning Operator: [op_replace_tag]

Output:

```python
ratio = 0.5  # 50% of values will have different formats
diverse_formats = ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y', '%Y/%m/%d']

target_df = input_table.copy()
for i in range(len(target_df)):
    if random.random() < ratio:
        selected_format = random.choice(diverse_formats)
        target_df.loc[i, 'date'] = pd.to_datetime(target_df.loc[i, 'date']).strftime(selected_format)
    else:
        target_df.loc[i, 'date'] = pd.to_datetime(target_df.loc[i, 'date']).strftime('%Y-%m-%d')

# This creates the "dirty" table with inconsistent datetime formats
```

After executing the python code, we get a target_df contain dirty data:

date | sales
---|---
01/01/2023 | 100
2023-01-02 | 200

To restore the original table from the target_df, we can execute the StandardizeDatetime operator: StandardizeDatetime(
    table_name="target_df",
    column_name="date",
    date_format="%Y-%m-%d"
)
