from collections.abc import Iterator

import pytest

from langgraph_decision_team.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.5")
    monkeypatch.setenv("MAX_ITERATIONS", "4")
    monkeypatch.setenv("MAX_HUMAN_REVISIONS", "3")
    monkeypatch.setenv("QUALITY_THRESHOLD", "90")
    monkeypatch.setenv("CHECKPOINT_DB", "test.sqlite")
    monkeypatch.setenv("THREAD_ACCESS_SECRET", "x" * 32)

    settings = get_settings()

    assert settings.openai_model == "test-model"
    assert settings.temperature == 0.5
    assert settings.max_iterations == 4
    assert settings.max_human_revisions == 3
    assert settings.quality_threshold == 90
    assert settings.checkpoint_db == "test.sqlite"
    assert settings.thread_access_secret == "x" * 32


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("MAX_ITERATIONS", "0", "MAX_ITERATIONS must be at least 1."),
        (
            "MAX_HUMAN_REVISIONS",
            "-1",
            "MAX_HUMAN_REVISIONS cannot be negative.",
        ),
        (
            "QUALITY_THRESHOLD",
            "101",
            "QUALITY_THRESHOLD must be between 0 and 100.",
        ),
        (
            "MAX_RESEARCH_SOURCES",
            "0",
            "MAX_RESEARCH_SOURCES must be at least 1.",
        ),
        (
            "THREAD_ACCESS_SECRET",
            "too-short",
            "THREAD_ACCESS_SECRET must be at least 32 characters.",
        ),
    ],
)
def test_settings_reject_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
    message: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=message):
        get_settings()
