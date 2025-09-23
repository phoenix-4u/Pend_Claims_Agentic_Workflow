import sqlite3
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent / "data/claims.db"

def create_processing_tables():
    """Create the claims_processed_lines and claim_processing_steps tables."""

    # SQL for claims_processed_lines table
    create_claims_processed_lines = """
    CREATE TABLE IF NOT EXISTS claims_processed_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        icn TEXT NOT NULL,
        sop_code TEXT NOT NULL,
        decision TEXT,
        decision_reason TEXT,
        processed_at TEXT DEFAULT CURRENT_TIMESTAMP,
        processing_results TEXT
    );
    """

    # Create index for better query performance
    index_icn_processed = """
    CREATE INDEX IF NOT EXISTS idx_claims_processed_lines_icn
    ON claims_processed_lines(icn);
    """

    # SQL for claim_processing_steps table
    create_claim_processing_steps = """
    CREATE TABLE IF NOT EXISTS claim_processing_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        icn TEXT NOT NULL,
        sop_code TEXT NOT NULL,
        step_number INTEGER NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        query TEXT,
        data TEXT,
        row_count INTEGER,
        execution_time_ms REAL,
        error TEXT
    );
    """

    # Create indexes for better query performance
    index_icn_steps = """
    CREATE INDEX IF NOT EXISTS idx_claim_processing_steps_icn
    ON claim_processing_steps(icn);
    """

    index_icn_step = """
    CREATE INDEX IF NOT EXISTS idx_claim_processing_steps_icn_step
    ON claim_processing_steps(icn, step_number);
    """

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Create tables
        print("Creating claims_processed_lines table...")
        cursor.execute(create_claims_processed_lines)

        print("Creating index on claims_processed_lines.icn...")
        cursor.execute(index_icn_processed)

        print("Creating claim_processing_steps table...")
        cursor.execute(create_claim_processing_steps)

        print("Creating indexes on claim_processing_steps...")
        cursor.execute(index_icn_steps)
        cursor.execute(index_icn_step)

        # Commit changes
        conn.commit()
        print("✅ All tables created successfully!")

        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('claims_processed_lines', 'claim_processing_steps')")
        tables = cursor.fetchall()
        print(f"\nCreated tables: {[table[0] for table in tables]}")

    except sqlite3.Error as e:
        print(f"❌ Error creating tables: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_processing_tables()
