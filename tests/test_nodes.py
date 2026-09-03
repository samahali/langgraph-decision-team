import json
from collections import defaultdict, deque
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from langgraph_decision_team import nodes
from langgraph_decision_team.graph import build_graph, route_human_review
from langgraph_decision_team.nodes import human_review_node
from langgraph_decision_team.schemas import Critique, Plan
from langgraph_decision_team.state import GraphState


class FakeStructuredLLM:
    def __init__(self, responses: deque[Any]) -> None:
        self.responses = responses

    def invoke(self, _messages: Any) -> Any:
        return self.responses.popleft()


class FakeLLM:
    """Small deterministic replacement for ChatOpenAI."""

    def __init__(
        self,
        *,
        text: tuple[str, ...] = (),
        structured: dict[type[Any], tuple[Any, ...]] | None = None,
    ) -> None:
        self.text = deque(text)
        self.invocations: list[Any] = []
        self.structured: defaultdict[type[Any], deque[Any]] = defaultdict(deque)
        for schema, responses in (structured or {}).items():
            self.structured[schema].extend(responses)

    def invoke(self, _messages: Any) -> AIMessage:
        self.invocations.append(_messages)
        return AIMessage(content=self.text.popleft())

    def bind_tools(self, _tools: Any, **_kwargs: Any) -> "FakeLLM":
        return self

    def with_structured_output(self, schema: type[Any]) -> FakeStructuredLLM:
        return FakeStructuredLLM(self.structured[schema])


def make_state(**changes: Any) -> GraphState:
    state: GraphState = {
        "question": "Should we launch the product?",
        "plan": {
            "steps": ["Research"],
            "key_risks": [],
            "desired_output_structure": [],
        },
        "research_notes": ["Demand is growing."],
        "sources": [{"title": "Market report", "url": "https://example.com"}],
        "draft": "Initial draft",
        "final_answer": None,
        "critique": None,
        "human_feedback": None,
        "human_revision_count": 0,
        "max_human_revisions": 2,
        "iteration": 0,
        "max_iterations": 2,
        "quality_threshold": 80,
        "max_research_sources": 10,
        "status": "running",
    }
    return cast(GraphState, {**state, **changes})


def use_fake_llm(monkeypatch: pytest.MonkeyPatch, fake: FakeLLM) -> None:
    monkeypatch.setattr(nodes, "get_llm", lambda: fake)
    monkeypatch.setattr(nodes, "get_research_llm", lambda: fake)


def test_planner_node_returns_serialized_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = Plan(
        steps=["Compare options"],
        key_risks=["Budget"],
        desired_output_structure=["Recommendation"],
    )
    use_fake_llm(monkeypatch, FakeLLM(structured={Plan: (plan,)}))

    assert nodes.planner_node(make_state()) == {"plan": plan.model_dump()}


def test_researcher_node_returns_notes(monkeypatch: pytest.MonkeyPatch) -> None:
    response = AIMessage(
        content=[
            {
                "type": "web_search_call",
                "action": {
                    "sources": [
                        {
                            "title": "Primary source",
                            "url": "https://example.com/research",
                        }
                    ]
                },
            },
            {
                "type": "text",
                "text": "Finding",
                "annotations": [],
            },
        ],
        response_metadata={"output_version": "v1"},
    )
    fake = FakeLLM()
    monkeypatch.setattr(fake, "invoke", lambda _messages: response)
    use_fake_llm(monkeypatch, fake)

    assert nodes.researcher_node(make_state()) == {
        "research_notes": ["Finding"],
        "sources": [{"title": "Primary source", "url": "https://example.com/research"}],
    }


def test_researcher_rejects_untrusted_urls_and_caps_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = AIMessage(
        content=[
            {
                "type": "text",
                "text": "Finding",
                "annotations": [
                    {
                        "type": "url_citation",
                        "title": "Bad",
                        "url": "javascript:alert(1)",
                    },
                    {
                        "type": "url_citation",
                        "title": "Good",
                        "url": "https://example.com",
                    },
                    {
                        "type": "url_citation",
                        "title": "Ignored",
                        "url": "https://other.example",
                    },
                ],
            },
        ],
        response_metadata={"output_version": "v1"},
    )
    fake = FakeLLM()
    monkeypatch.setattr(fake, "invoke", lambda _messages: response)
    use_fake_llm(monkeypatch, fake)

    result = nodes.researcher_node(make_state(max_research_sources=1))

    assert result["sources"] == [{"title": "Good", "url": "https://example.com"}]


def test_writer_node_returns_trimmed_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLLM(text=("  Better draft  ",))
    use_fake_llm(monkeypatch, fake)

    assert nodes.writer_node(make_state(human_feedback="Use a shorter comparison")) == {
        "draft": "Better draft"
    }
    request = json.loads(fake.invocations[0][-1].content)
    assert request["human_feedback"] == "Use a shorter comparison"


def test_critic_node_returns_critique_and_increments_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    critique = Critique(
        issues=["Too vague"],
        missing_points=["Cost"],
        hallucination_risks=[],
        score=70,
        fix_instructions=["Add numbers"],
    )
    use_fake_llm(monkeypatch, FakeLLM(structured={Critique: (critique,)}))

    result = nodes.critic_node(make_state(iteration=1))

    assert result == {"critique": critique.model_dump(), "iteration": 2}


def test_finalizer_node_returns_trimmed_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    use_fake_llm(monkeypatch, FakeLLM(text=("  Final answer  ",)))

    assert nodes.finalizer_node(make_state()) == {
        "final_answer": "Final answer",
        "status": "awaiting_human_review",
    }


def test_graph_revises_low_scoring_draft_without_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = Plan(
        steps=["Research"],
        key_risks=[],
        desired_output_structure=["Recommendation"],
    )
    low_score = Critique(
        issues=["Needs evidence"],
        missing_points=[],
        hallucination_risks=[],
        score=60,
        fix_instructions=["Use the research"],
    )
    high_score = low_score.model_copy(update={"issues": [], "score": 90})
    fake = FakeLLM(
        text=(
            "First draft",
            "Revised draft",
            "First final",
            "Human revision",
            "Approved exact",
        ),
        structured={
            Plan: (plan,),
            Critique: (low_score, high_score, high_score),
        },
    )
    research_response = AIMessage(
        content=[
            {
                "type": "text",
                "text": "Verified finding",
                "annotations": [
                    {
                        "type": "url_citation",
                        "title": "Evidence",
                        "url": "https://example.com/evidence",
                    }
                ],
            }
        ],
        response_metadata={"output_version": "v1"},
    )
    original_invoke = fake.invoke
    calls = 0

    def invoke(messages: Any) -> AIMessage:
        nonlocal calls
        calls += 1
        if calls == 1:
            return research_response
        return original_invoke(messages)

    monkeypatch.setattr(fake, "invoke", invoke)
    use_fake_llm(monkeypatch, fake)

    config: RunnableConfig = {"configurable": {"thread_id": "test-thread"}}
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        updates = list(
            graph.stream(
                make_state(
                    plan=None,
                    research_notes=[],
                    sources=[],
                    draft=None,
                    max_iterations=3,
                ),
                config=config,
                stream_mode="updates",
            )
        )
        assert [next(iter(update)) for update in updates] == [
            "planner",
            "researcher",
            "writer",
            "critic",
            "writer",
            "critic",
            "finalizer",
            "__interrupt__",
        ]
        first_review = updates[-1]["__interrupt__"][0].value
        assert first_review["type"] == "final_answer_review"
        assert first_review["final_answer"] == "First final"
        assert first_review["critic_score"] == 90
        assert first_review["human_revision_count"] == 0
        assert first_review["max_human_revisions"] == 2

        paused = graph.invoke(
            Command(resume={"action": "revise", "feedback": "Clarify recommendation"}),
            config=config,
        )
        assert paused["__interrupt__"]
        assert paused["human_feedback"] == "Clarify recommendation"
        assert paused["human_revision_count"] == 1
        assert paused["iteration"] == 1
        assert paused["final_answer"] == "Approved exact"
        calls_before_approval = len(fake.invocations)

        result = graph.invoke(
            Command(resume={"action": "approve", "feedback": ""}),
            config=config,
        )
        saved_state = graph.get_state(config)

    assert result["draft"] == "Human revision"
    assert result["final_answer"] == "Approved exact"
    assert result["iteration"] == 1
    assert result["critique"]["score"] == 90
    assert result["status"] == "approved"
    assert len(fake.invocations) == calls_before_approval
    assert saved_state.values["final_answer"] == "Approved exact"


def build_review_graph():
    workflow = StateGraph(GraphState)
    workflow.add_node("human_review", human_review_node)
    workflow.add_edge(START, "human_review")
    workflow.add_conditional_edges(
        "human_review",
        route_human_review,
        {"end": END, "revise": END, "review": "human_review"},
    )
    return workflow


def test_human_can_cancel_without_changing_reviewed_answer() -> None:
    config: RunnableConfig = {"configurable": {"thread_id": "cancel-thread"}}
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_review_graph().compile(checkpointer=checkpointer)
        paused = graph.invoke(
            make_state(
                final_answer="Reviewed answer",
                critique={"score": 88},
                status="awaiting_human_review",
            ),
            config=config,
        )
        assert paused["__interrupt__"]

        result = graph.invoke(
            Command(resume={"action": "cancel", "feedback": ""}),
            config=config,
        )

    assert result["status"] == "cancelled"
    assert result["final_answer"] == "Reviewed answer"


def test_human_revision_stores_feedback_increments_count_and_resets_iteration() -> None:
    config: RunnableConfig = {"configurable": {"thread_id": "revision-thread"}}
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_review_graph().compile(checkpointer=checkpointer)
        graph.invoke(
            make_state(
                final_answer="Reviewed answer",
                critique={"score": 88},
                status="awaiting_human_review",
                iteration=2,
            ),
            config=config,
        )
        result = graph.invoke(
            Command(resume={"action": "revise", "feedback": "Add cost details"}),
            config=config,
        )

    assert result["status"] == "running"
    assert result["human_feedback"] == "Add cost details"
    assert result["human_revision_count"] == 1
    assert result["iteration"] == 0
    assert result["final_answer"] is None


def test_human_revision_limit_returns_to_review_without_writer() -> None:
    config: RunnableConfig = {"configurable": {"thread_id": "limit-thread"}}
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        graph = build_review_graph().compile(checkpointer=checkpointer)
        graph.invoke(
            make_state(
                final_answer="Limit answer",
                critique={"score": 88},
                status="awaiting_human_review",
                max_human_revisions=0,
            ),
            config=config,
        )
        paused = graph.invoke(
            Command(resume={"action": "revise", "feedback": "Change it"}),
            config=config,
        )

    assert paused["__interrupt__"]
    assert paused["status"] == "revision_limit_reached"
    assert paused["human_revision_count"] == 0
    assert paused["final_answer"] == "Limit answer"
