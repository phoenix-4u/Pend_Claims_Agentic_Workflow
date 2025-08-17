"""Script to consolidate B007 and F027 SQL files into a single SOP table."""
import sqlite3
from pathlib import Path
from typing import List, Dict
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sop_consolidation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SOPConsolidator:
    """Consolidates multiple SOP SQL files into a single SOP table."""
    
    def __init__(self, output_db: str = 'consolidated_sops.db'):
        """Initialize the consolidator with output database path."""
        self.output_db = Path(output_db)
        self.conn = None
        self.cur = None
    
    def connect(self):
        """Connect to the SQLite database."""
        self.conn = sqlite3.connect(self.output_db, timeout=15)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        self.cur = self.conn.cursor()
        logger.info(f"Connected to database: {self.output_db}")
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def create_sop_table(self):
        """Create the consolidated SOP table if it doesn't exist."""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS SOP (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sop_code TEXT NOT NULL,
            step_number INTEGER NOT NULL,
            description TEXT NOT NULL,
            query TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        self.cur.execute(create_table_sql)
        self.conn.commit()
        logger.info("Created SOP table")

    def get_all_steps(self) -> List[Dict]:
        """Returns a hardcoded list of all SOP steps."""
        steps = [
            # B007 Steps
            {
                'sop_code': 'B007', 'step_number': 1, 'description': 'Access the Code section of the Medical Policy Database and search to identify the Procedure Code on the claim to determine if the Procedure Code is eligible for the Place of Service (POS) present on the claim',
                'query': None
            },
            {
                'sop_code': 'B007', 'step_number': 2, 'description': 'Compare the Place of Service in the Medical Policy Database to what is coded on HRUK application',
                'query': "ATTACH DATABASE 'hruk.db' AS hrukdb; SELECT DISTINCT r.pos_allowed FROM hrukdb.hruk AS r WHERE r.procedure_code IN (SELECT procedure_code FROM claim_lines WHERE icn = '{icn}');"
            },
            {
                'sop_code': 'B007', 'step_number': 3, 'description': 'If the HRUK application and the Medical Policy Database reflect the same information, then Examiner denies the claim',
                'query': None
            },
            {
                'sop_code': 'B007', 'step_number': 4, 'description': 'If the Medical Policy Database has the Place of Service listed and the HRUK does not then submit a Plog for updates',
                'query': None
            },
            # F027 Steps
            {
                'sop_code': 'F027', 'step_number': 1, 'description': 'Identify the Provider Specialty Code on the claim',
                'query': "SELECT procedure_specialty FROM claim_headers WHERE icn = '{icn}';"
            },
            {
                'sop_code': 'F027', 'step_number': 2, 'description': 'Access the Code section of the Medical Policy Database and search to identify the Specialty Code on the claim to determine if that Provider Specialty is eligible for the service present on the claim',
                'query': None
            },
            {
                'sop_code': 'F027', 'step_number': 3, 'description': 'Compare the Specialty code in the Medical Policy Database to what is coded on HRUK application',
                'query': "ATTACH DATABASE 'hruk.db' AS hrukdb; SELECT DISTINCT r.procedure_speciality FROM hrukdb.hruk r WHERE r.procedure_code IN (SELECT procedure_code FROM claim_lines WHERE icn = '{icn}');"
            },
            {
                'sop_code': 'F027', 'step_number': 4, 'description': 'If the HRUK application and the Medical Policy Database reflect the same information, then Examiner denies the claim',
                'query': None
            },
            {
                'sop_code': 'F027', 'step_number': 5, 'description': 'Compare Provider Specialty on the claim with the Service performed in the claim. If the combination matches (valid) then resolve the pend by overriding the edit',
                'query': "SELECT cl.procedure_code, ch.provider_speciality FROM claim_headers ch JOIN claim_lines cl ON cl.icn = ch.icn WHERE ch.icn = '{icn}';"
            },
            {
                'sop_code': 'F027', 'step_number': 6, 'description': 'Create a Plog in ClearQuest to update the system making the Specialty valid for the Service so future claims do not stop for the F027 edit',
                'query': None
            }
        ]
        return steps

    def insert_steps(self, steps: List[Dict]):
        """Insert steps into the SOP table."""
        # Clear existing steps for these SOP codes to avoid duplicates
        if steps:
            sop_codes = list({step['sop_code'] for step in steps})
            placeholders = ','.join('?' * len(sop_codes))
            self.cur.execute(
                f"DELETE FROM SOP WHERE sop_code IN ({placeholders})",
                sop_codes
            )
            self.conn.commit()
            
            # Insert new steps
            insert_sql = """
            INSERT INTO SOP (sop_code, step_number, description, query)
            VALUES (?, ?, ?, ?)
            """
            
            for step in steps:
                self.cur.execute(insert_sql, (
                    step['sop_code'],
                    step['step_number'],
                    step['description'],
                    step['query']
                ))
            
            self.conn.commit()
            logger.info(f"Inserted/updated {len(steps)} steps for SOP codes: {', '.join(sop_codes)}")
    
    def consolidate_sops(self):
        """Consolidate multiple SOP SQL files into a single table."""
        try:
            self.connect()
            self.create_sop_table()
            
            all_steps = self.get_all_steps()
            
            self.insert_steps(all_steps)
            
            # Verify the data was inserted
            self.cur.execute("SELECT sop_code, COUNT(*) as step_count FROM SOP GROUP BY sop_code")
            results = self.cur.fetchall()
            logger.info("Consolidated SOP counts:")
            for row in results:
                logger.info(f"  {row['sop_code']}: {row['step_count']} steps")
            
            logger.info("Consolidation completed successfully")
            
        except Exception as e:
            logger.error(f"Error during SOP consolidation: {e}", exc_info=True)
            if self.conn:
                self.conn.rollback()
            raise
        finally:
            self.close()


def main():
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    
    # Define output database path
    output_db = project_root / 'data' / 'claims.db'
    
    # Create output directory if it doesn't exist
    output_db.parent.mkdir(parents=True, exist_ok=True)
    
    # Run the consolidation
    consolidator = SOPConsolidator(output_db)
    consolidator.consolidate_sops()
    
    print(f"\nConsolidated SOP database created at: {output_db}")


if __name__ == "__main__":
    main()