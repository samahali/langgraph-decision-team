import json
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from langgraph_decision_team.prompts import (
    CRITIC_SYSTEM_PROMPT,
    FINALIZER_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from langgraph_decision_team.schemas import Critique, Plan, ResearchNotes
from langgraph_decision_team.state import GraphState


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Create and reuse the language model client."""

    return ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.2,
    )


def planner_node(state: GraphState) -> dict[str, Any]:
    """Create a structured plan for answering the user's question."""

    llm = get_llm()
    structured_llm = llm.with_structured_output(Plan)

    plan = structured_llm.invoke(
        [
            SystemMessage(content=PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=state["question"]),
        ]
    )

    return {"plan": plan.model_dump()}

def researcher_node(state: GraphState) -> dict[str, Any]:
    """Produce structured research notes from the question and plan."""

    llm = get_llm()
    structured_llm = llm.with_structured_output(ResearchNotes)

    research_request = {
        "question": state["question"],
        "plan": state["plan"],
    }

    research = structured_llm.invoke(
        [
            SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    research_request,
                    indent=2,
                    ensure_ascii=False,
                )
            ),
        ]
    )

    return {"research_notes": research.notes}


def writer_node(state: GraphState) -> dict[str, Any]:
    """Write or revise a draft using the available workflow context."""

    llm = get_llm()

    writing_request = {
        "question": state["question"],
        "plan": state["plan"],
        "research_notes": state["research_notes"],
        "current_draft": state["draft"],
        "critique": state["critique"],
    }

    response = llm.invoke(
        [
            SystemMessage(content=WRITER_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    writing_request,
                    indent=2,
                    ensure_ascii=False,
                )
            ),
        ]
    )

    if not isinstance(response.content, str):
        raise TypeError("The writer returned non-text content.")

    return {"draft": response.content.strip()}


def critic_node(state: GraphState) -> dict[str, Any]:
    """Evaluate the draft and provide structured improvement feedback."""

    llm = get_llm()
    structured_llm = llm.with_structured_output(Critique)

    critique_request = {
        "question": state["question"],
        "plan": state["plan"],
        "research_notes": state["research_notes"],
        "draft": state["draft"],
    }

    critique = structured_llm.invoke(
        [
            SystemMessage(content=CRITIC_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    critique_request,
                    indent=2,
                    ensure_ascii=False,
                )
            ),
        ]
    )

    return {
        "critique": critique.model_dump(),
        "iteration": state["iteration"] + 1,
    }


def finalizer_node(state: GraphState) -> dict[str, Any]:
    """Produce the polished final answer from the workflow context."""

    llm = get_llm()

    finalization_request = {
        "question": state["question"],
        "plan": state["plan"],
        "research_notes": state["research_notes"],
        "current_draft": state["draft"],
        "critique": state["critique"],
    }

    response = llm.invoke(
        [
            SystemMessage(content=FINALIZER_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    finalization_request,
                    indent=2,
                    ensure_ascii=False,
                )
            ),
        ]
    )

    if not isinstance(response.content, str):
        raise TypeError("The finalizer returned non-text content.")

    return {"draft": response.content.strip()}

    """Produce research notes from the question and its plan."""

    llm = get_llm()

    research_request = {
        "question": state["question"],
        "plan": state["plan"],
    }

    response = llm.invoke(
        [
            SystemMessage(content=RESEARCHER_SYSTEM_PROMPT),
            HumanMessage(
                content=json.dumps(
                    research_request,
                    indent=2,
                    ensure_ascii=False,
                )
            ),
        ]
    )

    if not isinstance(response.content, str):
        raise TypeError("The researcher returned non-text content.")

    notes = [
        line.removeprefix("-").strip()
        for line in response.content.splitlines()
        if line.strip()
    ]

    return {"research_notes": notes}