"""Models for Standard Operating Procedures (SOPs) aligned with DB schema."""

from typing import List, Optional
from pydantic import BaseModel, Field, validator


class SOPStep(BaseModel):
    """Single SOP step corresponding to a row in the SOP table."""
    step_number: int = Field(..., description="Sequential step number")
    description: str = Field(..., description="Detailed description of the step")
    query: Optional[str] = Field(
        None,
        description="Optional SQL query executed for this step (can be None)"
    )


class SOPDefinition(BaseModel):
    """Definition of a Standard Operating Procedure constructed from step rows."""
    sop_code: str = Field(..., description="Unique identifier for the SOP (e.g., B007, F027)")
    steps: List[SOPStep] = Field(..., description="Ordered list of steps for the SOP")
    # Entry point for the workflow engine. For numeric step flows, this is typically the first step_number.
    # Your Streamlit app expects `entry_point` to exist on SOPDefinition.
    entry_point: int = Field(
        1,
        description="Initial step number to execute in the SOP workflow"
    )
    # Optional descriptive metadata you can extend later if needed
    version: str = Field("1.0.0", description="Version of the SOP")
    description: Optional[str] = Field(None, description="Optional long description of the SOP")

    @validator("steps")
    def validate_steps_not_empty(cls, v: List[SOPStep]):
        if not v:
            raise ValueError("SOP must contain at least one step")
        return v

    @validator("entry_point")
    def validate_entry_point_in_steps(cls, v: int, values):
        steps: List[SOPStep] = values.get("steps", [])
        if steps and v not in {s.step_number for s in steps}:
            # If an explicit entry_point is set but not present in steps, default to the first step_number.
            # This keeps compatibility with loaders that set entry_point=1 by default.
            first_step = steps[0].step_number
            return first_step
        return v
