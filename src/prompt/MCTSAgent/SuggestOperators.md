You are an expert in data science. Your task is to suggest a set of diverse and reasonable next-step operations for a data transformation problem.

**Problem Description**:
{tgt_tbl_schema_description}

**Initial Data Tables**:
{inp_tbls}

**History of Previous Operations and Outputs**:
{his_op_and_output}

**Available Operators**:
{ops}

**Your Task**:
Based on the problem description and the history, suggest a list of **single, valid, and diverse** operators that could be the next step toward solving the problem. Each operator should be on a new line.
Do not suggest an entire chain of operations. Focus only on the next single step.
Wrap your suggestions in an <operator> tag. Each operator should be on a new line.

Example:
<operator>
FILTER(df_name='gdp_by_country', conditions="Year > 2010 AND Series_Name == 'GDP per capita (current US$)'")
SORT(df_name='population', by='Population', ascending=False)
JOIN(df1_name='gdp_by_country', df2_name='population', on='Country_Code', how='inner')
</operator> 