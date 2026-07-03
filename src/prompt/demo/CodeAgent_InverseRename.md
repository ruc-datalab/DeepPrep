## Demonstration 1

Input Table:

client id | client name | client type | client address
---|---|---|---
1 | John Doe | Individual | 123 Main St, Anytown, USA
2 | Jane Smith | Company | 456 Elm St, Anytown, USA
3 | Jim Beam | Company | 789 Oak St, Anytown, USA
4 | John Doe | Individual | 123 Main St, Anytown, USA
5 | Jane Smith | Company | 456 Elm St, Anytown, USA

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
# rename the column "client id" to "cid"
input_table.rename(columns={"client type": "leixing", "client address": "dizhi"}, inplace=True)
# Print the renamed table
target_df = input_table
```

After executing the python code to make the table contain dirty data, we get a target_df:

client id | client name | leixing | dizhi
---|---|---|---
1 | John Doe | Individual | 123 Main St, Anytown, USA
2 | Jane Smith | Company | 456 Elm St, Anytown, USA
3 | Jim Beam | Company | 789 Oak St, Anytown, USA
4 | John Doe | Individual | 123 Main St, Anytown, USA
5 | Jane Smith | Company | 456 Elm St, Anytown, USA

We can restore the original table from the target_df by executing the Rename operator: Rename(table_name="input_table", rename_map=[{"old_name": "leixing", "new_name": "client type"}, {"old_name": "dizhi", "new_name": "client address"}])

## Demonstration 2

Input Table:

student_id | student_name | student_age | student_gender
---|---|---|---
1 | John Doe | 20 | Male
2 | Jane Smith | 21 | Female
3 | Jim Beam | 22 | Male
4 | John Doe | 20 | Male
5 | Jane Smith | 21 | Female

Data Cleaning Operator Type: [op_replace_tag]

Output:

```python
input_table.rename(columns={"student_gender": "xb"}, inplace=True)
# Print the renamed table
target_df = input_table
```

After executing the python code to make the table contain dirty data, we get a target_df:

student_id | student_name | student_age | xb
---|---|---|---
1 | John Doe | 20 | Male
2 | Jane Smith | 21 | Female
3 | Jim Beam | 22 | Male
4 | John Doe | 20 | Male
5 | Jane Smith | 21 | Female

We can restore the original table from the target_df by executing the Rename operator: Rename(table_name="input_table", rename_map=[{"old_name": "xb", "new_name": "student_gender"}])

