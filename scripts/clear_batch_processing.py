#!/usr/bin/env python3
"""
Script to clear batch processing tables for a fresh start.
This script deletes all records from the batch processing related tables:
- sop_results
- claims_processed_lines
- claim_processing_steps
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.base import get_db
from app.models.claims import SOPResult, ClaimProcessedLine, ClaimProcessingStep
from app.config.logging_config import logger

def clear_batch_processing_tables():
    """Clear all batch processing related tables."""
    try:
        logger.info("Starting to clear Bulk Claim processing tables...")

        with get_db() as db:
            # Count records before deletion for reporting
            sop_results_count = db.query(SOPResult).count()
            processed_lines_count = db.query(ClaimProcessedLine).count()
            processing_steps_count = db.query(ClaimProcessingStep).count()

            logger.info(f"Found {sop_results_count} SOP results, {processed_lines_count} processed claims, and {processing_steps_count} processing steps to delete.")

            # Delete all records from batch processing tables
            # Note: Order matters due to foreign key constraints
            db.query(ClaimProcessingStep).delete()
            db.query(ClaimProcessedLine).delete()
            db.query(SOPResult).delete()

            # Commit the changes
            db.commit()

            logger.info("Successfully cleared all Bulk Claim processing tables.")
            print("✅ Bulk Claim processing tables cleared successfully!")
            print(f"   - Deleted {sop_results_count} SOP results")
            print(f"   - Deleted {processed_lines_count} processed claims")
            print(f"   - Deleted {processing_steps_count} processing steps")

    except Exception as e:
        logger.error(f"Error clearing Bulk Claim processing tables: {e}")
        print(f"❌ Error clearing Bulk Claim processing tables: {e}")
        raise

if __name__ == "__main__":
    clear_batch_processing_tables()
