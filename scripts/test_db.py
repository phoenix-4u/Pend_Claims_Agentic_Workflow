import sqlite3

# Connect to the database
conn = sqlite3.connect('claims.db')
cursor = conn.cursor()

# Execute a query
cursor.execute("SELECT DISTINCT icn FROM claim_headers LIMIT 5;")
icns = cursor.fetchall()
print("Available ICNs:", [row[0] for row in icns])

# Don't forget to close the connection
conn.close()