from typing import Literal

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from langgraph_decision_team.config import get_settings
from langgraph_decision_team.nodes import (
    critic_node,
    finalizer_node,
    human_review_node,
    planner_node,
    researcher_node,
    writer_node,
)
from langgraph_decision_team.state import GraphState


def create_initial_state(question: str) -> GraphState:
    """Create initial state using configured workflow limits."""

    settings = get_settings()
    return {
        "question": question,
        "plan": None,
        "research_notes": [],
        "sources": [],
        "draft": None,
        "final_answer": None,
        "critique": None,
        "human_feedback": None,
        "human_revision_count": 0,
        "max_human_revisions": settings.max_human_revisions,
        "iteration": 0,
        "max_iterations": settings.max_iterations,
        "quality_threshold": settings.quality_threshold,
        "max_research_sources": settings.max_research_sources,
        "status": "running",
    }


def should_revise(state: GraphState) -> Literal["revise", "finalize"]:
    """Decide whether the writer should revise the draft."""

    critique = state["critique"]

    if critique is None:
        raise ValueError("A critique is required before routing.")

    if state["iteration"] >= state["max_iterations"]:
        return "finalize"

    if critique["score"] < state["quality_threshold"]:
        return "revise"

    return "finalize"


def route_human_review(state: GraphState) -> Literal["end", "revise", "review"]:
    """Route deterministic human decisions without model calls."""

    if state["status"] in {"approved", "cancelled"}:
        return "end"
    if state["status"] == "running":
        return "revise"
    if state["status"] == "revision_limit_reached":
        return "review"

    raise ValueError("Human review did not produce a routable status.")


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """Build and compile the multi-agent decision workflow."""

    workflow = StateGraph(GraphState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("finalizer", finalizer_node)

    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "researcher")
    workflow.add_edge("researcher", "writer")
    workflow.add_edge("writer", "critic")

    workflow.add_conditional_edges(
        "critic",
        should_revise,
        {
            "revise": "writer",
            "finalize": "finalizer",
        },
    )
    workflow.add_edge("finalizer", "human_review")
    workflow.add_conditional_edges(
        "human_review",
        route_human_review,
        {
            "end": END,
            "revise": "writer",
            "review": "human_review",
        },
    )

    return workflow.compile(checkpointer=checkpointer)
