# Role Definition

{role}

# Hint

{system_msg}

# The Processed Task Object

## The Initial Input of the Task

The task is to use operator to transform the initial input table(s) into the target table. 

Initial Input Table:
{inp_tbl}

Target Table Schema Description:
{tgt_tbl}

## The Processing process for completing the task

When completin the task, the agent will use the tag <operator> to explore, and a external executor will execute the operators to return the observation. Finally it will output the solution within the tag <solution> to be evaluated.

{process}

In the above process, the generated solution is evaluated to be wrong, Please analyze the error.

# Current Error Category

{error_category_str}

# Completion

Please analyze the error categories in the task processing process above.

{last_error_if_exist}Remember to follow the format in "#Hint" Section.

Output: 