## Demonstration 1

Input Table:

email
---
"john@example.com"
"jane@example.com"

Data Cleaning Operator: [op_replace_tag]

Output:

```python
target_df = input_table.copy()
extra_rows = pd.DataFrame({
    'email': ["invalid_email"]
})
target_df = pd.concat([input_table, extra_rows], ignore_index=True)
```

After, dirty data with invalid email.

To restore, ErrorDetection(table_name="input_table", column_name="email", func="""def is_valid_email(val): return '@' in val""")  # Then perhaps filter based on tag.
