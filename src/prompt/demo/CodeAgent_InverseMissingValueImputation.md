## Demonstration 1

Input Table:

name | age
---|---
"John" | 25
"Jane" | 25
"Mike" | 35
"Mia" | 25
"Tom" | 25

Data Cleaning Operator: [op_replace_tag]

Output:

```python
import numpy as np

target_df = input_table.copy()
target_df.loc[0, 'age'] = np.nan
```

After executing the python code, we get a target_df contain dirty data:

name | age
---|---
"John" | NaN
"Jane" | 25
"Mike" | 35
"Mia" | 25
"Tom" | 25

To restore the original table from the target_df, we can execute the MissingValueImputation operator: MissingValueImputation(table_name="input_table", column_name="age", mode="mode")
