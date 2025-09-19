import sqlite3

# Connect to the database
conn = sqlite3.connect('claims.db')
cursor = conn.cursor()

# Check if tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='claim_headers'")
table_exists = cursor.fetchone()

if table_exists:
    # Query the count
    cursor.execute("SELECT COUNT(*) FROM claim_headers")
    header_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM claim_lines")
    line_count = cursor.fetchone()[0]

    print(f"Headers: {header_count}, Lines: {line_count}")

    # Check if our specific ICN exists
    cursor.execute("SELECT COUNT(*) FROM claim_headers WHERE icn = '20251220007100'")
    specific_count = cursor.fetchone()[0]
    print(f"Specific ICN count: {specific_count}")
else:
    print("claim_headers table does not exist")

# Close the connection
conn.close()
