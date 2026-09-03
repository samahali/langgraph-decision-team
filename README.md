# Decision Team

> Evidence-backed decisions with human approval — powered by a multi-agent LangGraph workflow and a live React interface.

A six-stage decision-support system that plans your question, researches live web sources, writes a draft, critiques its own work, and stops at your desk for approval. It is designed to reduce unsupported claims and excessive agency; it does not claim that hallucinations are impossible.

## What it does

1. **Planner** breaks your question into ordered research steps and identifies risks.
2. **Researcher** uses only read-only web search for authoritative, cited evidence.
3. **Writer** drafts a structured answer using the research and plan.
4. **Critic** evaluates the draft against the plan, assigns a 0–100 quality score, and prescribes fixes.
5. **Finalizer** produces the polished final answer with sources.
6. **Human Review** — the workflow pauses and waits for you to approve, request revision, or cancel.

Low scores trigger automatic revision cycles. Human feedback resets the critic budget. No model runs after you approve.

## Quick start

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 22+ with npm
- An OpenAI API key and a model that supports the Responses API `web_search` tool

### 1. Configure the backend

```bash
cp .env.example .env
```

Edit `.env` and set your `OPENAI_API_KEY`. Generate a secure `THREAD_ACCESS_SECRET` (at least 32 characters):

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Run the API

```bash
uv run uvicorn langgraph_decision_team.api:app --reload
```

The API starts on `http://localhost:8000`.

### 3. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### 4. Try the CLI

```bash
uv run python main.py
```

Enter a question, and after the workflow finalizes, choose an action:

```text
[a] Approve   [r] Request revision   [c] Cancel
```

To resume a previous run, enter the saved thread ID when prompted. Checkpoints persist in `checkpoints.sqlite` (or your `CHECKPOINT_DB`).

## How the workflow loops

```text
Planner → Researcher → Writer → Critic
                           ↑      │
                           └──────┘  score < threshold and revisions remain
                                     │
                                     ↓
                              Finalizer → Human Review
                                            ├─ approve → END (no more model calls)
                                            ├─ cancel  → END (final answer unchanged)
                                            └─ revise  → Writer (critique budget resets)
```

Two independent counters enforce separate limits:

| Counter | Controls | Reset by | Configured via |
|---|---|---|---|
| `iteration` | Automatic Critic revision cycles | Human revision | `MAX_ITERATIONS` |
| `human_revision_count` | Human-requested revisions | Never (cumulative) | `MAX_HUMAN_REVISIONS` |

## Configuration

All configuration is environment-based. See `.env.example` for the full list:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o-mini` | Model used for planning, writing, criticism, and finalization |
| `LLM_TEMPERATURE` | `0.2` | Sampling temperature (higher = more creative) |
| `MAX_ITERATIONS` | `2` | Max automatic Critic revision cycles before finalization |
| `MAX_HUMAN_REVISIONS` | `2` | Max human-requested revisions before the answer is locked |
| `QUALITY_THRESHOLD` | `80` | Minimum Critic score (0–100) to skip revision |
| `MAX_RESEARCH_SOURCES` | `10` | Cap on web-search result URLs collected per query |
| `THREAD_ACCESS_SECRET` | *(required)* | HMAC signing key for thread access tokens; minimum 32 characters |
| `CHECKPOINT_DB` | `checkpoints.sqlite` | SQLite checkpoint file path |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed CORS origins |
| `LANGSMITH_API_KEY` | — | LangSmith tracing (optional but recommended) |

## API reference

All endpoints stream Server-Sent Events (`text/event-stream`).

### `GET /health`

Returns service health.

**Response** `200`

```json
{"status": "ok"}
```

### `POST /runs`

Start a new workflow or resume an existing one.

**Headers**

| Header | Required | Description |
|---|---|---|
| `X-Thread-Token` | When resuming | HMAC capability token received from the `started` event of the original run |

**Body**

```json
{
  "question": "Should we build, buy, or partner for our analytics platform?",
  "thread_id": "optional-uuid-to-resume"
}
```

**SSE events**

| Event `type` | Fields | Description |
|---|---|---|
| `started` | `thread_id`, `thread_token` | Emitted first; save the token to resume later |
| `node` | `node`, `data` | A workflow node completed |
| `approval_required` | `thread_id`, `review` | The finalizer paused for your decision |
| `complete` | `thread_id`, `state` | The workflow finished (status: approved or cancelled) |
| `error` | `message` | The workflow encountered an error |

### `POST /runs/{thread_id}/approval`

Submit a human review decision to a paused workflow.

**Headers**

| Header | Required | Description |
|---|---|---|
| `X-Thread-Token` | Yes | HMAC capability token from the original `started` event |

**Body**

```json
{
  "action": "approve",
  "feedback": ""
}
```

| `action` | Effect |
|---|---|
| `approve` | Finalizes immediately; no further model calls |
| `revise` | Returns to the Writer with your feedback (feedback required) |
| `cancel` | Stops the workflow; the reviewed answer is preserved unchanged |

## Security

### Threat model

- **Researcher is read-only:** The web-search tool is the only capability exposed. The researcher cannot execute arbitrary code, follow UI instructions in retrieved pages, or navigate to non-HTTP URLs.
- **URL validation:** Only `http`/`https` schemes with a network location are accepted. `javascript:` and other schemes are silently rejected.
- **Source capping:** At most `MAX_RESEARCH_SOURCES` URLs are retained per research step.
- **Thread authorization:** Resuming or approving a workflow requires an HMAC-SHA256-signed token derived from `THREAD_ACCESS_SECRET` + `thread_id`. Tokens are compared with `hmac.compare_digest` (constant-time).
- **Human-in-the-loop:** No answer is returned to the user without explicit human approval.

> **Note:** Thread tokens are capability tokens, not user authentication. For multi-user deployments, place an identity provider (OAuth2, SAML) in front of the API.

## Project structure

```
.
├── main.py                          # CLI entry point (interactive workflow runner)
├── pyproject.toml                   # uv build config + dependencies
├── uv.lock
├── src/langgraph_decision_team/
│   ├── __init__.py
│   ├── api.py                       # FastAPI app with SSE streaming
│   ├── config.py                    # Environment-based Settings (lru_cache)
│   ├── graph.py                     # LangGraph StateGraph definition + routing
│   ├── nodes.py                     # The six workflow node functions
│   ├── prompts.py                   # System prompts for each agent role
│   ├── schemas.py                   # Pydantic models (Plan, Critique)
│   └── state.py                     # GraphState TypedDict + WorkflowStatus
├── tests/
│   ├── conftest.py                  # Disables LangSmith tracing for tests
│   ├── test_config.py               # Settings parsing + validation
│   ├── test_routing.py              # should_revise + route_human_review
│   ├── test_nodes.py                # Node functions + full graph e2e
│   ├── test_api.py                  # API endpoints + token auth
│   └── test_cli.py                  # CLI input parsing
└── frontend/                        # React + Vite + TypeScript + Tailwind
    ├── src/
    │   ├── App.tsx                  # Main layout and routing
    │   ├── main.tsx                 # ReactDOM entry
    │   ├── styles.css               # Tailwind + custom oklch theme
    │   ├── lib/api.ts               # SSE stream consumer
    │   ├── hooks/
    │   │   └── use-decision-workflow.ts   # Workflow state machine
    │   ├── types/
    │   │   └── workflow.ts          # StreamEvent discriminated unions
    │   ├── components/
    │   │   ├── error-boundary.tsx
    │   │   ├── markdown-article.tsx
    │   │   ├── result-panel.tsx
    │   │   ├── review-panel.tsx
    │   │   ├── workflow-progress.tsx
    │   │   └── ui/                  # shadcn-style component primitives
    │   └── lib/utils.ts             # clsx + tailwind-merge helper
    ├── vitest.config.ts              # jsdom test + coverage configuration
    └── vite.config.ts
```

## Development

### Backend

```bash
uv sync --group dev              # install dev dependencies
uv run ruff check                # lint
uv run ruff format --check       # format check
uv run mypy src tests main.py    # type check
uv run pytest --cov=src          # test with coverage
```

### Frontend

```bash
cd frontend
npm install
npm run lint
npm test
npm run test:coverage
npm run build
```

### Running the full test suite

```bash
uv run pytest --cov=src --cov-report=term-missing
```

```
Backend: 35 tests, 83% statement coverage
Frontend: 4 tests, 83% statement coverage, 64.44% branch coverage
npm audit: 0 vulnerabilities
```

GitHub Actions runs linting, formatting, type checking, tests, dependency
audit, coverage enforcement, and production builds on every push and pull
request.

See [EVALUATION_REPORT.md](EVALUATION_REPORT.md) for a detailed assessment of
code quality, test coverage gaps, security findings, and a prioritized
roadmap.

## License

MIT
