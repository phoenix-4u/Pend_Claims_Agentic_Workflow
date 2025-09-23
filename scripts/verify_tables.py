import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "claims.db"

def verify_tables():
    """Verify that the processing tables were created successfully."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = cursor.fetchall()
        print("All tables in database:")
        for table in all_tables:
            print(f"  - {table[0]}")

        # Check specifically for our new tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('claims_processed_lines', 'claim_processing_steps')")
        processing_tables = cursor.fetchall()

        if processing_tables:
            print(f"\n✅ Found processing tables: {[table[0] for table in processing_tables]}")

            # Check schema for each table
            for table_name in ['claims_processed_lines', 'claim_processing_steps']:
                print(f"\n--- Schema for {table_name} ---")
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                for col in columns:
                    print(f"  {col[1]} ({col[2]}) {'NOT NULL' if col[3] else ''} {'PRIMARY KEY' if col[5] else ''}")

                # Check indexes
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?", (table_name,))
                indexes = cursor.fetchall()
                if indexes:
                    print(f"  Indexes: {[idx[0] for idx in indexes]}")
        else:
            print("\n❌ Processing tables not found!")

    except sqlite3.Error as e:
        print(f"❌ Error verifying tables: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_tables()
