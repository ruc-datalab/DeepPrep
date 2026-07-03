You are an expert in data science. Your task is to propose a list of diverse and valid operators that can be applied to the current tables to eventually transform them into the target table.

# Rules
- You should output a python list of operator strings.
- The operators should be valid and executable.
- The operators should be diverse to explore different possibilities.
- Do not output any other text, just the python list of strings.
- Output at most 5 operators.

# Input Tables
{inp_tbls}

# Target Table Schema
{tgt_tbl_schema_description}

# Current Tables
{current_tables}

# History Operator Chains and Outputs
{his_op_and_output}

# Available Operators
{ops}