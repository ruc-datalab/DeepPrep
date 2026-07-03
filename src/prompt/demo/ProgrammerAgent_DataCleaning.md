## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0

Requirement: Please clean the table_1, including removing the quotes, standardize string to numerical, drop out null age_values, and deduplicate the rows where the plane_name is the same.

<physical_operator> CastType(table_name="table_1", column="age_value", dtype="str") --> StandardizeString(table_name="table_1", column_name="age_value", func="""def transform(s): s = s.strip('"'); if s.lower() == 'nan': return ''; return s""") --> CastType(table_name="table_1", column="age_value", dtype="float") --> DropNull(table_name="table_1", columns=["age_value"]) --> Deduplicate(table_name="table_1", subset=["plane_name"], keep="first") </physical_operator>

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
Name: "statistic_table"
value
---
5

Requirement: Rename the column 'value' to 'count(DISTINCT plane_name)'.

<physical_operator> Rename(table_name="statistic_table", rename_map=[{"old_name": "value", "new_name": "count(DISTINCT plane_name)"}]) </physical_operator>

<observation> 
Name: "statistic_table"
count(DISTINCT plane_name)
---
5
</observation>