## Input Tables

Input Tables:
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

Target Table Schema Description:
We transform the input tables to complete the task: The task aims to analyze and compare the average artwork ID values for different results (Nominated and Won) of festivals held in the United States by transforming the input tables with asceding order by `United States` first and `result` second.
The column schema of the target table is as follows:
- Name of Column: "result"
  - Description: The outcome status of artworks submitted to festivals. Each row represents a distinct result category across all festival submissions.
  - Requirement
    - Distinct values for each row with the column `United States`
- Name of Column: "United States"
  - Description: The average artwork identifier values for each festival result within the United States location. These values represent the mean of artwork IDs that achieved each result status, calculated after combining festival and artwork data and accounting for location-specific aggregations.
  - Requirement
    - Distinct values for each row with the column `result`
    - Asceding order by `United States`

Output:
<operator> Join(left_table="table_1", right_table="table_2", left_on="festival id", right_on="festival id", how="outer", suffixes=["_left", "_right"]) --> Pivot(table_name="table_1_table_2_join", index="result", columns="location", values="artwork id", aggfunc="mean") --> GroupBy(table_name="table_1_table_2_join", by=["result"], agg=[{"column": "United States", "agg_func": "max"}]) --> Sort(table_name="table_1_table_2_join", by=["United States", "result"], ascending=[True, False]) --> Deduplicate(table_name="table_1_table_2_join", subset=["United States", "result"], keep="last") --> Terminate(result=["table_1_table_2_join"]) </operator>