from typing import Any, TypedDict


class GraphState(TypedDict):
    """Shared state passed between nodes in the LangGraph workflow."""

    question: str
    plan: dict[str, Any] | None
    research_notes: list[str]
    draft: str | None
    critique: dict[str, Any] | None
    iteration: int
    max_iterations: int