"""Database models for claims processing."""
from datetime import date
from sqlalchemy import Column, String, Integer, Float, Date, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..db.base import Base

class ClaimHeader(Base):
    """Claim header information (one per claim)."""
    __tablename__ = 'claim_headers'
    
    icn = Column(String, primary_key=True, index=True, comment='Internal Control Number')
    claim_type = Column(String, nullable=True, comment='Type of claim')
    member_id = Column(String, nullable=True, comment='Member identifier')
    member_name = Column(String, nullable=True, comment='Member full name')
    member_dob = Column(String, nullable=True, comment='Member date of birth (YYYY-MM-DD)')
    member_gender = Column(String(10), nullable=True, comment='Member gender')
    provider_number = Column(String, nullable=True, comment='Provider identifier')
    provider_name = Column(String, nullable=True, comment='Provider full name')
    provider_type = Column(String, nullable=True, comment='Type of provider')
    provider_speciality = Column(String, nullable=True, comment='Provider speciality')
    total_charge = Column(Float, nullable=True, comment='Total charge amount')
    primary_dx_code = Column(String, nullable=True, comment='Primary diagnosis code')
    
    # Relationship to claim lines
    claim_lines = relationship("ClaimLine", back_populates="header", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ClaimHeader(icn={self.icn}, member={self.member_name}, provider={self.provider_name})>"


class ClaimLine(Base):
    """Claim line items (one or more per claim)."""
    __tablename__ = 'claim_lines'
    
    icn = Column(String, ForeignKey('claim_headers.icn', ondelete='CASCADE'), primary_key=True)
    line_no = Column(Integer, primary_key=True, comment='Line number')
    diagnosis_code = Column(String, nullable=True, comment='Diagnosis code')
    procedure_code = Column(String, nullable=True, comment='Procedure code')
    first_dos = Column(String, nullable=True, comment='First date of service (YYYY-MM-DD)')
    last_dos = Column(String, nullable=True, comment='Last date of service (YYYY-MM-DD)')
    type_of_service = Column(String, nullable=True, comment='Type of service')
    pos_code = Column(String, nullable=True, comment='Place of service code')
    provider_number = Column(String, nullable=True, comment='Rendering provider number')
    charge = Column(Float, nullable=True, comment='Charged amount')
    allowed_amount = Column(Float, nullable=True, comment='Allowed amount')
    deductible = Column(Float, nullable=True, comment='Deductible amount')
    coinsurance = Column(Float, nullable=True, comment='Coinsurance amount')
    copay = Column(Float, nullable=True, comment='Copay amount')
    condition_code = Column(String, nullable=True, comment='Condition code (e.g., F027, B007)')
    
    # Relationship to claim header
    header = relationship("ClaimHeader", back_populates="claim_lines")
    
    def __repr__(self):
        return f"<ClaimLine(icn={self.icn}, line={self.line_no}, procedure={self.procedure_code})>"


class SOPResult(Base):
    """Results from SOP processing."""
    __tablename__ = 'sop_results'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    icn = Column(String, index=True, nullable=False, comment='Related claim ICN')
    sop_code = Column(String, nullable=False, comment='SOP code (e.g., B007, F027)')
    step_number = Column(Integer, nullable=False, comment='Step number in the SOP')
    step_name = Column(String, nullable=False, comment='Name/description of the step')
    status = Column(String, nullable=False, comment='Status: pending, success, failed')
    result_data = Column(Text, nullable=True, comment='JSON string of result data')
    error_message = Column(Text, nullable=True, comment='Error message if step failed')
    created_at = Column(String, server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<SOPResult(icn={self.icn}, sop={self.sop_code}, step={self.step_number}, status={self.status})>"


class ClaimProcessedLine(Base):
    """Stores the results of processed claims."""
    __tablename__ = 'claims_processed_lines'

    id = Column(Integer, primary_key=True, autoincrement=True)
    icn = Column(String, index=True, nullable=False, comment='Related claim ICN')
    sop_code = Column(String, nullable=False, comment='SOP code used for processing')
    decision = Column(String, nullable=True, comment='Final decision (e.g., APPROVE, DENY, PEND)')
    decision_reason = Column(Text, nullable=True, comment='Reason for the decision')
    processed_at = Column(String, server_default=func.now(), nullable=False)
    processing_results = Column(Text, nullable=True, comment='Full JSON output from the claim processing workflow')

    def __repr__(self):
        return f"<ClaimProcessedLine(icn={self.icn}, decision={self.decision}, sop_code={self.sop_code})>"


class ClaimProcessingStep(Base):
    """Stores the detailed results of each step of the claim processing workflow."""
    __tablename__ = 'claim_processing_steps'

    id = Column(Integer, primary_key=True, autoincrement=True)
    icn = Column(String, index=True, nullable=False, comment='Related claim ICN')
    sop_code = Column(String, nullable=False, comment='SOP code used for processing')
    step_number = Column(Integer, nullable=False, comment='Step number in the SOP')
    description = Column(String, nullable=True, comment='Description of the step')
    status = Column(String, nullable=False, comment='Status of the step (e.g., completed, failed)')
    timestamp = Column(String, nullable=False, comment='Timestamp of the step execution')
    query = Column(Text, nullable=True, comment='SQL query executed in the step')
    data = Column(Text, nullable=True, comment='JSON string of the data returned by the query')
    row_count = Column(Integer, nullable=True, comment='Number of rows returned by the query')
    execution_time_ms = Column(Float, nullable=True, comment='Execution time of the query in milliseconds')
    error = Column(Text, nullable=True, comment='Error message if the step failed')

    def __repr__(self):
        return f"<ClaimProcessingStep(icn={self.icn}, sop_code={self.sop_code}, step={self.step_number})>"
