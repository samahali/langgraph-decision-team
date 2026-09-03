import os
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from langgraph_decision_team.config import get_settings
from langgraph_decision_team.graph import build_graph, create_initial_state
from langgraph_decision_team.state import GraphState


def stream_workflow(
    graph: Any,
    graph_input: GraphState | Command | None,
    config: RunnableConfig,
) -> tuple[dict[str, Any], tuple[Any, ...]]:
    """Run workflow while printing node completion events."""

    interrupts: tuple[Any, ...] = ()
    for update in graph.stream(graph_input, config=config, stream_mode="updates"):
        for node, value in update.items():
            if node == "__interrupt__":
                interrupts = value
            else:
                print(f"[{node}] complete", flush=True)

    return dict(graph.get_state(config).values), interrupts


def prompt_human_decision(
    read: Callable[[str], str] = input,
) -> dict[str, str]:
    """Read and validate a CLI human-review decision."""

    actions = {
        "a": "approve",
        "approve": "approve",
        "r": "revise",
        "revise": "revise",
        "c": "cancel",
        "cancel": "cancel",
    }
    action = ""
    while action not in actions:
        action = read("Action: ").strip().lower()

    decision = {"action": actions[action], "feedback": ""}
    if decision["action"] == "revise":
        while not decision["feedback"]:
            decision["feedback"] = read("What should be changed? ").strip()

    return decision


def main() -> None:
    """Run the multi-agent decision workflow."""

    get_settings()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from the .env file.")

    entered_thread_id = input("Thread ID (blank for new): ").strip()
    thread_id = entered_thread_id or str(uuid4())
    settings = get_settings()

    with SqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
        graph = build_graph(checkpointer=checkpointer)
        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(config)

        if snapshot.values:
            result = dict(snapshot.values)
            interrupts = tuple(
                item for task in snapshot.tasks for item in task.interrupts
            )
            if not interrupts and result["status"] == "running":
                result, interrupts = stream_workflow(graph, None, config)
        else:
            question = input("Enter your question: ").strip()
            if not question:
                print("A question is required.")
                return
            result, interrupts = stream_workflow(
                graph,
                create_initial_state(question),
                config,
            )

        while interrupts:
            review = interrupts[0].value
            print("\nFINAL ANSWER FOR REVIEW\n")
            print(review["final_answer"])
            print("\nChoose an action:")
            print("[a] Approve")
            print("[r] Request revision")
            print("[c] Cancel")
            decision = prompt_human_decision()

            result, interrupts = stream_workflow(
                graph,
                Command(resume=decision),
                config,
            )

    print("\nFINAL ANSWER\n")
    print(result["final_answer"])

    print("\nWORKFLOW INFORMATION")
    print("Status:", result["status"])
    print("Thread ID:", thread_id)
    print("Critic iterations:", result["iteration"])
    print("Human revisions:", result["human_revision_count"])
    print("Last draft critic score:", result["critique"]["score"])


if __name__ == "__main__":
    main()
