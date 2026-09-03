import hmac
import json
import logging
from collections.abc import Iterator
from hashlib import sha256
from typing import Annotated, Any, Literal, Self
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, Field, model_validator

from langgraph_decision_team.config import get_settings
from langgraph_decision_team.graph import build_graph, create_initial_state
from langgraph_decision_team.state import GraphState

logger = logging.getLogger(__name__)


class StartRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None

    @model_validator(mode="after")
    def require_question_text(self) -> Self:
        if not self.question.strip():
            raise ValueError("Question cannot be blank.")
        return self


class ApprovalRequest(BaseModel):
    action: Literal["approve", "revise", "cancel"]
    feedback: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def require_rejection_feedback(self) -> Self:
        if self.action == "revise" and not self.feedback.strip():
            raise ValueError("Human revisions require feedback.")
        return self


def sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def thread_access_token(thread_id: str) -> str:
    """Return stable server-signed capability token for one workflow thread."""

    return hmac.new(
        get_settings().thread_access_secret.encode(),
        thread_id.encode(),
        sha256,
    ).hexdigest()


def require_thread_access(thread_id: str, token: str | None) -> None:
    if token is None or not hmac.compare_digest(token, thread_access_token(thread_id)):
        raise HTTPException(status_code=403, detail="Invalid workflow access token.")


def started_events(events: Iterator[str], thread_id: str) -> Iterator[str]:
    yield sse(
        {
            "type": "started",
            "thread_id": thread_id,
            "thread_token": thread_access_token(thread_id),
        }
    )
    yield from events


def workflow_events(
    graph_input: GraphState | Command[Any] | None,
    thread_id: str,
) -> Iterator[str]:
    """Stream graph updates as server-sent events."""

    settings = get_settings()
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

    try:
        with SqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
            graph = build_graph(checkpointer=checkpointer)
            if graph_input is None:
                snapshot = graph.get_state(config)
                stored_interrupts = tuple(
                    item for task in snapshot.tasks for item in task.interrupts
                )
                if stored_interrupts:
                    yield sse(
                        {
                            "type": "approval_required",
                            "thread_id": thread_id,
                            "review": stored_interrupts[0].value,
                        }
                    )
                    return
                if snapshot.values.get("status") in {"approved", "cancelled"}:
                    yield sse(
                        {
                            "type": "complete",
                            "thread_id": thread_id,
                            "state": dict(snapshot.values),
                        }
                    )
                    return

            for update in graph.stream(
                graph_input,
                config=config,
                stream_mode="updates",
            ):
                for node, value in update.items():
                    if node == "__interrupt__":
                        yield sse(
                            {
                                "type": "approval_required",
                                "thread_id": thread_id,
                                "review": value[0].value,
                            }
                        )
                    else:
                        yield sse({"type": "node", "node": node, "data": value})

            state = dict(graph.get_state(config).values)
            if state.get("status") in {"approved", "cancelled"}:
                yield sse({"type": "complete", "thread_id": thread_id, "state": state})
    except Exception:
        logger.exception("Workflow event stream failed for thread %s", thread_id)
        yield sse({"type": "error", "message": "Workflow failed. Please retry."})


def thread_exists(thread_id: str) -> bool:
    settings = get_settings()
    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    with SqliteSaver.from_conn_string(settings.checkpoint_db) as checkpointer:
        return bool(build_graph(checkpointer=checkpointer).get_state(config).values)


app = FastAPI(title="Decision Team API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_settings().cors_origins),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Thread-Token"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/runs")
async def start_run(
    request: StartRequest,
    x_thread_token: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    thread_id = request.thread_id or str(uuid4())
    exists = request.thread_id is not None and thread_exists(thread_id)
    if exists:
        require_thread_access(thread_id, x_thread_token)
    graph_input = None if exists else create_initial_state(request.question.strip())
    return StreamingResponse(
        started_events(workflow_events(graph_input, thread_id), thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/runs/{thread_id}/approval")
async def approve_run(
    thread_id: str,
    request: ApprovalRequest,
    x_thread_token: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    if not thread_exists(thread_id):
        raise HTTPException(status_code=404, detail="Workflow thread not found.")
    require_thread_access(thread_id, x_thread_token)

    return StreamingResponse(
        workflow_events(
            Command(resume={"action": request.action, "feedback": request.feedback}),
            thread_id,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
