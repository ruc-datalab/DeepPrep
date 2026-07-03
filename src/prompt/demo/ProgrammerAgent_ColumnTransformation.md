## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"smith" | "age" | "b1" | 41.0
"silson" | "age" | "b1" | 52.0
"silson" | "age" | "b1" | 52.0

Requirement: Please standardize the pilot_name to uppercase.

<physical_operator> StandardizeString(table_name="table_1", column_name="pilot_name", func="""def transform(s): return s.upper()""") </physical_operator>

<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"SMITH" | "age" | "b1" | 41.0
"SILSON" | "age" | "b1" | 52.0
"SILSON" | "age" | "b1" | 52.0
...... 
</observation>