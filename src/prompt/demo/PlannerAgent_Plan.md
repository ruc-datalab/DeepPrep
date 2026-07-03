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

Target Table Schema Description:
We transform the input tables to complete the task: The task aims to count the number of distinct plane names associated with any pilot from the input table that includes pilot details and their plane-related attributes.
The column schema of the target table is as follows:
- Name of Column: "count(DISTINCT plane_name)"
  - Description: The total number of unique plane names that appear across all pilots in the input data, reflecting the distinct types of planes referenced for any pilot.
  - Requirements
    - Single non-negative integer value
    - Represents the count of unique plane names across all pilots

<logical_operator> TableTransformation(input_table=["table_1"], requirement="Please first transform the input table to a wide format with columns: pilot_name, attribute, plane_name, age_value") </logical_operator>
<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"
</observation>

<logical_operator> DataCleaning(input_tables=["table_1"], requirement="Please clean the table_1, including removing the quotes, standardize string to numerical, drop out null age_values, and deduplicate the rows where the plane_name is the same.") </logical_operator>
<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"
</observation>

<logical_operator> TableTransformation(input_tables=["table_1"], requirement="Please calculate the count of distinct plane names and select only the value column.") </logical_operator>
<observation> 
Name: "statistic_table"
value
---
5
</observation>

<logical_operator> DataCleaning(input_tables=["statistic_table"], requirement="Rename the column 'value' to 'count(DISTINCT plane_name)'") </logical_operator>
<observation> 
Name: "statistic_table"
count(DISTINCT plane_name)
---
5
</observation>