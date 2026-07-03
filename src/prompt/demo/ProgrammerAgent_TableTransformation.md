## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | b1 | B-52 Bomber | f14 | F-17 Fighter | pc
---|---|---|---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"

Requirement: Please first transform the input table to a wide format with columns: pilot_name, attribute, plane_name, age_value

<physical_operator> Stack(table_name="table_1", id_vars=["pilot_name", "attribute"], value_vars=["b1", "B-52 Bomber", "f14", "F-17 Fighter", "pc"], var_name="plane_name", value_name="age_value") </physical_operator>

<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0
...... 
</observation>

## Demonstration 2

Input Table:
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0

Requirement: Please calculate the count of distinct plane names and select only the value column.

<physical_operator> CalculateStatistic(table_name="table_1", statistic_name="count(DISTINCT plane_name)", func="""def calculate_stat(df: pd.DataFrame): return len(df)""") --> SelectCol(table_name="statistic_table", columns=["value"]) </physical_operator>

<observation> 
Name: "statistic_table"
value
---
5
</observation>