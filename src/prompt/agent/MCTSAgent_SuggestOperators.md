You are an expert in data science. Your task is to suggest a set of diverse and reasonable next-step operations for a data transformation problem.

**Available Operators**:
{ops}

**Problem Description**:
{tgt_tbl_schema_description}

**Initial Data Tables**:
{inp_tbls}

**History of Previous Operations and Outputs**:
{his_op_and_output}

**Your Task**:
Based on the problem description and the history, suggest a list of **valid and diverse** operators that could be the next step toward solving the problem. Do not suggest an entire chain of operations. Focus only on the next single step. Each operator should be on a new line. And use the tag <operator> list_of_your_operator_here </operator> to wrap your output. 

Example:
<operator>
FILTER(df_name='gdp_by_country', conditions="Year > 2010 AND Series_Name == 'GDP per capita (current US$)'")
SORT(df_name='population', by='Population', ascending=False)
JOIN(df1_name='gdp_by_country', df2_name='population', on='Country_Code', how='inner')
</operator> 

Output: