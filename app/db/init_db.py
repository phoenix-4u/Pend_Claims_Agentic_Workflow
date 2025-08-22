"""Initialize the database with tables and sample data."""
import os
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.db.base import Base, engine, SessionLocal
from app.models.claims import ClaimHeader, ClaimLine, SOPResult
from app.models.sops import SOP
from app.config.settings import settings
from app.config.logging_config import logger

def init_db():
    """Initialize the database with tables and sample data."""
    try:
        logger.info("Creating database tables...")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        logger.info("Database tables created successfully.")
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def clear_db():
    """Drop all tables from the database."""
    try:
        logger.warning("Dropping all database tables...")
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped.")
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database initialization utility")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all tables before recreating them"
    )
    
    args = parser.parse_args()
    
    if args.reset:
        clear_db()
    
    init_db()
    logger.info("Database initialization complete.")
