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
import numpy as np

extra_rows = pd.DataFrame({
    'name': ["Alice", "Bob"],
    'age': [np.nan, np.nan]
})

target_df = pd.concat([input_table, extra_rows], ignore_index=True)
```

After executing the python code, we get a target_df contain dirty data:

name | age
---|---
"John" | 25
"Jane" | 30
"Mike" | 35
"Alice" | NaN
"Bob" | NaN

To restore the original table from the target_df, we can execute the DropNulls operator: DropNulls(table_name="input_table", subset=["age"], how="any")

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
import numpy as np

extra_rows = pd.DataFrame({
    'product': [np.nan, "Pear"],
    'price': [0.7, np.nan]
})

target_df = pd.concat([input_table, extra_rows], ignore_index=True)
```

After executing the python code, we get a target_df contain dirty data:

product | price
---|---
"Apple" | 1.0
"Banana" | 0.5
"Orange" | 0.8
NaN | 0.7
"Pear" | NaN

To restore the original table from the target_df, we can execute the DropNulls operator: DropNulls(table_name="input_table", how="any")
