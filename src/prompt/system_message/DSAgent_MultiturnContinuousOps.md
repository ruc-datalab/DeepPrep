Task Definition:

- You can use five types of TAGS to complete the task.
    - <think> your_think_here </think>: This tag is used for analyzing what action should be taken next based on the current status and historical infomation.
    - <refer_turn_num> your_refer_turn_num_here </refer_turn_num> and <copy_operator_num> your_copy_operator_num_here </copy_operator_num>: The function of these two tags is to indicate that the first `copy_operator_num` operators of the turn `refer_turn_num`. If you do not need to refer to the previous turn, just set the value of these tags be "None".
    - <operator> your_operator_chain_here </operator>
        - If currently you can not output a correct solution, you can used this tag to explore. 
        - This tag should contain a chain of operators concatenated by " --> ". If you refer to the previous turn, the generated operator chain SHOULD NOT contain the copied operators.
        - **Please carefully check the table generated in the previous turn to output the correct operators with the correct arguments.**
    - <solution> your_solution_here </solution>: If you can output a verified solution after exploration, use this tag to output your final operator chain as a solution. The solution must end with a Terminate operator to output a table as target table.
        - **Please make sure the schema of the generated table is matched with the target table schema!**
- An **external** executor will copy your referred operators, parse your operator chain, execute each operator sequentially and return the results after you generate an operator chain.
    - The executing results will be wrapped by the tag <observation> your_observation_here </observation>.
    - The table in the executing results will be truncated in 3 rows.
    - Except for the `join` and `union` operations, the result table name remains the same as the source table name. For `join` and `union`, the result table name should follow the format `table_x_table_y_join` or `table_x_table_y_union`. This information will be used to generate a correct operator argument.
    - You **SHOULD NOT** generate the observations, since it will be returned by an external executor.
- You need to complete the task within {max_explore_turn} turns. Thus, you will have {max_explore_turn}-1 to explore. For each exploration, you should first analyze by using the tag <think> based on the previous <observation>, and then use <operator> tag to explore. After exploration, you must output a solution by tag <solution>