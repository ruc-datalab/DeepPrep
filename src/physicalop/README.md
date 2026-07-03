# How to add a new operator

To add a new operator, you need to follow two main steps: defining the operator and implementing its execution logic.

## Step 1: Define and Register the Operator

### 1.1 Define the Operator Class
In `src/physicalop/data_transform.py`, define a new class for your operator. This class should inherit from `BaseOp` and use the `@dataclass` decorator.

You need to define:
- `action_type`: A unique string identifier for the operator.
- Fields: The parameters required for the operator.
- `get_action_description`: A class method that returns the description of the operator (signature and description).

**Example:**
```python
@dataclass
class MyNewOp(BaseOp):
    action_type: str = field(
        default="my_new_op",
        init=False,
        repr=False,
        metadata={"help": 'type of action'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    param1: str = field(metadata={"help": 'description of param1'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: MyNewOp(table_name: str, param1: str)
* Description: Description of what this operator does.
""".strip()
        # You can also implement json_format if needed, similar to other ops
        op_definition = eval(FORMAT_TYPE)
        return op_definition
```

### 1.2 Register the Operator
In `src/physicalop/__init__.py`, import your new operator class and add it to the appropriate list (e.g., `DATA_CLEANING_OPS`, `COLUMN_TRANSFORMATION_OPS`, or `TABLE_TRANSFORMATION_OPS`) so it can be discovered.

**Example:**
```python
from .data_transform import MyNewOp

# Add to the relevant list
TABLE_TRANSFORMATION_OPS = [
    ...,
    MyNewOp
]
```

## Step 2: Implement Execution Logic

In `src/module/executor.py`, you need to implement how the operator actually transforms the data.

### 2.1 Add Execution Method
Add a method to the `RuleExecutor` class that takes the operator instance and the current state (usually `input_tables`) as input, performs the transformation, and returns the result.

**Example:**
```python
    def execute_my_new_op(self, op: MyNewOp, input_tables: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        df = input_tables[op.table_name].copy()
        # Perform transformation using op.param1
        # ...
        return df
```

### 2.2 Register in Function Mapper
In the `__init__` method of `RuleExecutor`, add your operator class and its corresponding execution method to `self.function_mapper`.

**Example:**
```python
        self.function_mapper = {
            ...,
            MyNewOp: self.execute_my_new_op,
        }
```

# To Evaluate on Buildings Dataset

If you want to evaluate DeepPrep on Buildings dataset, please use the operator defined in `AUTOPIPELINE_OP` and use the prompt `src/prompt/system_message/MultiturnAgent_MultiturnOps_Buildings.md` and `src/prompt/demo/MultiturnAgent_AutoPipeline.md`.