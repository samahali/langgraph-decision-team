from typing import Literal

from langgraph.graph import END, START, StateGraph

from langgraph_decision_team.nodes import (
    critic_node,
    finalizer_node,
    planner_node,
    researcher_node,
    writer_node,
)
from langgraph_decision_team.state import GraphState


def should_revise(state: GraphState) -> Literal["revise", "finalize"]:
    """Decide whether the writer should revise the draft."""

    critique = state["critique"]

    if critique is None:
        raise ValueError("A critique is required before routing.")

    if state["iteration"] >= state["max_iterations"]:
        return "finalize"

    if critique["score"] < 80:
        return "revise"

    return "finalize"


def build_graph():
    """Build and compile the multi-agent decision workflow."""

    workflow = StateGraph(GraphState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("researcher", researcher_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("critic", critic_node)
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

    workflow.add_edge("finalizer", END)

    return workflow.compile()