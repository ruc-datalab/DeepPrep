You are dealing with a complex task with multiple rounds of interaction, don't try to complete it in one step.

- Output with tags below to answer the question.
    - <think> your_think_here </think>: This tag is used for analyzing what action should be taken next.
    - <operator> your_operator_chain_here </operator> or <solution> your_operator_chain_here </solution>
        - The operator chain are concatenated by " --> ", which will be executed by an external executor.
        - Please first use the <operator> tag to fully explore. During exploration, you can split the complicated task into multiple sub-tasks. Thus, you only need to generate several new operators at one turn. As shown in the demonstration, we only generate part of the operator chain at one turn.
        - If previous exploration results can deduce a correct operator chain to get the target table or it is the last turn, use the <solution> tag to summarize the correct operator chain. Output your final solution with operators used in the previous exploration. The solution must end with a Terminate operator.
        - IMPORTANT!: **For each turn, when generate operator chain, please generate from generate from scratch. You can refer to previous generated operator and execution results, but our system will not cache these execution results and assume the previous generated operators were executed.**
- Other Tips:
    - The table in the executing results will be truncated. Thus, when filtering the record, try to adopt multi-step fuzzy filtering to ensure the correctness of the filtering.
    - Carefully check the generated table with the target table schema description. DO NOT output redundant columns.
    - For most operators, the result table name remains the same as the source table name. For `join` and `union`, the result table name should follow the format `table_x_table_y_join` or `table_x_table_y_union`. 
    - **DO NOT** Generate the <observation> tag! **DO NOT** Generate the <observation> tag! **DO NOT** Generate the <observation> tag! Because the execution results will be given by an external executor.
- The capabilities you should have:
    - You should have the ability to effectively explore the operator space to find the correct operator chain.
    - You should have the ability to correct the previous wrong operator in the new exploration.
    - You should have the ability to examine the execution results to determine whether a correct target table is generated to determine whether a correct operator chain is found.

You will have {max_explore_turn} to explore. For each exploration, you should first reflect with the tag <think> based on the previous <observation>, and then use <operator> tag to explore. After exploration, you must output a solution with tag <solution>. Make sure all operators in the <solution> can be executed successfully.