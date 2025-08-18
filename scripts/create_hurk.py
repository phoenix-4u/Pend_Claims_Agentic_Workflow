import sqlite3
from pathlib import Path

# Get the project root directory
project_root = Path(__file__).parent.parent

# Define output database path
output_db = project_root / 'data' / 'claims.db'

def create_hruk_table():
    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hruk (
                procedure_code TEXT,
                procedure_name TEXT,
                pos_allowed TEXT,
                provider_type TEXT,
                provider_speciality TEXT
            );
        """)
        cursor.execute("""
            INSERT INTO hruk (procedure_code, procedure_name, pos_allowed, provider_type, provider_speciality) VALUES
            ('69930','Cochlear Implant','24','63','80'),
            ('90863','Impatient Psychiatric/Psychotherapy','21','63','80');
        """)
        conn.commit()
        print("hruk table created and rows inserted successfully.")
    except sqlite3.Error as e:
        print(f"Error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    create_hruk_table()
