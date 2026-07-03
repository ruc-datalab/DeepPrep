Note: 

- You only need to generate a **code snippet**.
    - **Do not** generate code for table reading, etc., as the tables have already been read and stored in the `input_tables` object in the code's context.
    - **Do not** generate code for other table transformation operation, only use brief code to implement the given logical operator.
- Input Format: The input tables is maintained in a python dict `input_tables`, where the keys store table names and the values store table objects of pd.DataFrame. You can access all the tables stored in the dict in a way similar to `input_tables['table_1']`.
- Output Format: Your generated target table will be maintained in a pd.Dataframe object named `target_df`. Do not change the name of your output object, only use `target_df`.