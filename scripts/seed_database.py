import sys
from pathlib import Path
import logging

# Add project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import get_db, Base, engine
from app.models.claims import ClaimHeader, ClaimLine, SOPResult, ClaimProcessedLine, ClaimProcessingStep
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_data(db: Session):
    """Clears all data from the relevant tables."""
    logger.info("Clearing existing data...")
    db.query(ClaimProcessingStep).delete()
    db.query(ClaimProcessedLine).delete()
    db.query(SOPResult).delete()
    db.query(ClaimLine).delete()
    db.query(ClaimHeader).delete()
    db.commit()
    logger.info("Data cleared.")

def seed_data(db: Session):
    """Seeds the database with mock claim data."""
    logger.info("Seeding data...")

    # Mock data similar to the original frontend mock data
    claims_to_create = []
    for i in range(1, 26):
        icn = f"ICN{1000 + i}"
        pend_code = "B007" if i % 2 == 0 else "F027"
        
        header = ClaimHeader(
            icn=icn,
            member_name=f"Member Name {i}",
            member_dob="1980-01-15",
            provider_name=f"Provider Name {i}",
            provider_speciality="Cardiology",
            total_charge=5000.00 + (i * 100),
            primary_dx_code="I25.10",
        )
        
        line = ClaimLine(
            icn=icn,
            line_no=1,
            procedure_code="99214",
            diagnosis_code="I25.10",
            first_dos="2023-10-01",
            last_dos="2023-10-01",
            pos_code="11",
            charge=5000.00 + (i * 100),
            condition_code=pend_code,
        )
        
        header.claim_lines.append(line)
        claims_to_create.append(header)

    db.add_all(claims_to_create)
    db.commit()
    logger.info(f"Successfully seeded {len(claims_to_create)} claims.")

def seed_processed_claims(db: Session):
    """Seeds the database with mock processed claim data."""
    logger.info("Seeding processed claims...")

    processed_claims_to_create = [
        ClaimProcessedLine(
            icn=f"ICN{1000 + i}",
            sop_code="B007" if i % 2 == 0 else "F027",
            decision="APPROVE" if i % 3 == 0 else "DENY",
            decision_reason="Claim meets all criteria." if i % 3 == 0 else "Claim does not meet criteria.",
        )
        for i in range(1, 26)
    ]

    db.add_all(processed_claims_to_create)
    db.commit()
    logger.info(f"Successfully seeded {len(processed_claims_to_create)} processed claims.")

def seed_processing_steps(db: Session):
    """Seeds the database with mock claim processing steps."""
    logger.info("Seeding processing steps...")
    steps_to_create = []
    for i in range(1, 26):
        icn = f"ICN{1000 + i}"
        sop_code = "B007" if i % 2 == 0 else "F027"
        decision = "APPROVE" if i % 3 == 0 else "DENY"

        steps_to_create.extend([
            ClaimProcessingStep(
                icn=icn,
                sop_code=sop_code,
                step_number=1,
                description="Initial Validation",
                status="completed",
                timestamp="2023-10-27T10:00:00Z",
                query="SELECT * FROM claim_headers WHERE icn=:icn",
                data='{"result": "valid"}',
                row_count=1,
                execution_time_ms=15.0,
            ),
            ClaimProcessingStep(
                icn=icn,
                sop_code=sop_code,
                step_number=2,
                description="Check Member Eligibility",
                status="completed",
                timestamp="2023-10-27T10:00:05Z",
                query="SELECT * FROM members WHERE member_id=:id",
                data='{"eligible": true}',
                row_count=1,
                execution_time_ms=25.0,
            ),
            ClaimProcessingStep(
                icn=icn,
                sop_code=sop_code,
                step_number=3,
                description="Medical Necessity Review",
                status="failed" if decision == "DENY" else "completed",
                timestamp="2023-10-27T10:00:10Z",
                query="SELECT * FROM medical_policies WHERE code=:code",
                data='{"policy": "not_covered"}' if decision == "DENY" else '{"policy": "covered"}',
                row_count=0 if decision == "DENY" else 1,
                execution_time_ms=50.0,
                error="Procedure not covered under policy" if decision == "DENY" else None,
            ),
        ])
    db.add_all(steps_to_create)
    db.commit()
    logger.info(f"Successfully seeded {len(steps_to_create)} processing steps.")

def main():
    """Main function to run the seeding process."""
    logger.info("Initializing database and tables...")
    # This ensures tables are created if they don't exist
    Base.metadata.create_all(bind=engine)
    
    with get_db() as db:
        try:
            clear_data(db)
            seed_data(db)
            seed_processed_claims(db)
            seed_processing_steps(db)
        finally:
            db.close()

if __name__ == "__main__":
    main()