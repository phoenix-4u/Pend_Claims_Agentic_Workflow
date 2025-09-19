"""Database CRUD operations for claims processing."""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import json

from ..models.claims import ClaimHeader, ClaimLine, SOPResult, ClaimProcessedLine, ClaimProcessingStep
from ..models.sops import SOP
from ..config.logging_config import logger

class ClaimCRUD:
    """CRUD operations for claim data."""
    
    @staticmethod
    def get_claim_header(db: Session, icn: str) -> Optional[ClaimHeader]:
        """Retrieve a claim header by ICN."""
        try:
            return db.query(ClaimHeader).filter(ClaimHeader.icn == icn).first()
        except Exception as e:
            logger.error(f"Error getting claim header for ICN {icn}: {e}")
            raise
    
    @staticmethod
    def get_claim_lines(db: Session, icn: str) -> List[ClaimLine]:
        """Retrieve all claim lines for a given ICN."""
        try:
            return db.query(ClaimLine).filter(ClaimLine.icn == icn).order_by(ClaimLine.line_no).all()
        except Exception as e:
            logger.error(f"Error getting claim lines for ICN {icn}: {e}")
            raise
    
    @staticmethod
    def get_claim_with_lines(db: Session, icn: str) -> Dict[str, Any]:
        """Retrieve a claim with all its lines as a dictionary."""
        try:
            claim = ClaimCRUD.get_claim_header(db, icn)
            if not claim:
                return None
                
            claim_dict = {c.name: getattr(claim, c.name) for c in claim.__table__.columns}
            claim_dict['claim_lines'] = [
                {c.name: getattr(line, c.name) for c in ClaimLine.__table__.columns}
                for line in ClaimCRUD.get_claim_lines(db, icn)
            ]
            return claim_dict
        except Exception as e:
            logger.error(f"Error getting claim with lines for ICN {icn}: {e}")
            raise
    
    @staticmethod
    def get_all_claims_with_details(db: Session) -> List[Dict[str, Any]]:
        """Retrieve all claims with their lines."""
        try:
            claims = db.query(ClaimHeader).all()
            claim_list = []
            for claim in claims:
                claim_dict = {c.name: getattr(claim, c.name) for c in claim.__table__.columns}
                claim_dict['claim_lines'] = [
                    {c.name: getattr(line, c.name) for c in ClaimLine.__table__.columns}
                    for line in ClaimCRUD.get_claim_lines(db, claim.icn)
                ]
                claim_list.append(claim_dict)
            return claim_list
        except Exception as e:
            logger.error(f"Error getting all claims with details: {e}")
            raise
    
    @staticmethod
    def get_condition_codes(db: Session, icn: str) -> List[str]:
        """Get all unique condition codes for a claim."""
        try:
            result = db.query(ClaimLine.condition_code).filter(
                ClaimLine.icn == icn,
                ClaimLine.condition_code.isnot(None)
            ).distinct().all()
            return [r[0] for r in result if r[0]]
        except Exception as e:
            logger.error(f"Error getting condition codes for ICN {icn}: {e}")
            raise
    
    @staticmethod
    def create_sop_result(
        db: Session,
        icn: str,
        sop_code: str,
        step_number: int,
        step_name: str,
        status: str,
        result_data: Optional[Dict] = None,
        error_message: Optional[str] = None
    ) -> SOPResult:
        """Create a new SOP processing result."""
        try:
            result = SOPResult(
                icn=icn,
                sop_code=sop_code,
                step_number=step_number,
                step_name=step_name,
                status=status,
                result_data=str(result_data) if result_data else None,
                error_message=error_message
            )
            db.add(result)
            db.commit()
            db.refresh(result)
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating SOP result for ICN {icn}, SOP {sop_code}: {e}")
            raise
    
    @staticmethod
    def get_sop_results(
        db: Session,
        icn: str,
        sop_code: Optional[str] = None
    ) -> List[SOPResult]:
        """Get all SOP results for a claim, optionally filtered by SOP code."""
        try:
            query = db.query(SOPResult).filter(SOPResult.icn == icn)
            if sop_code:
                query = query.filter(SOPResult.sop_code == sop_code)
            return query.order_by(SOPResult.step_number).all()
        except Exception as e:
            logger.error(f"Error getting SOP results for ICN {icn}: {e}")
            raise

    @staticmethod
    def create_claim_processed(db: Session, icn: str, sop_code: str, decision: str, decision_reason: str, processing_results: Dict[str, Any]) -> ClaimProcessedLine:
        """Create a new processed claim line."""
        try:
            processed_line = ClaimProcessedLine(
                icn=icn,
                sop_code=sop_code,
                decision=decision,
                decision_reason=decision_reason,
                processing_results=json.dumps(processing_results, default=str)
            )
            db.add(processed_line)
            db.commit()
            db.refresh(processed_line)
            logger.info(f"Saved processed result for ICN {icn} to the database.")
            return processed_line
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating processed claim line for ICN {icn}: {e}")
            raise

    @staticmethod
    def get_all_processed_claims(db: Session) -> List[ClaimProcessedLine]:
        """Retrieve all processed claims, ensuring only the most recent entry for each ICN."""
        try:
            # Subquery to find the latest processed_at for each icn
            from sqlalchemy import func
            subquery = db.query(
                ClaimProcessedLine.icn,
                func.max(ClaimProcessedLine.id).label('max_id')
            ).group_by(ClaimProcessedLine.icn).subquery()

            # Join the original table with the subquery to get the full record of the latest entry
            return db.query(ClaimProcessedLine).join(
                subquery,
                and_(
                    ClaimProcessedLine.icn == subquery.c.icn,
                    ClaimProcessedLine.id == subquery.c.max_id
                )
            ).all()
        except Exception as e:
            logger.error(f"Error getting all processed claims: {e}")
            raise

    @staticmethod
    def create_claim_processing_step(db: Session, icn: str, sop_code: str, step_data: Dict[str, Any]) -> ClaimProcessingStep:
        """Create a new claim processing step."""
        try:
            step = ClaimProcessingStep(
                icn=icn,
                sop_code=sop_code,
                step_number=step_data.get("step_number"),
                description=step_data.get("description"),
                status=step_data.get("status"),
                timestamp=step_data.get("timestamp"),
                query=step_data.get("query"),
                data=json.dumps(step_data.get("data"), default=str),
                row_count=step_data.get("row_count"),
                execution_time_ms=step_data.get("execution_time_ms"),
                error=step_data.get("error")
            )
            db.add(step)
            db.commit()
            db.refresh(step)
            return step
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating claim processing step for ICN {icn}: {e}")
            raise

    @staticmethod
    def get_claim_processing_steps(db: Session, icn: str) -> List[ClaimProcessingStep]:
        """Retrieve all processing steps for a given ICN."""
        try:
            return db.query(ClaimProcessingStep).filter(ClaimProcessingStep.icn == icn).order_by(ClaimProcessingStep.step_number).all()
        except Exception as e:
            logger.error(f"Error getting claim processing steps for ICN {icn}: {e}")
            raise

# Create an instance for easier importing
crud = ClaimCRUD()

class SOPCRUD:
    """CRUD operations for SOP data."""
    
    @staticmethod
    def create_sop(
        db: Session,
        sop_code: str,
        step_number: int,
        description: str,
        query: Optional[str]
    ) -> SOP:
        """Create a new SOP step."""
        try:
            sop = SOP(
                sop_code=sop_code,
                step_number=step_number,
                description=description,
                query=query
            )
            db.add(sop)
            db.commit()
            db.refresh(sop)
            return sop
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating SOP for SOP Code {sop_code}: {e}")
            raise

sop_crud = SOPCRUD()
