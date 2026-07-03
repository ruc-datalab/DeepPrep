Task Definition:

- Input: You will be given a table and the type of a target data cleaning operator
- Required Output: You are required to generate the inverse operation of the data cleaning operator. Also, you are required to complete the argument of the data cleaning operator.
- Requirement: Executing the code on the input table will get a table with dirty data. Executing the operator on the dirty table will restore the original input table.
- You can refer to the Demonstration Section to see a specific example.

Note:

- You only need to generate a **code snippet**. **Do not** generate code for reading the table, intitialzing the dataframe object, etc., as the tables have already been read and stored in the `input_table` object in the code's context.
- Input Format: The input table is maintained in a pandas.DataFrame object `input_table`.
- Output Format: Your generated target table will be maintained in a pd.Dataframe object named `target_df`. Do not change the name of your output object, only use `target_df`.