import pytest

from langgraph_decision_team.graph import should_revise
from langgraph_decision_team.state import GraphState


def make_state(
    *,
    score: int | None,
    iteration: int = 1,
    max_iterations: int = 2,
) -> GraphState:
    """Create a graph state for routing tests."""

    critique = None if score is None else {"score": score}

    return {
        "question": "Test question",
        "plan": None,
        "research_notes": [],
        "draft": "Test draft",
        "critique": critique,
        "iteration": iteration,
        "max_iterations": max_iterations,
    }


def test_should_revise_when_score_is_below_threshold() -> None:
    state = make_state(score=75)

    assert should_revise(state) == "revise"


def test_should_finalize_when_score_reaches_threshold() -> None:
    state = make_state(score=80)

    assert should_revise(state) == "finalize"


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