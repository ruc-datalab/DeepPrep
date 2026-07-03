## Demonstration 1

Input Table:

name | age
---|---
"John" | 25
"Jane" | 30
"Mike" | 35

Data Cleaning Operator: [op_replace_tag]

Output:

```python
import pandas as pd

duplicates = input_table.iloc[[0, 2]].copy()
target_df = pd.concat([input_table, duplicates], ignore_index=True)
```

After executing the python code, we get a target_df contain dirty data:

name | age
---|---
"John" | 25
"Jane" | 30
"Mike" | 35
"John" | 25
"Mike" | 35

To restore the original table from the target_df, we can execute the Deduplicate operator: Deduplicate(table_name="input_table", keep="first")

## Demonstration 2

Input Table:

product | price
---|---
"Apple" | 1.0
"Banana" | 0.5
"Orange" | 0.8

Data Cleaning Operator: [op_replace_tag]

Output:

```python
import pandas as pd

# 随机选择若干行
duplicates = input_table.sample(n=3, random_state=42).copy()
target_df = pd.concat([input_table, duplicates], ignore_index=True)
```

After executing the python code, we get a target_df contain dirty data:

product | price
---|---
"Apple" | 1.0
"Banana" | 0.5
"Orange" | 0.8
"Banana" | 0.5
"Banana" | 0.5
"Banana" | 0.5

To restore the original table from the target_df, we can execute the Deduplicate operator: Deduplicate(table_name="input_table", keep="first")
