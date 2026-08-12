FORBIDDEN = [
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "ALTER",
    "CREATE",
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "TRUNCATE"
]

def validate_sql(sql_query):

    upper_sql = sql_query.upper().strip()

    if not (
        upper_sql.startswith("SELECT")
        or upper_sql.startswith("WITH")
    ):
        return False, "Only SELECT queries are allowed."

    for keyword in FORBIDDEN:
        if keyword in upper_sql:
            return False, f"Unsafe SQL detected: {keyword}"

    return True, "Safe"