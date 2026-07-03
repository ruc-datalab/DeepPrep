You are an expert in data science. Your task is to select the best next operation to perform and define its parameters to solve a data transformation problem.

**Problem Description**:
{tgt_tbl_schema_description}

**Initial Data Tables**:
{inp_tbls}

**History of Previous Operations and Outputs**:
{his_op_and_output}

**Available Operator Types**:
{ops}

**Your Task**:
Based on the problem description and the history, choose the **single best operator type** from the list of available types to apply next. Then, provide the full, executable operator with all its parameters correctly filled.

Wrap your response in an <operator> tag.

Example:
<operator>
FILTER(df_name='gdp_by_country', conditions="Year > 2010 AND Series_Name == 'GDP per capita (current US$)'")
</operator> 