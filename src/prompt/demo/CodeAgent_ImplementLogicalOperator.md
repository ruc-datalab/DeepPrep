## Demonstration 1

**Input Tables**:
table_1:
festival id | festival name | chair name | location | year | num of audience
---|---|---|---|---|---
1 | Panasonic Awards | Raymond Floyd | United States | 2006 | 152
2 | Flower Awards | Charles Coody | United States | 2007 | 155
3 | Cherry Awards | Doug Ford | United States | 2007 | 160
4 | Gobel Awards | Arnold Palmer | United States | 2008 | 160
5 | LA Awards | Lucy Lu | United States | 2010 | 161

table_2:
artwork id | festival id | result
---|---|---
1 | 2 | Nominated
2 | 2 | Won
3 | 1 | Nominated
4 | 1 | Won
8 | 5 | Nominated
9 | 5 | Nominated

**Logical operator**: Join(left_table="table_1", right_table="table_2", left_on="festival id", right_on="festival id", how="outer", suffixes=["_left", "_right"])

Output: 
```
table_1 = input_tables['table_1']
table_2 = input_tables['table_2']
target_df = pd.merge(table_1, table_2, on='festival id', how='outer')
```

## Demonstration2

**Input Tables**:
table_1_table_2_join:
festival id | festival name | chair name | location | year | num of audience | artwork id | result
---|---|---|---|---|---|---|---|
1 | Panasonic Awards | Raymond Floyd | United States | 2006 | 152 | 3 | Nominated
1 | Panasonic Awards | Raymond Floyd | United States | 2006 | 152 | 4 | Won
2 | Flower Awards | Charles Coody | United States | 2007 | 155 | 1 | Nominated

**Logical operator**: Pivot(table_name="table_1_table_2_join", index="result", columns="location", values="artwork id", aggfunc="mean")

Output:
```
table_1_table_2_join = input_tables['table_1_table_2_join']
target_df = table_1_table_2_join.pivot_table(index='result', columns='location', values='artwork id', aggfunc='mean')
```

## Demonstration3

**Input Tables**:
table_1_table_2_join:
result | United States
---|---
Nominated | 5.25
Won | 3.0

**Logical operator**: GroupBy(table_name="table_1_table_2_join", by=["result"], agg=[{"column": "United States", "agg_func": "max"}])

Output: ```
table_1_table_2_join = input_tables['table_1_table_2_join']
target_df = table_1_table_2_join.groupby('result')['United States'].max().reset_index()
```