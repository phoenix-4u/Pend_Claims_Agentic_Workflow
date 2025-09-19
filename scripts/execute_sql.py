import sqlite3

# Connect to the database
conn = sqlite3.connect('data/claims.db')
cursor = conn.cursor()

# Read and execute the SQL file
with open('claims_data.sql', 'r') as f:
    sql = f.read()

cursor.executescript(sql)
conn.commit()

print("SQL executed successfully")

# Close the connection
conn.close()
