from collections.abc import AsyncIterator

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from langgraph_decision_team import api


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=api.app),
        base_url="http://test",
    ) as test_client:
        yield test_client


@pytest.mark.anyio
async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}


@pytest.mark.anyio
async def test_local_ui_origin_is_allowed(client: AsyncClient) -> None:
    response = await client.options(
        "/runs",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_started_events_include_thread_access_token() -> None:
    events = list(
        api.started_events(
            iter([api.sse({"type": "complete", "thread_id": "thread-1"})]),
            "thread-1",
        )
    )

    assert '"type": "started"' in events[0]
    assert '"thread_token"' in events[0]
    assert '"thread_id": "thread-1"' in events[1]


def test_thread_access_token_is_required() -> None:
    token = api.thread_access_token("thread-1")

    api.require_thread_access("thread-1", token)

    with pytest.raises(HTTPException, match="Invalid workflow access token"):
        api.require_thread_access("thread-1", "wrong-token")


@pytest.mark.anyio
async def test_existing_thread_requires_access_token(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(api, "thread_exists", lambda _thread_id: True)

    response = await client.post(
        "/runs",
        json={"question": "Choose a database", "thread_id": "thread-1"},
    )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_approval_requires_access_token(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(api, "thread_exists", lambda _thread_id: True)

    response = await client.post(
        "/runs/thread-1/approval",
        json={"action": "approve"},
    )

    assert response.status_code == 403


@pytest.mark.anyio
async def test_rejection_requires_feedback(client: AsyncClient) -> None:
    response = await client.post(
        "/runs/thread-1/approval",
        json={"action": "revise", "feedback": ""},
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_blank_question_is_rejected(client: AsyncClient) -> None:
    response = await client.post("/runs", json={"question": "   "})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_approval_returns_404_for_unknown_thread(
    monkeypatch: pytest.MonkeyPatch,
    client: AsyncClient,
) -> None:
    monkeypatch.setattr(api, "thread_exists", lambda _thread_id: False)

    response = await client.post(
        "/runs/missing-thread/approval",
        json={"action": "approve"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Workflow thread not found.",
    }


def test_workflow_events_returns_safe_error_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_database_error(_connection_string: str):
        raise RuntimeError("Database unavailable")

    monkeypatch.setattr(
        api.SqliteSaver,
        "from_conn_string",
        raise_database_error,
    )

    events = list(
        api.workflow_events(
            graph_input=None,
            thread_id="thread-1",
        )
    )

    assert len(events) == 1
    assert '"type": "error"' in events[0]
    assert '"message": "Workflow failed. Please retry."' in events[0]
    assert "Database unavailable" not in events[0]
