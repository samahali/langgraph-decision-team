import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    openai_model: str
    temperature: float
    max_iterations: int
    max_human_revisions: int
    quality_threshold: int
    checkpoint_db: str
    cors_origins: tuple[str, ...]
    max_research_sources: int
    thread_access_secret: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read workflow settings from environment variables."""

    load_dotenv()
    settings = Settings(
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        max_iterations=int(os.getenv("MAX_ITERATIONS", "2")),
        max_human_revisions=int(os.getenv("MAX_HUMAN_REVISIONS", "2")),
        quality_threshold=int(os.getenv("QUALITY_THRESHOLD", "80")),
        checkpoint_db=os.getenv("CHECKPOINT_DB", "checkpoints.sqlite"),
        cors_origins=tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        ),
        max_research_sources=int(os.getenv("MAX_RESEARCH_SOURCES", "10")),
        thread_access_secret=os.getenv(
            "THREAD_ACCESS_SECRET",
            "development-only-thread-access-secret-change-me",
        ),
    )

    if settings.max_iterations < 1:
        raise ValueError("MAX_ITERATIONS must be at least 1.")
    if settings.max_human_revisions < 0:
        raise ValueError("MAX_HUMAN_REVISIONS cannot be negative.")
    if not 0 <= settings.quality_threshold <= 100:
        raise ValueError("QUALITY_THRESHOLD must be between 0 and 100.")
    if settings.max_research_sources < 1:
        raise ValueError("MAX_RESEARCH_SOURCES must be at least 1.")
    if len(settings.thread_access_secret) < 32:
        raise ValueError("THREAD_ACCESS_SECRET must be at least 32 characters.")

    return settings
