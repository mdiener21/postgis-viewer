sql = "SELECT * FROM my_table;  "
clean_sql = sql.strip().rstrip(';')
print(f"'{clean_sql}'")
