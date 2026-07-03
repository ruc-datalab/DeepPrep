## Demonstration 1

Input Table:

id | year | sales | profit
|---|---|---|---
1 | 2021 | 100 | 10
2 | 2021 | 200 | 20
3 | 2021 | 300 | 30
1 | 2022 | 150 | 15
2 | 2022 | 250 | 25
3 | 2022 | 350 | 35

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
InverseWideToLong(
    index=['id'],
    column='year',
    values=['sales', 'profit']
)
```

### Result: Dirty Table (Wide Format):

id | sales_2021 | sales_2022 | profit_2021 | profit_2022
|---|---|---|---|---
1 | 100 | 150 | 10 | 15
2 | 200 | 250 | 20 | 25
3 | 300 | 350 | 30 | 35

To restore the original table from the target_df, we can execute the WideToLong operator: WideToLong(
    table_name="target_df",
    subnames=["sales", "profit"],
    i=["id"],
    j="year",
    sep="_",
    suffix=r"\d+"
)


## Demonstration 2

Input Table:

City_ID | Official_Name | Status | Attribute | Value
---|---|---|---|---
1 | "Grand Falls/Grand-Sault" | "Town" | "Area_km_2" | 18.06
1 | "Grand Falls/Grand-Sault" | "Town" | "Population" | 5706.0
1 | "Grand Falls/Grand-Sault" | "Town" | "Census_Ranking" | "636 of 5008"
2 | "Perth-Andover" | "Village" | "Population" | 1778.0
2 | "Perth-Andover" | "Village" | "Census_Ranking" | "1442 of 5,008"
2 | "Perth-Andover" | "Village" | "Area_km_2" | 8.89
3 | "Plaster Rock" | "Village" | "Population" | 1135.0
3 | "Plaster Rock" | "Village" | "Area_km_2" | 3.09
3 | "Plaster Rock" | "Village" | "Census_Ranking" | "1936 of 5,008"
4 | "Drummond" | "Village" | "Area_km_2" | 8.91
4 | "Drummond" | "Village" | "Census_Ranking" | "2418 of 5008"
4 | "Drummond" | "Village" | "Population" | 775.0
5 | "Aroostook" | "Village" | "Area_km_2" | 2.24
5 | "Aroostook" | "Village" | "Population" | 351.0
5 | "Aroostook" | "Village" | "Census_Ranking" | "3460 of 5008"

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
wide_df = input_table.pivot(
    index=['City_ID', 'Official_Name', 'Status'],
    columns='Attribute',
    values='Value'
)
# wide_df.columns = [f'{metric}_{year}' for metric, year in wide_df.columns]
newcols = []
wide_df.columns = [f'Value_{col}' for col in wide_df.columns]  # 结果：City_Area_km_2、City_Population等
wide_df = wide_df.reset_index()

# This creates the "dirty" wide format table
target_df = wide_df
```

### Result: Dirty Table (Wide Format):

City_ID | Official_Name | Status | Value_Area_km_2 | Value_Census_Ranking | Value_Population
---|---|---|---|---|---
1 | "Grand Falls/Grand-Sault" | "Town" | 18.06 | "636 of 5008" | 5706.0
2 | "Perth-Andover" | "Village" | 8.89 | "1442 of 5,008" | 1778.0
3 | "Plaster Rock" | "Village" | 3.09 | "1936 of 5,008" | 1135.0
4 | "Drummond" | "Village" | 8.91 | "2418 of 5008" | 775.0
5 | "Aroostook" | "Village" | 2.24 | "3460 of 5008" | 351.0

To restore the original table from the target_df, we can execute the WideToLong operator: WideToLong(
    table_name="target_df",
    subnames=["Value"],
    i=["City_ID", "Official_Name", "Status"],
    j="Attribute",
    sep="_",
    suffix=r".*"
)