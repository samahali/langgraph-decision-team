import pytest

from langgraph_decision_team.graph import route_human_review, should_revise
from langgraph_decision_team.state import GraphState, WorkflowStatus


def make_state(
    *,
    score: int | None,
    iteration: int = 1,
    max_iterations: int = 2,
    quality_threshold: int = 80,
) -> GraphState:
    """Create a graph state for routing tests."""

    critique = None if score is None else {"score": score}

    return {
        "question": "Test question",
        "plan": None,
        "research_notes": [],
        "sources": [],
        "draft": "Test draft",
        "final_answer": None,
        "critique": critique,
        "human_feedback": None,
        "human_revision_count": 0,
        "max_human_revisions": 2,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "quality_threshold": quality_threshold,
        "max_research_sources": 10,
        "status": "running",
    }


def test_should_revise_when_score_is_below_threshold() -> None:
    state = make_state(score=75)

    assert should_revise(state) == "revise"


def test_should_finalize_when_score_reaches_threshold() -> None:
    state = make_state(score=80)

    assert should_revise(state) == "finalize"


def test_should_use_configured_quality_threshold() -> None:
    state = make_state(score=80, quality_threshold=90)

    assert should_revise(state) == "revise"


def test_should_finalize_at_maximum_iterations() -> None:
    state = make_state(
        score=40,
        iteration=2,
        max_iterations=2,
    )

    assert should_revise(state) == "finalize"


def test_should_raise_when_critique_is_missing() -> None:
    state = make_state(score=None)

    with pytest.raises(
        ValueError,
        match="A critique is required before routing.",
    ):
        should_revise(state)


@pytest.mark.parametrize(
    ("status", "route"),
    [
        ("approved", "end"),
        ("cancelled", "end"),
        ("running", "revise"),
        ("revision_limit_reached", "review"),
    ],
)
def test_route_human_review(status: WorkflowStatus, route: str) -> None:
    state = make_state(score=90)
    state["status"] = status

    assert route_human_review(state) == route
