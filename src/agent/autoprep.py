from src.tools.utils.create_prompt_of_tables import df_to_cotable
from .base_agent import BaseAgent
from src.data import Trial
from src.prompt.prompt_generator import PromptGenerator
from src.tools.utils import parse_any_string, parse_tag_wrapped_string
from src.tools.helper import GPT
from src.module.executor import Executor
from src.physicalop import *
from app.client import ApiClient
import httpx, copy

class LogicalOperator:
    def __init__(self, input_tables: List[str], requirement: str):
        self.input_tables = input_tables
        self.requirement = requirement
    def __str__(self):
        return f'LogicalOperator(input_tables={self.input_tables}, requirement="{self.requirement}")'
    def __repr__(self):
        return self.__str__()

class DataCleaning(LogicalOperator):
    def __str__(self): return f'DataCleaning(input_tables={self.input_tables}, requirement="{self.requirement}")'

class ColumnTransformation(LogicalOperator):
    def __str__(self): return f'ColumnTransformation(input_tables={self.input_tables}, requirement="{self.requirement}")'

class TableTransformation(LogicalOperator):
    def __str__(self): return f'TableTransformation(input_tables={self.input_tables}, requirement="{self.requirement}")'

class CodeGenerationLogicalOperator(LogicalOperator):
    def __str__(self): return f'CodeGenerationLogicalOperator(input_tables={self.input_tables}, requirement="{self.requirement}")'

class TerminateLogicalOperator(LogicalOperator):
    def __str__(self): return f'TerminateLogicalOperator(input_tables={self.input_tables}, requirement="{self.requirement}")'



PLANNER_PROMPT = """

# Logical Operators

You have access to the following logical operators:

{logical_op_registry}

Your task is to generate the next logical operator to tackle the task.

# Hint

- You must output the logical operator wrapped in XML tags: <logical_operator> ... </logical_operator>.
- Do not output Python code directly. Only output **ONE** next logical step.
- Output **one** logical operator at a time, the logical operator will be passed to the programmer agent to implement and implemented results will be passed back in the <observation> ... </observation> tags.

# Demonstrations
Here are examples of how to map requirements to logical operators:

## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | b1 | B-52 Bomber | f14 | F-17 Fighter | pc
---|---|---|---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"

Target Table Schema Description:
We transform the input tables to complete the task: The task aims to count the number of distinct plane names associated with any pilot from the input table that includes pilot details and their plane-related attributes.
The column schema of the target table is as follows:
- Name of Column: "count(DISTINCT plane_name)"
  - Description: The total number of unique plane names that appear across all pilots in the input data, reflecting the distinct types of planes referenced for any pilot.
  - Requirements
    - Single non-negative integer value
    - Represents the count of unique plane names across all pilots

<logical_operator> TableTransformation(input_table=["table_1"], requirement="Please first transform the input table to a wide format with columns: pilot_name, attribute, plane_name, age_value") </logical_operator>
<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"
</observation>

<logical_operator> DataCleaning(input_tables=["table_1"], requirement="Please clean the table_1, including removing the quotes, standardize string to numerical, drop out null age_values, and deduplicate the rows where the plane_name is the same.") </logical_operator>
<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"
</observation>

<logical_operator> TableTransformation(input_tables=["table_1"], requirement="Please calculate the count of distinct plane names and select only the value column.") </logical_operator>
<observation> 
Name: "statistic_table"
value
---
5
</observation>

<logical_operator> DataCleaning(input_tables=["statistic_table"], requirement="Rename the column 'value' to 'count(DISTINCT plane_name)'") </logical_operator>
<observation> 
Name: "statistic_table"
count(DISTINCT plane_name)
---
5
</observation>

<logical_operator> TerminateLogicalOperator(input_tables=["statistic_table"], requirement="Terminate the process and specify the final output tables as `statistic_table`.") </logical_operator>
<observation> 
You have completed the task and output a table named "statistic_table".
</observation>

# Initial Input Tables

{inp_tbls}

# Target Table Schema

{tgt_tbl_schema_description}

Please generate the next logical operator:
"""


PROGRAMMER_DATA_CLEANING_SYS_PROMPT = '''
# Role Definition
You are a **Data Cleaning Programmer**. Your goal is to translate a specific data cleaning requirement into a sequence of **Physical Operators**.

# Operator Space

{ops}

# Hint
- Output the plan wrapped in XML tags: <physical_operator> ... </physical_operator>.
- Use `-->` to represent the execution order if multiple operators are required.
- Do not output Python code directly unless it's inside the `func` argument of an operator.

# Demonstrations
Here are examples of how to map cleaning requirements to physical operators:

## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0

Requirement: Please clean the table_1, including removing the quotes, standardize string to numerical, drop out null age_values, and deduplicate the rows where the plane_name is the same.

<physical_operator> CastType(table_name="table_1", column="age_value", dtype="str") --> StandardizeString(table_name="table_1", column_name="age_value", func="""def transform(s): s = s.strip('"'); if s.lower() == 'nan': return ''; return s""") --> CastType(table_name="table_1", column="age_value", dtype="float") --> DropNull(table_name="table_1", columns=["age_value"]) --> Deduplicate(table_name="table_1", subset=["plane_name"], keep="first") </physical_operator>

<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0
...... 
</observation>

## Demonstration 2

Input Table:
Name: "statistic_table"
value
---
5

Requirement: Rename the column 'value' to 'count(DISTINCT plane_name)'.

<physical_operator> Rename(table_name="statistic_table", rename_map=[{{"old_name": "value", "new_name": "count(DISTINCT plane_name)"}}]) </physical_operator>

<observation> 
Name: "statistic_table"
count(DISTINCT plane_name)
---
5
</observation>'''.strip()

PROGRAMMER_DATA_CLEANING_USER_PROMPT='''
# Current Task

Input Tables:

{input_tables}

Cleaning Requirement: {requirement}

Please generate the physical operators:
'''.strip()

PROGRAMMER_COLUMN_TRANSFORMATION_SYS_PROMPT = '''
# Role Definition

You are a **Column Transformation Programmer**. Your goal is to translate a specific column transformation requirement (renaming, selecting, or simple arithmetic) into a sequence of **Physical Operators**.

# Operator Space

{ops}

# Hint

- Output the plan wrapped in XML tags: <physical_operator> ... </physical_operator>.
- Use `-->` to represent the execution order if multiple operators are required.
- Do not output Python code directly unless it's inside the `func` argument of an operator.

# Demonstrations
Here are examples of how to map column requirements to physical operators:

## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"smith" | "age" | "b1" | 41.0
"silson" | "age" | "b1" | 52.0
"silson" | "age" | "b1" | 52.0

Requirement: Please standardize the pilot_name to uppercase.

<physical_operator> StandardizeString(table_name="table_1", column_name="pilot_name", func="""def transform(s): return s.upper()""") </physical_operator>

<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"SMITH" | "age" | "b1" | 41.0
"SILSON" | "age" | "b1" | 52.0
"SILSON" | "age" | "b1" | 52.0
...... 
</observation>'''.strip()

PROGRAMMER_COLUMN_TRANSFORMATION_USER_PROMPT='''

# Current Task

Input Tables:

{input_tables}

Transformation Requirement: {requirement}

Please generate the physical operators:
'''.strip()

PROGRAMMER_TABLE_TRANSFORMATION_SYS_PROMPT = '''
# Role Definition
You are a **Table Transformation Programmer**. Your goal is to translate a specific table transformation requirement (reshaping, aggregation, joining) into a sequence of **Physical Operators**.

# Operator Space

{ops}

# Hint

- Output the plan wrapped in XML tags: <physical_operator> ... </physical_operator>.
- Use `-->` to represent the execution order if multiple operators are required.
- Do not output Python code directly unless it's inside the `func` argument of an operator.

# Demonstrations
Here are examples of how to map table transformation requirements to physical operators:

## Demonstration 1

Input Table:
Name: "table_1"
pilot_name | attribute | b1 | B-52 Bomber | f14 | F-17 Fighter | pc
---|---|---|---|---|---|---
"Celko" | "age" | nan | nan | nan | nan | ""23.0""
"Higgins" | "age" | nan | 34.0 | 50.0 | nan | ""30.0""
"Jones" | "age" | nan | 24.0 | 32.0 | nan | "nan"
"Smith" | "age" | 41.0 | 26.0 | 45.0 | nan | "nan"
"Wilson" | "age" | 52.0 | 34.0 | 24.0 | 35.0 | "nan"

Requirement: Please first transform the input table to a wide format with columns: pilot_name, attribute, plane_name, age_value

<physical_operator> Stack(table_name="table_1", id_vars=["pilot_name", "attribute"], value_vars=["b1", "B-52 Bomber", "f14", "F-17 Fighter", "pc"], var_name="plane_name", value_name="age_value") </physical_operator>

<observation> 
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0
...... 
</observation>

## Demonstration 2

Input Table:
Name: "table_1"
pilot_name | attribute | plane_name | age_value
---|---|---|---
"Smith" | "age" | "b1" | 41.0
"Wilson" | "age" | "b1" | 52.0
"Wilson" | "age" | "b1" | 52.0

Requirement: Please calculate the count of distinct plane names and select only the value column.

<physical_operator> CalculateStatistic(table_name="table_1", statistic_name="count(DISTINCT plane_name)", func="""def calculate_stat(df: pd.DataFrame): return len(df)""") --> SelectCol(table_name="statistic_table", columns=["value"]) </physical_operator>

<observation> 
Name: "statistic_table"
value
---
5
</observation>'''.strip()

PROGRAMMER_TABLE_TRANSFORMATION_USER_PROMPT='''

# Current Task

Input Tables:

{input_tables}

Transformation Requirement: {requirement}

Please generate the physical operators:
'''.strip()

PROGRAMMER_CODE_GENERATION_SYS_PROMPT = '''
# Role Definition
You are a **Code Generation Programmer**. Your goal is to translate a specific code generation requirement into a sequence of **Physical Operators**.

# Operator Space

{ops}

# Hint

- Output the plan wrapped in XML tags: <physical_operator> ... </physical_operator>.
- This programmer requires to generate python code within the operator. Please follow the format of the this operator.

# Demonstrations

## Demonstration 1

Input Table:
Name: "table_1"
ID | "35" | "35" | "35" | "35" | "35" | "35" | "35" | "35" | "35" | "35" | "35" | "56" | "56" | "56" | "56" | "56" | "56" | "56" | "56" | ...
---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|--- | ...
"course_id" | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 366 | 400 | 426 | 468 | 493 | 642 | 702 | 735 | 760 | 893 | 962 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | 105 | 237 | 242 | 345 | 400 | 400 | 443 | 561 | 581 | 612 | 791 | 795 | 852 | 960 | 972 | 974 | ...
"sec_id" | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | ...
"semester" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Fall" | "Spring" | "Spring" | "Spring" | "Fall" | "Spring" | "Fall" | ...
"grade_2001" | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | nan | "A-" | nan | nan | nan | nan | nan | nan | nan | nan | nan | 
......
[Truncated due to length]

Requirement: Please clean the table_1, including removing the quotes, standardize string to numerical, drop out null age_values, and deduplicate the rows where the plane_name is the same.

<physical_operator> CodeGeneration(table_names=['table_1'], target_table="restructured_table", func="""
import pandas as pd
def process_tables(table_1: pd.DataFrame):
    # Set index to 'ID' column
    df = table_1.set_index('ID')
    # Transpose the dataframe
    df_transposed = df.T
    # Reset index to turn original column headers into a column
    df_transposed = df_transposed.reset_index()
    # Rename the new column to 'student_id'
    df_transposed = df_transposed.rename(columns={'index': 'student_id'})
    return df_transposed
""") </physical_operator>

<observation> 
Table Name: "restructured_table"
Table Data:
student_id | course_id | sec_id | semester | grade_2001 | grade_2002 | grade_2003 | grade_2004 | grade_2005 | grade_2006 | ...
---|---|---|---|---|---|---|---|---|--- | ...
""35"" | 366 | 1 | "Fall" | nan | nan | nan | nan | "A " | nan | ...
""35"" | 400 | 2 | "Fall" | nan | nan | "C-" | nan | nan | nan | ...
""35"" | 426 | 1 | "Spring" | nan | nan | nan | nan | nan | "C-" | ...
......
</observation>'''.strip()

PROGRAMMER_CODE_GENERATION_USER_PROMPT='''

# Current Task

Input Tables:

{input_tables}

Requirement: {requirement}

Please generate the physical operators:
'''.strip()

class PlannerAgent(BaseAgent):
    def __init__(self, name: str='Planner Agent', cfg=None, log_file='_MAIN', planner_resgistry: dict=None):
        """
        Args:
            name: The name of the planner agent.
            cfg: The configuration of the planner agent.
            log_file: The file to log the planner agent.
            planner_resgistry: A dictionary that contains the programmer agents that the planner agent can use.
                - programmer_name: The name of the programmer agent.
        """
        super().__init__(name, cfg, log_file)
        self.llm = GPT(self.cfg)
        self.mode = self.cfg.get('execute_mode')
        self.planner_resgistry = planner_resgistry
        self.MAX_LOGICAL_OPERATOR_CNT = 10

    def initialize_message(self, trial: Trial):
        inp_tbls = trial.serialize_input_tables()
        tgt_tbl_schema_description = Trial.generate_schema_description(task=trial.task)
        system_message = """
# Role Definition
You are a **high-level** Data Preparation Planner. Your goal is to analyze the user's requirement and the schema of input tables, then construct a high-level plan using a sequence of Logical Operators."""

        logical_op_registry = []
        for logical_op_name, logical_op_features in self.planner_resgistry.items():
            description, signature = logical_op_features['description'], logical_op_features['signature']
            logical_op_registry.append(f'{logical_op_name}: {description}')
            logical_op_registry.append(f'- Signature: {signature}')
            related_phy_ops = logical_op_features['operators']
            related_phy_ops_str = ', '.join([op.__name__ for op in related_phy_ops])
            logical_op_registry.append(f'- Related Physical Operators (These operators can not be directly output by the Planner agent): {related_phy_ops_str}')
        logical_op_registry_str = '\n'.join(logical_op_registry)

        user_message = PLANNER_PROMPT.format(inp_tbls=inp_tbls, tgt_tbl_schema_description=tgt_tbl_schema_description, logical_op_registry=logical_op_registry_str)
        messages = []
        messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        return messages

    def step(self, trial: Trial, messages: List[dict]): # output a logical operator
        self._clear_state()
        self.MAX_ERR_CNT = 3
        cur_messages = copy.deepcopy(messages)
        while True:
            try:
                out, logical_op_obj = self._step(trial, cur_messages)
                return out, logical_op_obj
            except Exception as e:
                self._raise_error(e)
                cur_messages.append({"role": "user", "content": f"Error Raised: {e}. Please retry to avoid the error."})

    def _step(self, trial: Trial, messages: List[dict]):
        self.logger.log_messages(messages)
        out = self.llm.query(messages)
        self.logger.log(out)
        logical_operator = parse_tag_wrapped_string(rsp=out, tag='logical_operator', hard_replace=['your_logical_operator_here'])
        logical_op_obj = eval(logical_operator)
        return out, logical_op_obj

class ProgrammerAgent(BaseAgent):
    def __init__(self, name: str = 'Programmer Agent', cfg=None, log_file='_MAIN', programmer_resgistry: dict = None):
        """
        Args:
            programmer_resgistry: A dictionary containing 'operators' (list of classes) and descriptions.
        """
        super().__init__(name, cfg, log_file)
        self.llm = GPT(self.cfg)
        self.executor = Executor(self.cfg)
        self.programmer_resgistry = programmer_resgistry
        self.tol_ops = programmer_resgistry['operators']
        self.tol_ops_str = '\n\n'.join([op.get_action_description().strip() for op in self.tol_ops])

    def initialize_message(self, trial: Trial, logical_operator: LogicalOperator):
        input_tbl_names = logical_operator.input_tables
        input_tbl_eles = []
        for tbl_name in input_tbl_names:
            input_tbl_eles.append(f'Table name: {tbl_name}')
            tbl = trial.tables[tbl_name]
            input_tbl_eles.append(df_to_cotable(tbl))
            input_tbl_eles.append('')
        input_tbl_eles_str = '\n'.join(input_tbl_eles)
        requirement = logical_operator.requirement

        sys_prompt_template, user_prompt_template = None, None
        if isinstance(logical_operator, DataCleaning): 
            sys_prompt_template = PROGRAMMER_DATA_CLEANING_SYS_PROMPT
            user_prompt_template = PROGRAMMER_DATA_CLEANING_USER_PROMPT
        elif isinstance(logical_operator, ColumnTransformation): 
            sys_prompt_template = PROGRAMMER_COLUMN_TRANSFORMATION_SYS_PROMPT
            user_prompt_template = PROGRAMMER_COLUMN_TRANSFORMATION_USER_PROMPT
        elif isinstance(logical_operator, TableTransformation): 
            sys_prompt_template = PROGRAMMER_TABLE_TRANSFORMATION_SYS_PROMPT
            user_prompt_template = PROGRAMMER_TABLE_TRANSFORMATION_USER_PROMPT
        elif isinstance(logical_operator, CodeGenerationLogicalOperator): 
            sys_prompt_template = PROGRAMMER_CODE_GENERATION_SYS_PROMPT
            user_prompt_template = PROGRAMMER_CODE_GENERATION_USER_PROMPT
        else: raise Exception(f'Invalid logical operator: {logical_operator}')
        messages = []
        messages.append({"role": "system", "content": sys_prompt_template.format(ops=self.tol_ops_str)})
        messages.append({"role": "user", "content": user_prompt_template.format(input_tables=input_tbl_eles_str, requirement=requirement)})
        return messages


    def step(self, trial: Trial, logical_operator: LogicalOperator): # output a chain of physical operators
        self._clear_state()
        self.MAX_ERR_CNT = 5
        cur_messages = self.initialize_message(trial, logical_operator)
        while True:
            try:
                out = None
                out, physical_op_objs, generated_tbl, tmp_trial = self._step(trial, logical_operator, cur_messages)
                return out, physical_op_objs, generated_tbl, tmp_trial
            except Exception as e:
                self._raise_error(e)
                if out is not None: cur_messages.append({"role": "assistant", "content": out})
                cur_messages.append({"role": "user", "content": f"Error Raised: {e}. Please retry to avoid the error."})

    def _get_physical_op_objs(self, trial, logical_operator, messages: List[dict]):
        self.logger.log_messages(messages)
        out = self.llm.query(messages)
        self.logger.log(out)
        physical_operator_str = parse_tag_wrapped_string(rsp=out, tag='physical_operator', hard_replace=['your_physical_operator_here'])
        physical_op_objs = []
        for physical_operator_str in physical_operator_str.split('-->'):
            if physical_operator_str.strip() == '': continue
            try:
                cur_op_obj = auto_parse_op(physical_operator_str)
                physical_op_objs.append(cur_op_obj)
            except Exception as e:
                raise Exception(f"Error Parsing Physical Operator: {physical_operator_str}. Please output the correct operator name and arguments.")
        return out, physical_op_objs

    def _execute_physical_op_objs(self, trial, physical_op_objs):
        tmp_trial = copy.deepcopy(trial)
        generated_tbl = {}
        for physical_op_obj in physical_op_objs:
            try:
                out_tblname, df = self.executor.execute_op(physical_op_obj, tmp_trial)
                if df.empty or len(df) == 0:
                    raise ValueError(f'The output table is empty after executing operator!')
                _ = self.executor.step_op(physical_op_obj, tmp_trial, out_tblname, df)
                generated_tbl[out_tblname] = df
            except Exception as e:
                raise Exception(f"Error Executing Physical Operator: {physical_op_obj} with error: {e}")
        return generated_tbl, tmp_trial

    def _step(self, trial, logical_operator, messages: List[dict]):
        out, physical_op_objs = self._get_physical_op_objs(trial, logical_operator, messages)
        generated_tbl, tmp_trial = self._execute_physical_op_objs(trial, physical_op_objs)
        return out, physical_op_objs, generated_tbl, tmp_trial
