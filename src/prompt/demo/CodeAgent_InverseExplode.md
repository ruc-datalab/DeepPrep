## Demonstration 1

Input Table:

movie | director | award
---|---|---
"Titanic" | "James Cameron" | "Best Picture"
"Titanic" | "James Cameron" | "Best Actor"
"The Dark Knight" | "Christopher Nolan" | "Best Picture"
"The Dark Knight" | "Christopher Nolan" | "Best Actor"
"The Lord of the Rings: The Return of the King" | "Peter Jackson" | "Best Picture"
"The Lord of the Rings: The Return of the King" | "Peter Jackson" | "Best Actor"

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
# Assuming input_table is a pandas DataFrame
target_df = input_table.groupby(['movie', 'director'])['award'].apply(', '.join).reset_index()
```

After executing the python code, we get a target_df contain dirty data:

movie | director | award
---|---|---
"Titanic" | "James Cameron" | "Best Picture,Best Actor"
"The Dark Knight" | "Christopher Nolan" | "Best Picture,Best Actor"
"The Lord of the Rings: The Return of the King" | "Peter Jackson" | "Best Picture,Best Actor"

To restore the original table from the target_df, we can execute the Explode operator: Explode(
    table_name="target_df",
    column="award",
    split_comma=True
)

## Demonstration 2

Input Table:

born_state | head_ID | name | age
---|---|---|---
"Alabama" | 1 | "Tiger Woods" | 67.0
"Alabama" | 3 | "K. J. Choi" | 69.0
"California" | 2 | "Sergio García" | 68.0
"California" | 4 | "Dudley Hart" | 52.0
"California" | 6 | "Billy Mayfair" | 69.0
"California" | 8 | "Nick Faldo" | nan

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
group_column='born_state'
explode_columns=['head_ID', 'name', 'age']

df = input_table.copy()
grouped = df.groupby(group_column)
result_rows = []

for group_value, group_df in grouped:
    new_row = group_df.iloc[0].copy()

    for col in explode_columns:
        values = group_df[col].dropna().tolist()
        new_row[col] = values
    result_rows.append(new_row)
target_df = pd.DataFrame(result_rows)
```

After executing the python code, we get a target_df contain dirty data:

born_state | head_ID | name | age
---|---|---|---
"Alabama" | [1, 3] | ['Tiger Woods', 'K. J. Choi'] | [67.0, 69.0]
"California" | [2, 4, 6, 8] | ['Sergio García', 'Dudley Hart', 'Billy Mayfair', 'Nick Faldo'] | [68.0, 52.0, 69.0]

To restore the original table from the target_df, we can execute the Explode operator: Explode(
    table_name='target_df',
    column=['head_ID', 'name', 'age'],  # 多列explode
    split_comma=False
)

## Demonstration 3

Input Table:

born_state | head_ID | name | age
---|---|---|---
"Alabama" | "1" | "Tiger Woods" | "67.0"
"Alabama" | "3" | "K. J. Choi" | "69.0"
"California" | "2" | "Sergio García" | "68.0"
"California" | "4" | "Dudley Hart" | "52.0"
"California" | "6" | "Billy Mayfair" | "69.0"
"California" | "8" | "Nick Faldo" | "45.0"
"Texas" | "10" | "Jordan Spieth" | "32.0"
"Texas" | "20" | "Rickie Fowler" | "35.0"

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
group_column='born_state'
explode_columns=['head_ID', 'name', 'age']

grouped = df.groupby(group_column)
result_rows = []

for group_value, group_df in grouped:
    new_row = group_df.iloc[0].copy()
    for col in explode_columns:
        values = group_df[col].dropna().tolist()
        if values:
            str_values = [str(v) for v in values]
            new_row[col] = ','.join(str_values)
        else:
            new_row[col] = ''
    result_rows.append(new_row)
target_df = pd.DataFrame(result_rows)
```

After executing the python code, we get a target_df contain dirty data:

born_state | head_ID | name | age
---|---|---|---
"Alabama" | "1,3" | "Tiger Woods,K. J. Choi" | "67.0,69.0"
"California" | "2,4,6,8" | "Sergio García,Dudley Hart,Billy Mayfair,Nick Faldo" | "68.0,52.0,69.0"
"Texas" | "10,20" | "Jordan Spieth,Rickie Fowler" | "32.0,35.0"

To restore the original table from the target_df, we can execute the Explode operator: Explode(
    table_name='target_df',
    column=['head_ID', 'name', 'age'],
    split_comma=True
)