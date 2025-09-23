from sqlalchemy import Column, String, Integer, Text, UniqueConstraint
from ..db.base import Base

class SOP(Base):
    """SOP steps table."""
    __tablename__ = 'SOP'

    id = Column(Integer, primary_key=True, autoincrement=True)
    sop_code = Column(String, nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    description = Column(Text, nullable=False)
    query = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint('sop_code', 'step_number', name='uq_sop_code_step'),
    )

    def __repr__(self):
        return f"<SOP(sop_code={self.sop_code}, step={self.step_number})>"
