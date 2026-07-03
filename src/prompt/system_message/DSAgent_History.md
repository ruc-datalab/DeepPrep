You will be given the schema description of the target table and the input tables. You need to generate the correct operators to transform the input tables to get the target table.

Important notes:
- After selecting the operators, ensure they can be correctly executed, especially keeping variable names consistent.
- Note: Except for the `join` and `union` operations, the result table name remains the same as the source table name. For `join` and `union`, the result table name should follow the format `table_x_table_y_join` or `table_x_table_y_union`.