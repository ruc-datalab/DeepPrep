## Demonstration 1

Input Table:
Name: "table_1"
invoice_id | client_id | invoice_status | invoice_details
|---|---|---|---|---
1 | 5 | "Working" | "excellent"
2 | 9 | "Starting" | "good"
3 | 15 | "Starting" | "excellent"
4 | 8 | "Starting" | "ok"
......

Target Table Schema Description:
We transform the input tables to complete the task: The task aims to present the number of invoices each client has by counting the number of invoice entries for each unique client ID from the input invoice data.
The column schema of the target table is as follows:
- Name of Column: "client_id"
  - Description: Unique identifier for a client in the invoice system. Each row represents a distinct client.
  - Requirements
    - Distinct values for each row
    - Unique to each client
- Name of Column: "count(*)"
  - Description: The total number of invoices associated with each client ID, calculated by counting the number of invoice entries for that client.
  - Requirements
    - Non-negative integer values
    - Numerical values representing the count of invoices

Output: 
```
target_df = input_tables['table_1'].groupby('client_id')['invoice_id'].count().reset_index().rename(columns={'invoice_id': 'count(*)'})
```

## Demonstration 2

Input Table:
Name: "table_1"
pilot_name | attribute | b1 | B-52 Bomber | f14 | F-17 Fighter | pc
|---|---|---|---|---|---|---
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

Output: ```
melted_df = pd.melt(input_tables['table_1'], id_vars=['pilot_name', 'attribute'], value_vars=['b1', 'B-52 Bomber', 'f14', 'F-17 Fighter', 'pc'], var_name='plane_name', value_name='age_value')
melted_df['age_value'] = melted_df['age_value'].astype(str).apply(lambda x: x.strip('"') if x.lower() != 'nan' else '')
melted_df['age_value'] = pd.to_numeric(melted_df['age_value'], errors='coerce')
filtered_df = melted_df.dropna(subset=['age_value'])
deduplicated_df = filtered_df.drop_duplicates(subset=['plane_name'])
distinct_count = len(deduplicated_df)
target_df = pd.DataFrame({'count(DISTINCT plane_name)': [distinct_count]})
```