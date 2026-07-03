## Demonstration 1

Input Table:

name | salary
---|---
"John" | 50000
"Jane" | 60000
"Mike" | 55000

Data Cleaning Operator: [op_replace_tag]

Output:

```python
import pandas as pd

extra_rows = pd.DataFrame({
    'name': ["Alice", "Bob"],
    'salary': [10000000, 100]
})

target_df = pd.concat([input_table, extra_rows], ignore_index=True)
```

After executing the python code, we get a target_df contain dirty data:

name | salary
---|---
"John" | 50000
"Jane" | 60000
"Mike" | 55000
"Alice" | 100000
"Bob" | 1000

To restore the original table from the target_df, we can execute the OutlierDetection operator: OutlierDetection(table_name="input_table", column_name="salary", action="delete")
