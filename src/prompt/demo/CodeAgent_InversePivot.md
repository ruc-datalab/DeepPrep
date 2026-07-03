## Demonstration 1

Input Table:

date | Clothing | Electronics
---|---|---
"2023-01-01" | 300 | 13000
"2023-01-02" | 750 | 4500

Data Cleaning Operator: [op_replace_tag]

Output:

```python
target_df = input_table.melt(
    id_vars=['date'],  
    var_name='category', 
    value_name='sales' 
)

target_df = target_df.sort_values('date').reset_index(drop=True)
print(target_df)
```

After execute the python code, we get a target_df contain dirty data:

date | category | sales
---|---|---
"2023-01-01" | "Clothing" | 300
"2023-01-01" | "Electronics" | 13000
"2023-01-02" | "Clothing" | 750
"2023-01-02" | "Electronics" | 4500

To restore the original table from the target_df, we can execute the Pivot operator: Pivot(table_name="input_table", index="date", columns="category", values="sales", aggfunc="sum")

## Demonstration 2

Input Table:

quarter | North_America | Europe | Asia
---|---|---|---
"2023-Q1" | 25000 | 18000 | 32000
"2023-Q2" | 28000 | 22000 | 35000
"2023-Q3" | 31000 | 19000 | 38000

Data Cleaning Operator: [op_replace_tag]

Output:

```python
input_table = input_table.set_index('quarter')

target_df = input_table.melt(
    id_vars=['quarter'],
    var_name='region',
    value_name='revenue'
)

target_df = target_df.sort_values('quarter').reset_index(drop=True)
```

After executing the python code, we get a target_df contain dirty data:

quarter | region | revenue
---|---|---
"2023-Q1" | "North_America" | 25000
"2023-Q1" | "Europe" | 18000
"2023-Q1" | "Asia" | 32000
"2023-Q2" | "North_America" | 28000
"2023-Q2" | "Europe" | 22000
"2023-Q2" | "Asia" | 35000
"2023-Q3" | "North_America" | 31000
"2023-Q3" | "Europe" | 19000
"2023-Q3" | "Asia" | 38000

To restore the original table from the target_df, we can execute the Pivot operator: Pivot(table_name="input_table", index="quarter", columns="region", values="revenue", aggfunc="sum")