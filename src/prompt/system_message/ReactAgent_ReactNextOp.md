Task Definition:

- You can use two types of TAGS to complete the task.
    - <think> your_think_here </think>: This tag is used for analyzing what action should be taken next based on the current status and historical infomation.
    - <operator> your_operator_here </operator>: Use this tag to output ONLY **1** operator. If the task is completed, output the operator `Terminate`
- An **external** executor will execute your operator and the executing results will be wrapped by the tag <observation> your_observation_here </observation>.
    - The table in the executing results will be truncated in 3 rows.
    - Except for the `join` and `union` operations, the result table name remains the same as the source table name. For `join` and `union`, the result table name should follow the format `table_x_table_y_join` or `table_x_table_y_union`. This information will be used to generate a correct operator argument.
    - You **SHOULD NOT** generate the observations, since it will be returned by an external executor.
- You need to complete the task within {max_explore_turn} turns. Thus, you will have {max_explore_turn}-1 to explore. For each exploration, you should first analyze by using the tag <think> based on the previous <observation>, and then use <operator> tag to output the next operator.