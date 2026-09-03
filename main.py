import os
from pathlib import Path

from dotenv import load_dotenv

from langgraph_decision_team.graph import build_graph
from langgraph_decision_team.state import GraphState


def load_environment() -> None:
    """Load environment variables from the project's .env file."""

    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"

    load_dotenv(dotenv_path=env_file)


def create_initial_state(question: str) -> GraphState:
    """Create the initial state for the decision workflow."""

    return {
        "question": question,
        "plan": None,
        "research_notes": [],
        "draft": None,
        "critique": None,
        "iteration": 0,
        "max_iterations": 2,
    }


def main() -> None:
    """Run the multi-agent decision workflow."""

    load_environment()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from the .env file.")

    question = input("Enter your question: ").strip()

    if not question:
        print("A question is required.")
        return

    graph = build_graph()
    initial_state = create_initial_state(question)
    result = graph.invoke(initial_state)

    print("\nFINAL ANSWER\n")
    print(result["draft"])

    print("\nWORKFLOW INFORMATION")
    print("Critic iterations:", result["iteration"])
    print("Last draft critic score:", result["critique"]["score"])


if __name__ == "__main__":
    main()