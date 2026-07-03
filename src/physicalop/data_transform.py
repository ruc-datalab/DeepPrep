from ._base import BaseOp
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Union
import re,json

FORMAT_TYPE = 'base_format'
# FORMAT_TYPE = 'json_format'

@dataclass
class Filter(BaseOp):
    action_type: str = field(
        default="filter",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "filter"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    func: str = field(metadata={"help": 'filter function'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: Filter(table_name: str, func: str)
* Description: Filter rows based on a function. The function input with a pd.Series object and output a boolean value. If output True, the row will be kept; otherwise, the row will be filtered out.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "Filter",
                    "description": "Filter rows based on a function. The function input with a pd.Series object and output a boolean value. If output True, the row will be kept; otherwise, the row will be filtered out.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "name of the table to apply the operation on"
                            },
                            "func": {
                                "type": "string",
                                "description": "filter function in python code"
                            }
                        },
                        "required": ["table_name", "func"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Filter Definition

{op_definition}

* Example: 
Input Table: "my_table"
id | age | name
---|---|---
1 | 20 | John
2 | 25 | Jane
...

Executing the operator: Filter(table_name="my_table", func=\"\"\"
def filter_func(row: pd.Series) -> bool: 
    return row['age'] > 18 and row['name'] == 'John'
\"\"\")

Output Table: "my_table"
id | age | name
---|---|---
1 | 20 | John
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Filter\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_name=table_name, func=func)
        return None

    def __repr__(self) -> str:
        table_name = self.table_name.replace('"', '\\"')
        func = self.func.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{table_name}", func="""{func}""")'

@dataclass
class Sort(BaseOp):
    action_type: str = field(
        default="sort",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "sort"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    by: List[str] = field(metadata={"help": 'columns to sort by'})
    ascending: List[bool] = field(metadata={"help": 'sort direction for each column'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: Sort(table_name: str, by: List[str], ascending: List[bool])
* Description: Sort rows based on specified columns and directions.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "Sort",
                    "description": "Sort rows based on specified columns and directions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "name of the table to apply the operation on"
                            },
                            "by": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "columns to sort by"
                            },
                            "ascending": {
                                "type": "array",
                                "items": {"type": "boolean"},
                                "description": "sort direction for each column"
                            }
                        },
                        "required": ["table_name", "by", "ascending"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Sort Definition

{op_definition}

* Example: 

Input Table: "my_table"
id | age | name
---|---|---
1 | 20 | John
2 | 25 | Jane
...

Executing the operator: Sort(table_name="my_table", by=["age", "name"], ascending=[False, True])

Output Table: "my_table"
id | age | name
---|---|---
1 | 18 | Koby
2 | 18 | Lucy
...
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Sort\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*by\s*=\s*(.*?)\s*,\s*ascending\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, by_str, ascending_str = matches[-1]
            table_name = table_name.strip().strip("'\"")
            by = eval(by_str.strip())
            if isinstance(by, list):
                by = [str(b) for b in by]
            ascending = eval(ascending_str.strip())
            return cls(table_name=table_name, by=by, ascending=ascending)
        return None

    def __repr__(self) -> str:
        table_name = self.table_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{table_name}", by={self.by}, ascending={self.ascending})'

@dataclass
class Pivot(BaseOp):
    action_type: str = field(
        default="pivot",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "pivot"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    index: Union[str, List[str]] = field(metadata={"help": 'index column'})
    columns: str = field(metadata={"help": 'columns to pivot'})
    values: str = field(metadata={"help": 'values to aggregate'})
    aggfunc: str = field(metadata={"help": 'aggregation function'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: Pivot(table_name: str, index: Union[str, List[str]], columns: str, values: str, aggfunc: str)
* Description: Pivot table based on specified columns and aggregation function.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "Pivot",
                    "description": "Pivot table based on specified columns and aggregation function.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "name of the table to apply the operation on"
                            },
                            "index": {
                                "type": ["string", "array"],
                                "items": {"type": "string"},
                                "description": "index column"
                            },
                            "columns": {
                                "type": "string",
                                "description": "columns to pivot"
                            },
                            "values": {
                                "type": "string",
                                "description": "values to aggregate"
                            },
                            "aggfunc": {
                                "type": "string",
                                "description": "aggregation function"
                            }
                        },
                        "required": ["table_name", "index", "columns", "values", "aggfunc"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Pivot Definition

{op_definition}

* Example: 
date | category | sales
---|---|---
"2023-01-01" | "Clothing" | 300
"2023-01-01" | "Electronics" | 13000
"2023-01-02" | "Clothing" | 750
"2023-01-02" | "Electronics" | 4500
...

Executing the operator: Pivot(table_name="my_table", index="date", columns="category", values="sales", aggfunc="sum")

Output Table: "my_table"
date | Clothing | Electronics
---|---|---
"2023-01-01" | 300 | 13000
"2023-01-02" | 750 | 4500
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Pivot\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*index\s*=\s*(.*?)\s*,\s*columns\s*=\s*(.*?)\s*,\s*values\s*=\s*(.*?)\s*,\s*aggfunc\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, index, columns, values, aggfunc = (item.strip().strip("'\"") for item in matches[-1])
            columns = str(columns)
            return cls(table_name=table_name, index=index, columns=columns, values=values, aggfunc=aggfunc)
        return None

    def __repr__(self) -> str:
        if isinstance(self.index, str):
            index, columns, values = self.index.replace('"', '\\"'), self.columns.replace('"', '\\"'), self.values.replace('"', '\\"')
            return f'{self.__class__.__name__}(table_name="{self.table_name}", index="{index}", columns="{columns}", values="{values}", aggfunc="{self.aggfunc}")'
        else:
            return f'{self.__class__.__name__}(table_name="{self.table_name}", index={self.index}, columns="{self.columns}", values="{self.values}", aggfunc="{self.aggfunc}")'

@dataclass
class Join(BaseOp):
    action_type: str = field(
        default="join",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "join"'}
    )
    left_table: str = field(metadata={"help": 'left table name'})
    right_table: str = field(metadata={"help": 'right table name'})
    left_on: str = field(metadata={"help": 'left table join column'})
    right_on: str = field(metadata={"help": 'right table join column'})
    how: str = field(metadata={"help": 'join type'})
    suffixes: List[str] = field(metadata={"help": 'suffixes for duplicate columns'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: Join(left_table: str, right_table: str, left_on: str, right_on: str, how: str, suffixes: List[str])
* Description: Join two tables based on specified columns and join type.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "Join",
                    "description": "Join two tables based on specified columns and join type.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "left_table": {
                                "type": "string",
                                "description": "left table name"
                            },
                            "right_table": {
                                "type": "string",
                                "description": "right table name"
                            },
                            "left_on": {
                                "type": "string",
                                "description": "left table join column"
                            },
                            "right_on": {
                                "type": "string",
                                "description": "right table join column"
                            },
                            "how": {
                                "type": "string",
                                "description": "join type"
                            },
                            "suffixes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "suffixes for duplicate columns"
                            }
                        },
                        "required": ["left_table", "right_table", "left_on", "right_on", "how", "suffixes"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Join Definition

{op_definition}

* Example: 

Input Table: "users"
user_id | name
---|---
1 | John
2 | Jane
...

Input Table: "orders"
order_id | user_id | amount
---|---|---
1 | 1 | 100
2 | 2 | 200
...

Executing the operator: Join(left_table="users", right_table="orders", left_on="user_id", right_on="user_id", how="left", suffixes=["_user", "_order"])

Output Table: "users_orders_join"
user_id | name | order_id | amount
---|---|---|---
1 | John | 1 | 100
2 | Jane | 2 | 200
...
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        op = eval(text)
        if op.left_on == op.right_on:
            if len(op.suffixes) != 2:
                raise ValueError(f"The suffixes must have two elements. But got {op.suffixes}")
            if op.suffixes[0] == op.suffixes[1]:
                raise ValueError(f"The suffixes must have two different elements. But got {op.suffixes}")
        return op
        pattern = r'Join\s*\(\s*left_table\s*=\s*(.*?)\s*,\s*right_table\s*=\s*(.*?)\s*,\s*left_on\s*=\s*(.*?)\s*,\s*right_on\s*=\s*(.*?)\s*,\s*how\s*=\s*(.*?)\s*,\s*suffixes\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            left_table, right_table, left_on, right_on, how, suffixes_str = (item.strip() for item in matches[-1])
            
            # Strip quotes from string arguments
            left_table = left_table.strip("'\"")
            right_table = right_table.strip("'\"")
            left_on = left_on.strip("'\"")
            right_on = right_on.strip("'\"")
            how = how.strip("'\"")

            # Clean up and evaluate the suffixes argument
            if suffixes_str.endswith(')'):
                suffixes_str = suffixes_str[:-1]

            suffixes = list(eval(suffixes_str))
            return cls(left_table=left_table, right_table=right_table, left_on=left_on, right_on=right_on, how=how, suffixes=suffixes)
        return None

    def __repr__(self) -> str:
        left_on, right_on = self.left_on.replace('"', '\\"'), self.right_on.replace('"', '\\"')
        return f'{self.__class__.__name__}(left_table="{self.left_table}", right_table="{self.right_table}", left_on="{left_on}", right_on="{right_on}", how="{self.how}", suffixes={self.suffixes})'

@dataclass
class GroupBy(BaseOp):
    action_type: str = field(
        default="groupby",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "groupby"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    by: List[str] = field(metadata={"help": 'columns to group by'})
    agg: List[Dict[str, str]] = field(metadata={"help": 'aggregation specifications'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: GroupBy(table_name: str, by: List[str], agg: List[Dict[str, str]])
* Description: Group data by specified columns and apply aggregations.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "GroupBy",
                    "description": "Group data by specified columns and apply aggregations.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "name of the table to apply the operation on"
                            },
                            "by": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "columns to group by"
                            },
                            "agg": {
                                "type": "array",
                                "items": {
                                    "type": "object(dictionary)",
                                    "properties": {
                                        "column": {"type": "string"},
                                        "agg_func": {"type": "string"}
                                    }
                                },
                                "description": "aggregation specifications"
                            }
                        },
                        "required": ["table_name", "by", "agg"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## GroupBy Definition

{op_definition}

* Example: 
Input Table: "my_table"
sj_id | c_id | interaction
---|---|---
1.0 | 1.0 | 1
1.0 | 3.0 | 1
1.0 | 5.0 | 1
......

Executing the operator: GroupBy(table_name="my_table", by=['c_id'], agg=[{{'column': 'interaction', 'agg_func': 'sum'}}])

Output Table: "my_table"
c_id | interaction
---|---
1.0 | 4
2.0 | 4
3.0 | 1
......
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        op = eval(text)
        # assert the agg function has two keys
        for item in op.agg:
            if len(item) == 2 and 'column' in item and 'agg_func' in item:
                continue
            raise ValueError(f"The agg function must have two keys: 'column' and 'agg_func'. But got {item}")
        return op
        pattern = r'GroupBy\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*by\s*=\s*(.*?)\s*,\s*agg\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, by_str, agg_str = matches[-1]
            table_name = table_name.strip().strip("'\"")
            by = eval(by_str.strip())
            agg = eval(agg_str.strip())
            if isinstance(by, list):
                by = [str(b) for b in by]
            if isinstance(agg, list):
                for i in range(len(agg)):
                    agg[i]['column'] = str(agg[i]['column'])
            return cls(table_name=table_name, by=by, agg=agg)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", by={self.by}, agg={self.agg})'

@dataclass
class Rename(BaseOp):
    action_type: str = field(
        default="rename",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "rename"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    rename_map: List[Dict[str, str]] = field(metadata={"help": 'rename specifications'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: Rename(table_name: str, rename_map: List[Dict[str, str]])
* Description: Rename columns based on specified mappings.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "Rename",
                    "description": "Rename columns based on specified mappings.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "name of the table to apply the operation on"
                            },
                            "rename_map": {
                                "type": "array",
                                "items": {
                                    "type": "object(dictionary)",
                                    "properties": {
                                        "old_name": {"type": "string"},
                                        "new_name": {"type": "string"}
                                    }
                                },
                                "description": "rename specifications"
                            }
                        },
                        "required": ["table_name", "rename_map"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Rename Definition

{op_definition}

* Example: Rename(table_name="my_table", rename_map=[{{"old_name": "first_name", "new_name": "fname"}}, {{"old_name": "last_name", "new_name": "lname"}}])
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Rename\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*rename_map\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, rename_map_str = matches[-1]
            table_name = table_name.strip().strip("'\"")
            rename_map = eval(rename_map_str.strip())
            if isinstance(rename_map, list):
                for i in range(len(rename_map)):
                    rename_map[i]['old_name'] = str(rename_map[i]['old_name'])
                    rename_map[i]['new_name'] = str(rename_map[i]['new_name'])
            return cls(table_name=table_name, rename_map=rename_map)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", rename_map={self.rename_map})'

@dataclass
class Stack(BaseOp):
    action_type: str = field(
        default="stack",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "stack"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    id_vars: List[str] = field(metadata={"help": 'columns to keep as identifiers'})
    value_vars: List[str] = field(metadata={"help": 'columns to stack'})
    var_name: str = field(default="variable", metadata={"help": 'name for the stacked variable column'})
    value_name: str = field(default="value", metadata={"help": 'name for the stacked value column'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Stack(table_name: str, id_vars: List[str], value_vars: List[str], var_name: str, value_name: str)
* Description: Stack multiple columns into a single column.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Stack",
        "description": "Stack multiple columns into a single column.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "id_vars": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to keep as identifiers"
                },
                "value_vars": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to stack"
                },
                "var_name": {
                    "type": "string",
                    "description": "name for the stacked variable column",
                    "default": "variable"
                },
                "value_name": {
                    "type": "string",
                    "description": "name for the stacked value column",
                    "default": "value"
                }
            },
            "required": ["table_name", "id_vars", "value_vars", "var_name", "value_name"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Stack Definition

{op_definition}

* Example:
Input Table: "my_table"
Product | ASIA | EU | US
---|---|---|---
A | 20 | 30 | 100
B | 150 | 200 | 300

Executing the operator: Stack(
    table_name="my_table",
    id_vars=["Product"],
    value_vars=["ASIA", "EU", "US"],
    var_name="Region",
    value_name="Sales"
)

Output Table: "my_table"
Product | Region | Sales
---|---|---
A | ASIA | 20
B | ASIA | 150
A | EU | 30
B | EU | 200
A | US | 100
B | US | 300
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Stack\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*id_vars\s*=\s*(.*?)\s*,\s*value_vars\s*=\s*(.*?)\s*,\s*var_name\s*=\s*(.*?)\s*,\s*value_name\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, id_vars, value_vars, var_name, value_name = (item.strip().strip("'\"") for item in matches[-1])
            id_vars = eval(id_vars)
            value_vars = eval(value_vars)
            if isinstance(value_vars, list):
                value_vars = [str(v) for v in value_vars]
            if isinstance(id_vars, list):
                id_vars = [str(v) for v in id_vars]
            return cls(table_name=table_name, id_vars=id_vars, value_vars=value_vars, var_name=var_name, value_name=value_name)
        return None

    def __repr__(self) -> str:
        var_name, value_name = self.var_name.replace('"', '\\"'), self.value_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", id_vars={self.id_vars}, value_vars={self.value_vars}, var_name="{var_name}", value_name="{value_name}")'

@dataclass
class Explode(BaseOp):
    action_type: str = field(
        default="explode",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "explode"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column: str = field(metadata={"help": 'column to explode'})
    split_comma: bool = field(default=False, metadata={"help": 'whether to split by comma'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Explode(table_name: str, column: str, split_comma: bool)
* Description: Explode a column containing lists or comma-separated values.
""".strip()
        json_format = json.dumps({
            "type": "function",
            "function": {
                "name": "Explode",
                "description": "Explode a column containing lists or comma-separated values.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "table_name": {
                            "type": "string",
                            "description": "name of the table to apply the operation on"
                        },
                        "column": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "column(s) to explode"
                        },
                        "split_comma": {
                            "type": "boolean",
                            "description": "whether to split by comma if not a list",
                            "default": False
                        }
                    },
                    "required": ["table_name", "column", "split_comma"]
                }
            }
        })

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Explode Definition

{op_definition}

* Example:
Input Table: "my_table"
born_state | head_ID | age
---|---|---|---
"Alabama" | [1, 3] | [67.0, 69.0]
"California" | [2, 4, 6, 8] | [68.0, 52.0, 69.0]

Executing the operator: Explode(
    table_name='my_table',
    column=['head_ID', 'age'],  # 多列explode
    split_comma=False
)

Output Table: "my_table"
born_state | head_ID | age
---|---|---
"Alabama" | 1 | 67.0
"Alabama" | 3 | 69.0
"California" | 2 | 68.0
"California" | 4 | 52.0
"California" | 6 | 69.0
"California" | 8 | 69.0
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Explode\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column\s*=\s*(.*?)\s*,\s*split_comma\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column, split_comma = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, column=column, split_comma=eval(split_comma))
        return None

    def __repr__(self) -> str:
        if isinstance(self.column, list):
            return f'{self.__class__.__name__}(table_name="{self.table_name}", column={self.column}, split_comma={self.split_comma})'
        else:
            return f'{self.__class__.__name__}(table_name="{self.table_name}", column="{self.column}", split_comma={self.split_comma})'

@dataclass
class WideToLong(BaseOp):
    action_type: str = field(
        default="wide_to_long",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "wide_to_long"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    subnames: List[str] = field(metadata={"help": 'prefix of columns to convert'})
    i: List[str] = field(metadata={"help": 'columns to use as identifiers'})
    j: str = field(default="variable", metadata={"help": 'name for the new variable column'})
    sep: str = field(default="_", metadata={"help": 'separator in column names'})
    suffix: str = field(default=r"\d+", metadata={"help": 'suffix pattern in column names'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: WideToLong(table_name: str, subnames: List[str], i: List[str], j: str, sep: str, suffix: str)
* Description: Convert wide format data to long format.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "WideToLong",
        "description": "Convert wide format data to long format.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "subnames": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "prefix of columns to convert"
                },
                "i": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to use as identifiers"
                },
                "j": {
                    "type": "string",
                    "description": "name for the new variable column",
                    "default": "variable"
                },
                "sep": {
                    "type": "string",
                    "description": "separator in column names",
                    "default": "_"
                },
                "suffix": {
                    "type": "string",
                    "description": "suffix pattern in column names",
                    "default": r"\d+"
                }
            },
            "required": ["table_name", "subnames", "i", "j", "sep", "suffix"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## WideToLong Definition

{op_definition}

* Example:
Input Table: "my_table"
id | sales_2021 | sales_2022 | profit_2021 | profit_2022
|---|---|---|---|---
1 | 100 | 150 | 10 | 15
2 | 200 | 250 | 20 | 25

Executing the operator: WideToLong(
    table_name="my_table",
    subnames=["sales", "profit"],
    i=["id"],
    j="year",
    sep="_",
    suffix=r"\d+"
)

Output Table: "my_table"
id | year | sales | profit
|---|---|---|---
1 | 2021 | 100 | 10
2 | 2021 | 200 | 20
1 | 2022 | 150 | 15
2 | 2022 | 250 | 25
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'WideToLong\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*subnames\s*=\s*(.*?)\s*,\s*i\s*=\s*(.*?)\s*,\s*j\s*=\s*(.*?)\s*,\s*sep\s*=\s*(.*?)\s*,\s*suffix\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, subnames, i, j, sep, suffix = (item.strip().strip("'\"") for item in matches[-1])
            subnames = eval(subnames)
            if isinstance(subnames, list):
                subnames = [str(s) for s in subnames]
            i = eval(i)
            if isinstance(i, list):
                i = [str(i) for i in i]
            return cls(table_name=table_name, subnames=subnames, i=i, j=j, sep=sep, suffix=suffix)
        return None

    def __repr__(self) -> str:
        self.suffix = self.suffix.replace('"', '\\"')
        if isinstance(self.i, str):
            self.i = self.i.replace('"', '\\"')
        if isinstance(self.j, str):
            self.j = self.j.replace('"', '\\"')
        if isinstance(self.sep, str):
            self.sep = self.sep.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", subnames={self.subnames}, i={self.i}, j="{self.j}", sep="{self.sep}", suffix="{self.suffix}")'

@dataclass
class Union(BaseOp):
    action_type: str = field(
        default="union",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "union"'}
    )
    table_names: List[str] = field(metadata={"help": 'names of the tables to union'})
    how: str = field(default="all", metadata={"help": 'union type (all/distinct)'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: Union(table_names: List[str], how: str)
* Description: Combine multiple tables vertically. `table_names` is a list of table names. `how` is the union type, "all" means union all, "distinct" means union distinct.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Union",
        "description": "Combine multiple tables vertically. `table_names` is a list of table names. `how` is the union type, \"all\" means union all, \"distinct\" means union distinct.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "names of the tables to union"
                },
                "how": {
                    "type": "string",
                    "description": "union type (all/distinct)",
                    "default": "all"
                }
            },
            "required": ["table_names", "how"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Union Definition

{op_definition}

* Example: Union(table_names=["table_1", "table_2"], how="distinct")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Union\s*\(\s*table_names\s*=\s*(.*?)\s*,\s*how\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_names, how = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_names=eval(table_names), how=how)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_names={self.table_names}, how="{self.how}")'

@dataclass
class Transpose(BaseOp):
    action_type: str = field(
        default="transpose",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "transpose"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Transpose(table_name: str)
* Description: Transpose rows and columns.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Transpose",
        "description": "Transpose rows and columns.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                }
            },
            "required": ["table_name"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Transpose Definition

{op_definition}

* Example:
Input Table: "my_table"
Product | ASIA | EU | US
---|---|---|---
A | 20 | 30 | 100
B | 150 | 200 | 300

Executing the operator: Transpose(table_name="my_table")

Output Table: "my_table"
Product | A | B
---|---|---
A | 20 | 150
B | 30 | 200
US | 100 | 300
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Transpose\s*\(\s*table_name\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name = matches[-1].strip().strip("'\"")
            return cls(table_name=table_name)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}")'

@dataclass
class DropNulls(BaseOp):
    action_type: str = field(
        default="dropna",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "dropna"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    subset: Optional[List[str]] = field(default=None, metadata={"help": 'columns to check for nulls'})
    how: str = field(default="any", metadata={"help": 'how to handle nulls (any/all)'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: DropNulls(table_name: str, subset: Optional[List[str]], how: str)
* Description: Remove rows with null values.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "DropNulls",
        "description": "Remove rows with null values.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "subset": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to check for nulls"
                },
                "how": {
                    "type": "string",
                    "description": "how to handle nulls (any/all)",
                    "default": "any"
                }
            },
            "required": ["table_name", "subset", "how"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## DropNulls Definition

{op_definition}

* Example: DropNulls(table_name="my_table", subset=["age", "name"], how="all")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'DropNulls\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*subset\s*=\s*(.*?)\s*,\s*how\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, subset, how = (item.strip().strip("'\"") for item in matches[-1])
            subset_eval = eval(subset) if subset != "None" else None
            if isinstance(subset_eval, list):
                subset_eval = [str(s) for s in subset_eval]
            return cls(table_name=table_name, subset=subset_eval, how=how)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", subset={self.subset}, how="{self.how}")'

@dataclass
class Deduplicate(BaseOp):
    action_type: str = field(
        default="deduplicate",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "deduplicate"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    subset: Optional[List[str]] = field(default=None, metadata={"help": 'columns to check for duplicates'})
    keep: str = field(default="first", metadata={"help": 'which duplicate to keep (first/last)'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Deduplicate(table_name: str, subset: Optional[List[str]], keep: str)
* Description: Remove duplicate rows. `subset` is the columns to check for duplicates. `keep` is the duplicate to keep (first/last).
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Deduplicate",
        "description": "Remove duplicate rows. `subset` is the columns to check for duplicates. `keep` is the duplicate to keep (first/last).",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "subset": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to check for duplicates"
                },
                "keep": {
                    "type": "string",
                    "description": "which duplicate to keep (first/last)",
                    "default": "first"
                }
            },
            "required": ["table_name", "subset", "keep"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Deduplicate Definition

{op_definition}

* Example: Deduplicate(table_name="my_table", subset=["id"], keep="last")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Deduplicate\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*subset\s*=\s*(.*?)\s*,\s*keep\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, subset, keep = (item.strip().strip("'\"") for item in matches[-1])
            subset_eval = eval(subset) if subset != "None" else None
            if isinstance(subset_eval, list):
                subset_eval = [str(s) for s in subset_eval]
            return cls(table_name=table_name, subset=subset_eval, keep=keep)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", subset={self.subset}, keep="{self.keep}")'

@dataclass
class TopK(BaseOp):
    action_type: str = field(
        default="topk",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "topk"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    k: int = field(metadata={"help": 'number of rows to keep'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: TopK(table_name: str, k: int)
* Description: Keep only the first k rows.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "TopK",
        "description": "Keep only the first k rows.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "k": {
                    "type": "integer",
                    "description": "number of rows to keep"
                }
            },
            "required": ["table_name", "k"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## TopK Definition

{op_definition}

* Example: TopK(table_name="my_table", k=5)
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'TopK\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*k\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, k = matches[-1]
            table_name = table_name.strip().strip("'\"")
            return cls(table_name=table_name, k=int(k.strip()))
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", k={self.k})'

@dataclass
class SelectCol(BaseOp):
    action_type: str = field(
        default="select",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "select"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    columns: List[str] = field(metadata={"help": 'columns to select'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: SelectCol(table_name: str, columns: List[str])
* Description: Select specific columns.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "SelectCol",
        "description": "Select specific columns.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to select"
                }
            },
            "required": ["table_name", "columns"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## SelectCol Definition

{op_definition}

* Example: SelectCol(table_name="my_table", columns=["name", "age"])
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'SelectCol\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*columns\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, columns = matches[-1]
            table_name = table_name.strip().strip("'\"")
            columns = eval(columns.strip())
            if isinstance(columns, list):
                columns = [str(c) for c in columns]
            return cls(table_name=table_name, columns=columns)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", columns={self.columns})'

@dataclass
class CastType(BaseOp):
    action_type: str = field(
        default="cast",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "cast"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column: str = field(metadata={"help": 'column to cast'})
    dtype: str = field(metadata={"help": 'target data type'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: CastType(table_name: str, column: str, dtype: str)
* Description: Cast column to specified data type.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "CastType",
        "description": "Cast column to specified data type.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "column": {
                    "type": "string",
                    "description": "column to cast"
                },
                "dtype": {
                    "type": "string",
                    "description": "target data type"
                }
            },
            "required": ["table_name", "column", "dtype"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## CastType Definition

{op_definition}

* Example: CastType(table_name="my_table", column="age", dtype="float")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'CastType\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column\s*=\s*(.*?)\s*,\s*dtype\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column, dtype = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, column=str(column), dtype=dtype)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", column="{self.column}", dtype="{self.dtype}")'

@dataclass
class Terminate(BaseOp):
    action_type: str = field(
        default="terminate",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "terminate"'}
    )
    result: List[str] = field(metadata={"help": 'list of output table names'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Terminate(result: List[str])
* Description: Terminate the process and specify the final output tables.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Terminate",
        "description": "Terminate the process and specify the final output tables.",
        "parameters": {
            "type": "object",
            "properties": {
                "result": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "list of output table names"
                }
            },
            "required": ["result"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Terminate Definition

{op_definition}

* Example: Terminate(result=["table_1"])
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Terminate\s*\(\s*result\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            result_str = matches[-1]
            # The regex is greedy, so we might capture the outer parenthesis of the call
            if result_str.endswith(')'):
                result_str = result_str[:-1]
            
            result = eval(result_str.strip())
            if not isinstance(result, list):
                result = [result]
            return cls(result=result)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(result={self.result})'


@dataclass
class MissingValueImputation(BaseOp):
    action_type: str = field(
        default="missing_value_imputation",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "missing_value_imputation"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column_name: str = field(metadata={"help": 'column to impute missing values'})
    mode: str = field(metadata={"help": 'imputation method: mode, mean, or median'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: MissingValueImputation(table_name: str, column_name: str, mode: str)
* Description: Impute missing values in a column using mode, mean, or median.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "MissingValueImputation",
        "description": "Impute missing values in a column using mode, mean, or median.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "column_name": {
                    "type": "string",
                    "description": "column to impute missing values"
                },
                "mode": {
                    "type": "string",
                    "description": "imputation method: mode, mean, or median"
                }
            },
            "required": ["table_name", "column_name", "mode"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## MissingValueImputation Definition

{op_definition}

* Example: MissingValueImputation(table_name="my_table", column_name="age", mode="median")
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'MissingValueImputation\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column_name\s*=\s*(.*?)\s*,\s*mode\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column_name, mode = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, column_name=column_name, mode=mode)
        return None

    def __repr__(self) -> str:
        self.table_name = self.table_name.replace('"', '\\"')
        self.column_name = self.column_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", column_name="{self.column_name}", mode="{self.mode}")'

@dataclass
class OutlierDetection(BaseOp):
    action_type: str = field(
        default="outlier",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "outlier"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column_name: str = field(metadata={"help": 'column to detect outliers'})
    action: str = field(default="delete", metadata={"help": 'action to take: delete or add_tag'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: OutlierDetection(table_name: str, column_name: str, action: str)
* Description: Detect outliers using IQR method. Either delete rows (action="delete") or add a tag column (action="add_tag").
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "OutlierDetection",
        "description": "Detect outliers using IQR method. Either delete rows (action=\"delete\") or add a tag column (action=\"add_tag\").",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "column_name": {
                    "type": "string",
                    "description": "column to detect outliers"
                },
                "action": {
                    "type": "string",
                    "description": "action to take: delete or add_tag",
                    "default": "delete"
                }
            },
            "required": ["table_name", "column_name", "action"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## OutlierDetection Definition

{op_definition}

* Example: OutlierDetection(table_name="my_table", column_name="salary", action="add_tag")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'OutlierDetection\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column_name\s*=\s*(.*?)\s*,\s*action\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column_name, action = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, column_name=column_name, action=action)
        return None

    def __repr__(self) -> str:
        table_name, column_name = self.table_name.replace('"', '\\"'), self.column_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{table_name}", column_name="{column_name}", action="{self.action}")'

@dataclass
class StandardizeString(BaseOp):
    action_type: str = field(
        default="standardize_str",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "standardize_str"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column_name: str = field(metadata={"help": 'column to standardize'})
    func: str = field(metadata={"help": 'string transformation function'})

    @classmethod
    def get_action_description(cls) -> str:
        base_format = """
* Signature: StandardizeString(table_name: str, column_name: str, func: str)
* Description: Standardize string values in a column using a transformation function. The function should input with a string named "s" and output with a new string.
""".strip()
        json_format = json.dumps(
            {
                "type": "function",
                "function": {
                    "name": "StandardizeString",
                    "description": "Standardize string values in a column using a transformation function. The function should input with a string named \"s\" and output with a new string.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {
                                "type": "string",
                                "description": "name of the table to apply the operation on"
                            },
                            "column_name": {
                                "type": "string",
                                "description": "column to standardize"
                            },
                            "func": {
                                "type": "string",
                                "description": "string transformation function"
                            }
                        },
                        "required": ["table_name", "column_name", "func"]
                    }
                }
            }
        )

        op_definition = eval(FORMAT_TYPE)

        return f"""
## StandardizeString Definition

{op_definition}

* Example:
Input Table: "my_table"
cyclist | year
---|---|---
"John Doe (USA)" | 2023
"Mike Johnson-USA" | 2023

Executing the operator: StandardizeString(table_name="input_table", column_name="cyclist", func=\"\"\"
def transform_func(cyclist):
    match = re.match(r'(.+?)\\s*[(-]\\s*(\\w+)', cyclist)
    if match:
        name, country = match.groups()
        return f\"{{name.strip()}} ({{country}})\"
    return cyclist
\"\"\")

Output Table: "my_table"
cyclist | year
---|---|---
"John Doe (USA)" | 2023
"Mike Johnson (USA)" | 2023
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'StandardizeString\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column_name\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column_name, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            column_name = column_name.strip("'\"")
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_name=table_name, column_name=column_name, func=func)
        return None

    def __repr__(self) -> str:
        self.table_name = self.table_name.replace('"', '\\"')
        self.column_name = self.column_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", column_name="{self.column_name}", func="""{self.func}""")'

@dataclass
class StandardizeDatetime(BaseOp):
    action_type: str = field(
        default="standardize_dt",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "standardize_dt"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column_name: str = field(metadata={"help": 'column to standardize'})
    date_format: str = field(metadata={"help": 'target datetime format'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: StandardizeDatetime(table_name: str, column_name: str, date_format: str)
* Description: Standardize datetime values in a column to a specific format.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "StandardizeDatetime",
        "description": "Standardize datetime values in a column to a specific format.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "column_name": {
                    "type": "string",
                    "description": "column to standardize"
                },
                "date_format": {
                    "type": "string",
                    "description": "target datetime format"
                }
            },
            "required": ["table_name", "column_name", "date_format"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## StandardizeDatetime Definition

{op_definition}

* Example: StandardizeDatetime(table_name="my_table", column_name="date", date_format="%Y-%m-%d")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'StandardizeDatetime\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column_name\s*=\s*(.*?)\s*,\s*date_format\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column_name, date_format = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, column_name=column_name, date_format=date_format)
        return None

    def __repr__(self) -> str:
        table_name, column_name = self.table_name.replace('"', '\\"'), self.column_name.replace('"', '\\"')
        date_format = self.date_format.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{table_name}", column_name="{column_name}", date_format="{date_format}")'

@dataclass
class ErrorDetection(BaseOp):
    action_type: str = field(
        default="error_detect",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "error_detect"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    column_name: str = field(metadata={"help": 'column to check for errors'})
    func: str = field(metadata={"help": 'verification function, True if valid, False if error'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: ErrorDetection(table_name: str, column_name: str, func: str)
* Description: Detect errors in records using a custom function. The function will verify whether the input is valid or not.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "ErrorDetection",
        "description": "Detect errors in records using a custom function. The function will verify whether the input is valid or not.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "column_name": {
                    "type": "string",
                    "description": "column to check for errors"
                },
                "func": {
                    "type": "string",
                    "description": "verification function, True if valid, False if error"
                }
            },
            "required": ["table_name", "column_name", "func"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## ErrorDetection Definition

{op_definition}

* Example: ErrorDetection(table_name="my_table", column_name="email", func=\"\"\"
def is_valid_email(val): 
    name, at, domain = val.partition('@')
    return '@' in val and name and domain
\"\"\")
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'ErrorDetection\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*column_name\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, column_name, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            column_name = column_name.strip("'\"")
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_name=table_name, column_name=column_name, func=func)
        return None

    def __repr__(self) -> str:
        table_name, column_name = self.table_name.replace('"', '\\"'), self.column_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{table_name}", column_name="{column_name}", func="""{self.func}""")'

@dataclass
class AddNewColumn(BaseOp):
    action_type: str = field(
        default="add_col",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "add_col"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    new_column_name: str = field(metadata={"help": 'name of the new column to be added'})
    func: str = field(metadata={"help": 'function to compute new column value for each row'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: AddNewColumn(table_name: str, new_column_name: str, func: str)
* Description: Add a new column using a function that takes a pd.Series object and returns a value.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "AddNewColumn",
        "description": "Add a new column using a function that takes a pd.Series object and returns a value.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "new_column_name": {
                    "type": "string",
                    "description": "name of the new column to be added"
                },
                "func": {
                    "type": "string",
                    "description": "function to compute new column value for each row"
                }
            },
            "required": ["table_name", "new_column_name", "func"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## AddNewColumn Definition

{op_definition}

* Example: AddNewColumn(table_name="my_table", new_column_name="age_doubled", func=\"\"\"
def compute(row: pd.Series): 
    return row['age'] * 2
\"\"\")
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'AddNewColumn\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*new_column_name\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, new_column_name, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            new_column_name = new_column_name.strip("'\"")
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_name=table_name, new_column_name=new_column_name, func=func)
        return None

    def __repr__(self) -> str:
        table_name = self.table_name.replace('"', '\\"')
        new_column_name = self.new_column_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{table_name}", new_column_name="{new_column_name}", func="""{self.func}""")'

@dataclass
class DropColumn(BaseOp):
    action_type: str = field(
        default="drop_col",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "drop_col"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    drop_columns: List[str] = field(metadata={"help": 'columns to drop'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: DropColumn(table_name: str, drop_columns: List[str])
* Description: Drop specified columns from the table.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "DropColumn",
        "description": "Drop specified columns from the table.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "drop_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to drop"
                }
            },
            "required": ["table_name", "drop_columns"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## DropColumn Definition

{op_definition}

* Example: DropColumn(table_name="my_table", drop_columns=["unused_col", "temp_col"])
"""
    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'DropColumn\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*drop_columns\s*=\s*(.*?)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, drop_columns = matches[-1]
            table_name = table_name.strip().strip("'\"")
            drop_columns = eval(drop_columns.strip())
            if isinstance(drop_columns, list):
                drop_columns = [str(c) for c in drop_columns]
            return cls(table_name=table_name, drop_columns=drop_columns)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}", drop_columns={self.drop_columns})'

@dataclass
class SplitColumn(BaseOp):
    action_type: str = field(
        default="split_col",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "split_col"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    source_column: str = field(metadata={"help": 'column to split'})
    target_columns: List[str] = field(metadata={"help": 'names of the new columns after split'})
    func: str = field(metadata={"help": 'function to split the column, should return a dictionary with target column names as keys'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: SplitColumn(table_name: str, source_column: str, target_columns: List[str], func: str)
* Description: Split a column into multiple columns using a function that returns a dictionary with target column names as keys.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "SplitColumn",
        "description": "Split a column into multiple columns using a function that returns a dictionary with target column names as keys.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "source_column": {
                    "type": "string",
                    "description": "column to split"
                },
                "target_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "names of the new columns after split"
                },
                "func": {
                    "type": "string",
                    "description": "function to split the column, should return a dictionary with target column names as keys"
                }
            },
            "required": ["table_name", "source_column", "target_columns", "func"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## SplitColumn Definition

{op_definition}

* Example: SplitColumn(table_name="my_table", source_column="full_name", target_columns=["first_name", "last_name"], func=\"\"\"
def split(val):
    parts = val.split(' ')
    return {{"first_name": parts[0], "last_name": ' '.join(parts[1:]) if len(parts) > 1 else ''}}
\"\"\")
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'SplitColumn\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*source_column\s*=\s*(.*?)\s*,\s*target_columns\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, source_column, target_columns, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            source_column = source_column.strip("'\"")
            target_columns = eval(target_columns)
            if isinstance(target_columns, list):
                target_columns = [str(c) for c in target_columns]
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_name=table_name, source_column=source_column, target_columns=target_columns, func=func)
        return None

    def __repr__(self) -> str:
        source_column = self.source_column.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", source_column="{source_column}", target_columns={self.target_columns}, func="""{self.func}""")'

@dataclass
class Concatenate(BaseOp):
    action_type: str = field(
        default="concatenate",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "concatenate"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    concatenate_columns: List[str] = field(metadata={"help": 'columns to concatenate'})
    target_column: str = field(metadata={"help": 'name of the new column for concatenated result'})
    func: str = field(metadata={"help": 'function to concatenate columns'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Concatenate(table_name: str, concatenate_columns: List[str], target_column: str, func: str)
* Description: Concatenate multiple columns into a single new column using a function. The function input with a pd.Series object and output a string.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Concatenate",
        "description": "Concatenate multiple columns into a single new column using a function. The function input with a pd.Series object and output a string.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "concatenate_columns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "columns to concatenate"
                },
                "target_column": {
                    "type": "string",
                    "description": "name of the new column for concatenated result"
                },
                "func": {
                    "type": "string",
                    "description": "function to concatenate columns"
                }
            },
            "required": ["table_name", "concatenate_columns", "target_column", "func"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Concatenate Definition

{op_definition}

* Example: Concatenate(table_name="my_table", concatenate_columns=["first_name", "last_name"], target_column="full_name", func=\"\"\"
def concat(row: pd.Series) -> str:
    return f"{{row['first_name']}} {{row['last_name']}}"
\"\"\")
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        if text.endswith('"""")'):
            text = text[:-5]
            text += '" """)'
        return eval(text)
        pattern = r'Concatenate\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*concatenate_columns\s*=\s*(.*?)\s*,\s*target_column\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, concatenate_columns, target_column, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            concatenate_columns = eval(concatenate_columns)
            if isinstance(concatenate_columns, list):
                concatenate_columns = [str(c) for c in concatenate_columns]
            target_column = target_column.strip("'\"")
            if func.startswith("'") and func.endswith("'"):
                func = func[1:-1]
            if func.startswith('"') and func.endswith('"'):
                func = func[1:-1]
            return cls(table_name=table_name, concatenate_columns=concatenate_columns, target_column=target_column, func=func)
        return None

    def __repr__(self) -> str:
        self.target_column = self.target_column.replace('"', '\\"') if isinstance(self.target_column, str) else self.target_column
        return f'{self.__class__.__name__}(table_name="{self.table_name}", concatenate_columns={self.concatenate_columns}, target_column="{self.target_column}", func="""{self.func} """)'

@dataclass
class Subtitle(BaseOp):
    action_type: str = field(
        default="subtitle",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "subtitle"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})
    title: str = field(metadata={"help": 'title or subtitle to add to the table'})
    target_column: str = field(metadata={"help": 'name of the new column to store the subtitle'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Subtitle(table_name: str, title: str, target_column: str)
* Description: Add a title or subtitle as a new column to the table.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Subtitle",
        "description": "Add a title or subtitle as a new column to the table.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                },
                "title": {
                    "type": "string",
                    "description": "title or subtitle to add to the table"
                },
                "target_column": {
                    "type": "string",
                    "description": "name of the new column to store the subtitle"
                }
            },
            "required": ["table_name", "title", "target_column"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Subtitle Definition

{op_definition}

* Example: Subtitle(table_name="my_table", title="Sales Data 2023", target_column="subtitle")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Subtitle\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*title\s*=\s*(.*?)\s*,\s*target_column\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, title, target_column = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, title=title, target_column=target_column)
        return None

    def __repr__(self) -> str:
        title, target_column = self.title.replace('"', '\\"'), self.target_column.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", title="{title}", target_column="{target_column}")'

@dataclass
class Append(BaseOp):
    action_type: str = field(
        default="append",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "append"'}
    )
    table_name: str = field(metadata={"help": 'source table name'})
    table_to_be_appended: str = field(metadata={"help": 'table to be appended to source'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Append(table_name: str, table_to_be_appended: str)
* Description: Append one table to another vertically.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Append",
        "description": "Append one table to another vertically.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "source table name"
                },
                "table_to_be_appended": {
                    "type": "string",
                    "description": "table to be appended to source"
                }
            },
            "required": ["table_name", "table_to_be_appended"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Append Definition

{op_definition}

* Example: Append(table_name="main_table", table_to_be_appended="additional_data")
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Append\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*table_to_be_appended\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, table_to_be_appended = (item.strip().strip("'\"") for item in matches[-1])
            return cls(table_name=table_name, table_to_be_appended=table_to_be_appended)
        return None

    def __repr__(self) -> str:
        table_to_be_appended = self.table_to_be_appended.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", table_to_be_appended="{table_to_be_appended}")'

@dataclass
class Count(BaseOp):
    action_type: str = field(
        default="count",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "count"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to apply the operation on'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: Count(table_name: str)
* Description: Count the number of rows in the table.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "Count",
        "description": "Count the number of rows in the table.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to apply the operation on"
                }
            },
            "required": ["table_name"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## Count Definition

{op_definition}

* Example:
Input Table: "my_table"
cyclist | year
---|---|---
JD | 2023
MJ | 2023

Executing the operator: Count(table_name="my_table")

Output Table: "statistic_table"
operator | statistic_name | value
---|---
Count(table_name="my_table") | 2
"""

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'Count\s*\(\s*table_name\s*=\s*(.*?)\s*\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name = matches[-1].strip().strip("'\"")
            return cls(table_name=table_name)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_name="{self.table_name}")'

@dataclass
class CodeGeneration(BaseOp):
    action_type: str = field(
        default="code_gen",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "code_gen"'}
    )
    table_names: List[str] = field(metadata={"help": 'names of the tables to use as input'})
    target_table: str = field(metadata={"help": 'name of the single table to be generated'})
    func: str = field(metadata={"help": 'function to process input tables and return a single new table'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: CodeGeneration(table_names: List[str], target_table: str, func: str)
* Description: Generate a single new table using a function that processes input tables and returns a single DataFrame.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "CodeGeneration",
        "description": "Generate a single new table using a function that processes input tables and returns a single DataFrame.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "names of the tables to use as input"
                },
                "target_table": {
                    "type": "string",
                    "description": "name of the single table to be generated"
                },
                "func": {
                    "type": "string",
                    "description": "function to process input tables and return a single new table"
                }
            },
            "required": ["table_names", "target_table", "func"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## CodeGeneration Definition

{op_definition}

* Example: CodeGeneration(table_names=["table_1", "table_2"], target_table="new_table", func=\"\"\"
import pandas as pd
def process_tables(table_1: pd.DataFrame, table_2: pd.DataFrame):
    result_df = table_1.merge(table_2, on='id')
    return result_df
\"\"\")
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'CodeGeneration\s*\(\s*table_names\s*=\s*(.*?)\s*,\s*target_table\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_names, target_table, func = (item.strip() for item in matches[-1])
            table_names = eval(table_names)
            if isinstance(table_names, list):
                table_names = [str(t) for t in table_names]
            target_table = target_table.strip("'\"")
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_names=table_names, target_table=target_table, func=func)
        return None

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(table_names={self.table_names}, target_table="{self.target_table}", func="""{self.func}""")'

@dataclass
class CalculateStatistic(BaseOp):
    action_type: str = field(
        default="calc_stat",
        init=False,
        repr=False,
        metadata={"help": 'type of action, c.f., "calc_stat"'}
    )
    table_name: str = field(metadata={"help": 'name of the table to use as input'})
    statistic_name: str = field(metadata={"help": 'name of the statistic to calculate'})
    func: str = field(metadata={"help": 'function to calculate the statistic from input tables'})

    @classmethod
    def get_action_description(cls) -> str:
           
        base_format = """
* Signature: CalculateStatistic(table_name: str, statistic_name: str, func: str)
* Description: Calculate a statistic value from input tables using a function that processes dataframe objects and outputs a specific value.
""".strip()
        json_format = json.dumps({
    "type": "function",
    "function": {
        "name": "CalculateStatistic",
        "description": "Calculate a statistic value from input tables using a function that processes dataframe objects and outputs a specific value.",
        "parameters": {
            "type": "object",
            "properties": {
                "table_name": {
                    "type": "string",
                    "description": "name of the table to use as input"
                },
                "statistic_name": {
                    "type": "string",
                    "description": "name of the statistic to calculate"
                },
                "func": {
                    "type": "string",
                    "description": "function to calculate the statistic from input tables"
                }
            },
            "required": ["table_name", "statistic_name", "func"]
        }
    }
})

        op_definition = eval(FORMAT_TYPE)

        return f"""
## CalculateStatistic Definition

{op_definition}

* Example:
Input Table: "my_table"
cyclist | age
---|---
JD | 100
MJ | 120

Executing the operator: CalculateStatistic(table_name="my_table", statistic_name="average_age", func=\"\"\"
def calculate_stat(df: pd.DataFrame):
    return df['age'].mean()
\"\"\")

Output Table: "statistic_table"
operator | statistic_name | value
---|---|---
"CalculateStatistic(table_name="my_table", statistic_name="average_age", func=\"\"\"\ndef calculate_stat(df: pd.DataFrame):\n    return df['age'].mean()\n\"\"\")" | "average_age" | 116.66666666666667(...)
""".strip()

    @classmethod
    def parse_action_from_text(cls, text: str) -> Optional[BaseOp]:
        return eval(text)
        pattern = r'CalculateStatistic\s*\(\s*table_name\s*=\s*(.*?)\s*,\s*statistic_name\s*=\s*(.*?)\s*,\s*func\s*=\s*(.*)\)'
        matches = re.findall(pattern, text, flags=re.DOTALL)
        if matches:
            table_name, statistic_name, func = (item.strip() for item in matches[-1])
            table_name = table_name.strip("'\"")
            statistic_name = statistic_name.strip("'\"")
            while True:
                if func.startswith('"') and func.endswith('"'): func = func[1:-1]
                elif func.startswith("'") and func.endswith("'"): func = func[1:-1]
                else: break
            return cls(table_name=table_name, statistic_name=statistic_name, func=func)
        return None

    def __repr__(self) -> str:
        statistic_name = self.statistic_name.replace('"', '\\"')
        return f'{self.__class__.__name__}(table_name="{self.table_name}", statistic_name="{statistic_name}", func="""{self.func}""")'