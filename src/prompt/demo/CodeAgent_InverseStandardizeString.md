## Demonstration 1

Input Table:

cyclist | year | time
---|---|---|---
"John Doe (USA)" | 2023 | 100
"Jane Smith (UK)" | 2023 | 120
"Mike Johnson (USA)" | 2023 | 130

Data Cleaning Operator: [op_replace_tag]

Output:

```python
import random

def get_name_and_country(cyclist):
    name, country = cyclist.split('(')
    country = country.strip(')')
    name, country = name.strip(), country.strip()
    return name, country

def transform_func(name, country):
    return f"{name}-{country}"

target_df = input_table.copy()

func_ratio = 0.1
for i in range(len(target_df)):
    if random.random() < func_ratio:
        name, country = get_name_and_country(target_df['cyclist'][i])
        target_df['cyclist'][i] = transform_func(name, country)
    else:
        target_df['cyclist'][i] = target_df['cyclist'][i]

```

After executing the python code, we get a target_df contain dirty data:

cyclist | year | time
---|---|---
"John Doe (USA)" | 2023 | 100
"Jane Smith(UK)" | 2023 | 120
"Mike Johnson-USA" | 2023 | 130

To restore the original table from the target_df, we can execute the StandardizeString operator: StandardizeString(table_name="input_table", column_name="cyclist", func="""
possible_modes = [r"(\w+)\s*\((\w+)\)", r"(\w+)\s*\[(\w+)\]""]

def transform_func(cyclist):
    for mode in possible_modes:
        match = re.match(mode, cyclist)
        if match:
            cyclist, country = match.group(1), match.group(2)
            return f"{cyclist} ({country})"
    return cyclist

target_df = input_table.copy()

for i in range(len(target_df)):
    name, country = transform_func(target_df['cyclist'][i])
    target_df['cyclist'][i] = f"{name} ({country})"

""")

