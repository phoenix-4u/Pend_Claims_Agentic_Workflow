"""Script to seed the database with sample claim data for testing."""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import random

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.db.base import Base
from app.models.claims import ClaimHeader, ClaimLine
from app.config.settings import settings
from app.config.logging_config import logger

# Sample data
SAMPLE_MEMBERS = [
    {"id": "M1001", "name": "John Doe", "dob": "1980-05-15", "gender": "M"},
    {"id": "M1002", "name": "Jane Smith", "dob": "1975-09-22", "gender": "F"},
    {"id": "M1003", "name": "Robert Johnson", "dob": "1990-03-10", "gender": "M"},
]

SAMPLE_PROVIDERS = [
    {"id": "P2001", "name": "City Medical Group", "type": "GROUP_PRACTICE", "specialty": "FAMILY_MEDICINE"},
    {"id": "P2002", "name": "Downtown Physical Therapy", "type": "PHYSICAL_THERAPY", "specialty": "PHYSICAL_THERAPY"},
    {"id": "P2003", "name": "Advanced Radiology", "type": "DIAGNOSTIC", "specialty": "RADIOLOGY"},
]

SAMPLE_PROCEDURES = [
    {"code": "97110", "desc": "Therapeutic exercises"},
    {"code": "97112", "desc": "Neuromuscular reeducation"},
    {"code": "97140", "desc": "Manual therapy"},
    {"code": "99213", "desc": "Office visit, established patient"},
    {"code": "70450", "desc": "CT head/brain without contrast"},
]

SAMPLE_DIAGNOSES = [
    {"code": "M54.5", "desc": "Low back pain"},
    {"code": "M54.9", "desc": "Dorsalgia, unspecified"},
    {"code": "M25.551", "desc": "Pain in right hip"},
    {"code": "S72.001A", "desc": "Fracture of unspecified part of neck of right femur"},
]

def generate_sample_claims(count: int = 5):
    """Generate sample claim data."""
    claims = []
    
    for i in range(1, count + 1):
        member = random.choice(SAMPLE_MEMBERS)
        provider = random.choice(SAMPLE_PROVIDERS)
        
        # Generate claim header
        icn = f"ICN{1000000 + i}"
        claim = {
            "icn": icn,
            "claim_type": random.choice(["OUTPATIENT", "INPATIENT", "EMERGENCY"]),
            "member_id": member["id"],
            "member_name": member["name"],
            "member_dob": member["dob"],
            "member_gender": member["gender"],
            "provider_number": provider["id"],
            "provider_name": provider["name"],
            "provider_type": provider["type"],
            "provider_specialty": provider["specialty"],
            "total_charge": 0,  # Will be updated with line items
            "primary_dx_code": random.choice(SAMPLE_DIAGNOSES)["code"],
            "claim_lines": []
        }
        
        # Generate claim lines (1-5 per claim)
        num_lines = random.randint(1, 5)
        total_charge = 0
        
        for j in range(1, num_lines + 1):
            procedure = random.choice(SAMPLE_PROCEDURES)
            diagnosis = random.choice(SAMPLE_DIAGNOSES)
            units = random.randint(1, 4)
            charge = round(random.uniform(50, 500) * units, 2)
            total_charge += charge
            
            # Random date within the last 30 days
            service_date = (datetime.now() - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
            
            claim_line = {
                "icn": icn,
                "line_no": j,
                "diagnosis_code": diagnosis["code"],
                "procedure_code": procedure["code"],
                "first_dos": service_date,
                "last_dos": service_date,
                "type_of_service": "PHYSICAL_THERAPY" if "97" in procedure["code"][:2] else "OFFICE_VISIT",
                "pos_code": "11",  # Office
                "provider_number": provider["id"],
                "charge": charge,
                "allowed_amount": round(charge * 0.8, 2),  # 80% of charge
                "deductible": round(charge * 0.1, 2),  # 10% of charge
                "coinsurance": round(charge * 0.1, 2),  # 10% of charge
                "copay": 20.00 if random.random() > 0.7 else 0.00,  # 30% chance of copay
                "condition_code": "B007" if "97" in procedure["code"][:2] else ""
            }
            
            claim["claim_lines"].append(claim_line)
        
        # Update total charge
        claim["total_charge"] = total_charge
        claims.append(claim)
    
    return claims

def seed_database():
    """Seed the database with sample data."""
    # Create database engine
    engine = create_engine(settings.DATABASE_URL)
    
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    # Create a session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    try:
        # Clear existing data
        db.query(ClaimLine).delete()
        db.query(ClaimHeader).delete()
        db.commit()
        
        # Generate sample claims
        claims = generate_sample_claims(10)
        
        # Insert claims
        for claim_data in claims:
            # Create claim header
            header_data = {k: v for k, v in claim_data.items() if k != "claim_lines"}
            claim_header = ClaimHeader(**header_data)
            db.add(claim_header)
            
            # Create claim lines
            for line_data in claim_data["claim_lines"]:
                claim_line = ClaimLine(**line_data)
                db.add(claim_line)
            
            db.commit()
            
            logger.info(f"Added claim {claim_header.icn} with {len(claim_data['claim_lines'])} lines")
        
        logger.info("Database seeded successfully!")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
