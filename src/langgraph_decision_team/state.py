from typing import Any, Literal, TypedDict

WorkflowStatus = Literal[
    "running",
    "awaiting_human_review",
    "approved",
    "cancelled",
    "revision_limit_reached",
]


class ResearchSource(TypedDict):
    title: str
    url: str


class GraphState(TypedDict):
    """Shared state passed between nodes in the LangGraph workflow."""

    question: str
    plan: dict[str, Any] | None
    research_notes: list[str]
    sources: list[ResearchSource]
    draft: str | None
    final_answer: str | None
    critique: dict[str, Any] | None
    human_feedback: str | None
    human_revision_count: int
    max_human_revisions: int
    iteration: int
    max_iterations: int
    quality_threshold: int
    max_research_sources: int
    status: WorkflowStatus
