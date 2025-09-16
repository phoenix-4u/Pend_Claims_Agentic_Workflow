import sys
from pathlib import Path
import csv
import logging
import os
from datetime import datetime

# Change to project root directory to ensure .env file is found
project_root = Path(__file__).parent.parent
os.chdir(project_root)

# Add project root to the Python path
sys.path.append(str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from app.models.claims import ClaimHeader, ClaimLine
from sqlalchemy.exc import IntegrityError

# Create database connection directly
DATABASE_URL = "sqlite:///./data/claims.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_date(date_str):
    """Parse date string from various formats to YYYY-MM-DD."""
    if not date_str or date_str.strip() == '':
        return None
    try:
        # Try MM-DD-YY format first
        if '-' in date_str:
            parts = date_str.split('-')
            if len(parts) == 3:
                month, day, year = parts
                # Convert 2-digit year to 4-digit
                if len(year) == 2:
                    year = '20' + year if int(year) < 50 else '19' + year
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return date_str  # Return as-is if can't parse
    except:
        return date_str

def insert_claim_headers(db: Session, csv_path: str):
    """Insert claim headers from CSV file."""
    logger.info(f"Inserting claim headers from {csv_path}...")

    headers_inserted = 0
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                # Create ClaimHeader object
                header = ClaimHeader(
                    icn=row.get('icn', '').strip(),
                    claim_type=row.get('claim_type', '').strip() or None,
                    member_id=row.get('member_id', '').strip() or None,
                    member_name=row.get('member_name', '').strip() or None,
                    member_dob=parse_date(row.get('member_dob', '').strip()),
                    member_gender=row.get('member_gender', '').strip() or None,
                    provider_number=row.get('provider_number', '').strip() or None,
                    provider_name=row.get('provider_name', '').strip() or None,
                    provider_type=row.get('provider_type', '').strip() or None,
                    provider_speciality=row.get('provider_specialty', '').strip() or None,
                    total_charge=float(row.get('total_charge', '0').strip()) if row.get('total_charge', '').strip() else None,
                    primary_dx_code=row.get('primary_dx_code', '').strip() or None,
                )

                db.add(header)
                headers_inserted += 1

                # Commit every 100 records to avoid memory issues
                if headers_inserted % 100 == 0:
                    db.commit()
                    logger.info(f"Inserted {headers_inserted} claim headers...")

            except Exception as e:
                logger.error(f"Error inserting claim header {row.get('icn')}: {e}")
                continue

    # Final commit
    db.commit()
    logger.info(f"Successfully inserted {headers_inserted} claim headers.")

def insert_claim_lines(db: Session, csv_path: str):
    """Insert claim lines from CSV file."""
    logger.info(f"Inserting claim lines from {csv_path}...")

    lines_inserted = 0
    with open(csv_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            try:
                # Create ClaimLine object
                line = ClaimLine(
                    icn=row.get('icn', '').strip(),
                    line_no=int(row.get('line_no', '0').strip()) if row.get('line_no', '').strip() else 0,
                    diagnosis_code=row.get('diagnosis_code', '').strip() or None,
                    procedure_code=row.get('procedure_code', '').strip() or None,
                    first_dos=parse_date(row.get('first_dos', '').strip()),
                    last_dos=parse_date(row.get('last_dos', '').strip()),
                    type_of_service=row.get('type_of_service', '').strip() or None,
                    pos_code=row.get('pos_code', '').strip() or None,
                    provider_number=row.get('provider_number', '').strip() or None,
                    charge=float(row.get('charge', '0').strip()) if row.get('charge', '').strip() else None,
                    allowed_amount=float(row.get('allowed_amount', '0').strip()) if row.get('allowed_amount', '').strip() else None,
                    deductible=float(row.get('deductible', '0').strip()) if row.get('deductible', '').strip() else None,
                    coinsurance=float(row.get('coinsurance', '0').strip()) if row.get('coinsurance', '').strip() else None,
                    copay=float(row.get('copay', '0').strip()) if row.get('copay', '').strip() else None,
                    condition_code=row.get('condition_code', '').strip() or None,
                )

                db.add(line)
                lines_inserted += 1

                # Commit every 500 records to avoid memory issues
                if lines_inserted % 500 == 0:
                    db.commit()
                    logger.info(f"Inserted {lines_inserted} claim lines...")

            except Exception as e:
                logger.error(f"Error inserting claim line {row.get('icn')}-{row.get('line_no')}: {e}")
                continue

    # Final commit
    db.commit()
    logger.info(f"Successfully inserted {lines_inserted} claim lines.")

def clear_data(db: Session):
    """Clears all data from the claim tables."""
    logger.info("Clearing existing data...")
    db.query(ClaimLine).delete()
    db.query(ClaimHeader).delete()
    db.commit()
    logger.info("Data cleared.")

def main():
    """Main function to run the CSV insertion process."""
    logger.info("Initializing database and tables...")
    # This ensures tables are created if they don't exist
    Base.metadata.create_all(bind=engine)

    # Define CSV file paths
    headers_csv = Path(__file__).parent.parent / "data" / "claim_headers_synthetic.csv"
    lines_csv = Path(__file__).parent.parent / "data" / "claim_lines_synthetic.csv"

    # Check if files exist
    if not headers_csv.exists():
        logger.error(f"Claim headers CSV file not found: {headers_csv}")
        return

    if not lines_csv.exists():
        logger.error(f"Claim lines CSV file not found: {lines_csv}")
        return

    with get_db() as db:
        try:
            # Clear existing data first
            clear_data(db)

            # Insert claim headers first
            insert_claim_headers(db, str(headers_csv))

            # Then insert claim lines
            insert_claim_lines(db, str(lines_csv))

            logger.info("CSV data insertion completed successfully!")

        except Exception as e:
            logger.error(f"Error during CSV insertion: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    main()
