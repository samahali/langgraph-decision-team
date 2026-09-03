from collections.abc import Callable, Iterator

from main import prompt_human_decision


def reader(answers: Iterator[str], prompts: list[str]) -> Callable[[str], str]:
    def read(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    return read


def test_invalid_cli_action_prompts_again() -> None:
    prompts: list[str] = []

    decision = prompt_human_decision(reader(iter(["invalid", "approve"]), prompts))

    assert decision == {"action": "approve", "feedback": ""}
    assert prompts == ["Action: ", "Action: "]


def test_blank_revision_feedback_prompts_again() -> None:
    prompts: list[str] = []

    decision = prompt_human_decision(
        reader(iter(["r", "", "  Make it shorter  "]), prompts)
    )

    assert decision == {"action": "revise", "feedback": "Make it shorter"}
    assert prompts == [
        "Action: ",
        "What should be changed? ",
        "What should be changed? ",
    ]
