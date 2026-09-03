from pydantic import BaseModel, Field


class Plan(BaseModel):
    """Structured plan produced by the planner node."""

    steps: list[str] = Field(
        description="Ordered steps required to answer the user's question."
    )
    key_risks: list[str] = Field(
        description="Important risks and unknowns that should be considered."
    )
    desired_output_structure: list[str] = Field(
        description="Headings that should appear in the final answer."
    )


class Critique(BaseModel):
    """Structured evaluation produced by the critic node."""

    issues: list[str] = Field(
        description="Specific problems found in the current draft."
    )
    missing_points: list[str] = Field(
        description="Important considerations missing from the draft."
    )
    hallucination_risks: list[str] = Field(
        description="Claims that may be inaccurate or unsupported."
    )
    score: int = Field(
        ge=0,
        le=100,
        description="Overall quality score from 0 to 100.",
    )
    fix_instructions: list[str] = Field(
        description="Specific actions the writer should take to improve the draft."
    )
