import json
from functools import lru_cache
from typing import Any, cast
from urllib.parse import urlparse

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from langgraph_decision_team.config import get_settings
from langgraph_decision_team.prompts import (
    CRITIC_SYSTEM_PROMPT,
    FINALIZER_SYSTEM_PROMPT,
    PLANNER_SYSTEM_PROMPT,
    RESEARCHER_SYSTEM_PROMPT,
    WRITER_SYSTEM_PROMPT,
)
from langgraph_decision_team.schemas import Critique, Plan
from langgraph_decision_team.state import GraphState, ResearchSource


@lru_cache(maxsize=1)
def get_llm() -> ChatOpenAI:
    """Create and reuse the language model client."""

    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.temperature,
    )


@lru_cache(maxsize=1)
def get_research_llm() -> ChatOpenAI:
    """Create a model that exposes web-search content and citations."""

    settings = get_settings()
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.temperature,
        output_version="responses/v1",
        include=["web_search_call.action.sources"],
    )


def planner_node(state: GraphState) -> dict[str, Any]:
    """Create a structured plan for answering the user's question."""

    llm = get_llm()
    structured_llm = llm.with_structured_output(Plan)

    plan = cast(
        Plan,
        structured_llm.invoke(
            [
                SystemMessage(content=PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=state["question"]),
            ]
        ),
    )

    return {"plan": plan.model_dump()}


def researcher_node(state: GraphState) -> dict[str, Any]:
    """Search the web and return research notes with cited sources."""

    # OWASP LLM10: one read-only capability; no arbitrary tool execution.
    web_llm = get_research_llm().bind_tools(
        [{"type": "web_search"}],
        tool_choice="web_search",
    )

    research_request = {
        "question": state["question"],
        "plan": state["plan"],
    }

    response = web_llm.invoke(
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

    if not isinstance(response, AIMessage):
        raise TypeError("The researcher returned an invalid message.")

    notes: list[str] = []
    sources: list[ResearchSource] = []
    seen_urls: set[str] = set()

    def add_source(url: object, title: object) -> None:
        if not isinstance(url, str) or url in seen_urls:
            return
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return
        if len(sources) >= state["max_research_sources"]:
            return
        sources.append(
            {
                "title": title if isinstance(title, str) else url,
                "url": url,
            }
        )
        seen_urls.add(url)

    for block in response.content_blocks:
        if block.get("type") == "web_search_call":
            action = block.get("action")
            if isinstance(action, dict):
                raw_sources = action.get("sources", [])
                if isinstance(raw_sources, list):
                    for source in raw_sources:
                        if isinstance(source, dict):
                            add_source(source.get("url"), source.get("title"))
            continue

        if block.get("type") != "text":
            continue

        text = block.get("text")
        if isinstance(text, str):
            notes.extend(line.strip(" -") for line in text.splitlines() if line.strip())

        annotations = block.get("annotations", [])
        if not isinstance(annotations, list):
            continue

        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            url = annotation.get("url")
            if annotation.get("type") not in {
                "citation",
                "url_citation",
            }:
                continue
            add_source(url, annotation.get("title"))

    if not notes or not sources:
        raise ValueError("Web research must return text and at least one cited source.")

    return {"research_notes": notes, "sources": sources}


def writer_node(state: GraphState) -> dict[str, Any]:
    """Write or revise a draft using the available workflow context."""

    llm = get_llm()

    writing_request = {
        "question": state["question"],
        "plan": state["plan"],
        "research_notes": state["research_notes"],
        "sources": state["sources"],
        "current_draft": state["draft"],
        "critique": state["critique"],
        "human_feedback": state["human_feedback"],
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
        "sources": state["sources"],
        "draft": state["draft"],
    }

    critique = cast(
        Critique,
        structured_llm.invoke(
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
        ),
    )

    return {
        "critique": critique.model_dump(),
        "iteration": state["iteration"] + 1,
    }


def human_review_node(state: GraphState) -> dict[str, Any]:
    """Pause after finalization and apply a bounded human decision."""

    critique = state["critique"]
    if critique is None:
        raise ValueError("Human review requires a critique.")

    decision = interrupt(
        {
            "type": "final_answer_review",
            "final_answer": state["final_answer"],
            "critic_score": critique["score"],
            "human_revision_count": state["human_revision_count"],
            "max_human_revisions": state["max_human_revisions"],
            "status": state["status"],
        }
    )

    if not isinstance(decision, dict) or decision.get("action") not in {
        "approve",
        "revise",
        "cancel",
    }:
        raise ValueError("Human review requires approve, revise, or cancel.")

    action = decision["action"]
    if action == "approve":
        return {"status": "approved", "human_feedback": None}
    if action == "cancel":
        return {"status": "cancelled", "human_feedback": None}

    if state["human_revision_count"] >= state["max_human_revisions"]:
        return {"status": "revision_limit_reached", "human_feedback": None}

    feedback = decision.get("feedback")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError("Human revision requires feedback.")

    return {
        "final_answer": None,
        "human_feedback": feedback.strip(),
        "human_revision_count": state["human_revision_count"] + 1,
        "iteration": 0,
        "status": "running",
    }


def finalizer_node(state: GraphState) -> dict[str, Any]:
    """Produce the polished final answer from the workflow context."""

    llm = get_llm()

    finalization_request = {
        "question": state["question"],
        "plan": state["plan"],
        "research_notes": state["research_notes"],
        "sources": state["sources"],
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

    return {
        "final_answer": response.content.strip(),
        "status": "awaiting_human_review",
    }
