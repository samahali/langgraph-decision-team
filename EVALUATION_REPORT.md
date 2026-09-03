# Evaluation Report — LangGraph Decision Team

**Evaluation date:** September 3, 2026  
**Scope:** backend, graph behavior, API contract, frontend, security controls,
tests, and CI  
**Method:** static review plus reproducible local quality gates

## Executive summary

Decision Team is a strong portfolio-grade MVP. It has a clear LangGraph state
machine, grounded web research, bounded automatic and human revision loops,
SQLite persistence, a streaming FastAPI boundary, and a typed React UI.

The evaluated workspace passes every configured quality gate:

- 35 backend tests pass with 83% statement coverage.
- 4 frontend tests pass with 83% statement coverage.
- Ruff lint and formatting pass.
- Mypy checks pass for all 16 Python source/test files.
- ESLint, TypeScript, and the Vite production build pass.
- `npm audit` reports zero known vulnerabilities.
- GitHub Actions enforces the same checks for pushes and pull requests.

**Assessment: 8.2/10 for MVP engineering quality.** Production deployment
still needs user authentication, rate limiting, observability, and real-model
answer-quality evaluation.

## System under evaluation

```text
Planner -> Researcher -> Writer -> Critic
                           ^          |
                           +----------+  low score, budget remains
                                      |
                                      v
                               Finalizer -> Human Review
                                             | approve -> END
                                             | cancel  -> END
                                             + revise  -> Writer
```

The design separates automatic critic iterations from human revisions. Human
feedback resets only the automatic iteration budget. Approval ends the graph
without another model call, so the user approves the exact answer returned.

## Reproducible results

### Backend

```bash
uv run ruff check src tests main.py
uv run ruff format --check src tests main.py
uv run mypy src tests main.py
uv run pytest --cov=src --cov-report=term-missing
```

| Gate | Result |
|---|---:|
| Tests | 35 passed |
| Statement coverage | 83% |
| Ruff lint | Pass |
| Ruff formatting | Pass |
| Mypy | Pass, 16 files |

| Module | Coverage |
|---|---:|
| `config.py` | 100% |
| `state.py` | 100% |
| `schemas.py` | 100% |
| `prompts.py` | 100% |
| `graph.py` | 93% |
| `nodes.py` | 85% |
| `api.py` | 65% |
| Total | 83% |

The main gap is generator-based SSE orchestration in `api.py`. Core graph
routing and full mock-LLM revision behavior are covered.

### Frontend

```bash
cd frontend
npm run lint
npm test
npm run test:coverage
npm run build
npm audit --audit-level=critical
```

| Gate | Result |
|---|---:|
| Test files | 3 passed |
| Tests | 4 passed |
| Statement coverage | 83.00% |
| Branch coverage | 64.44% |
| Function coverage | 82.35% |
| Line coverage | 88.63% |
| ESLint | Pass |
| TypeScript | Pass |
| Vite production build | Pass |
| npm audit | 0 vulnerabilities |

Tests cover chunked CRLF/multiline SSE parsing, malformed events, signed token
forwarding, approval error recovery, and the React render error boundary.

## Architecture assessment

### Strengths

- Modules have focused responsibilities: configuration, prompts, schemas,
  state, nodes, graph, API, and UI are separate without speculative layers.
- Routing decisions are deterministic pure functions and easy to test.
- Structured Pydantic outputs constrain planner and critic responses.
- SQLite checkpoints preserve interrupted graph state.
- SSE provides node-level progress without polling.
- The frontend uses a discriminated event union and one workflow hook as the
  client-side state boundary.
- Dependencies are justified; build-only packages live in `devDependencies`.
- Frontend toolchain versions are pinned instead of using `latest`.

### Trade-offs

- SQLite is appropriate for one process, but not horizontal multi-instance
  deployment.
- A synchronous graph generator occupies a worker while the workflow runs.
- The HMAC thread token authorizes possession of a thread; it does not identify
  a user.
- Model calls fail the run rather than retrying transient failures.

## Security assessment

Implemented controls:

- `THREAD_ACCESS_SECRET` is required and must contain at least 32 characters.
- Resume and approval require a per-thread HMAC-SHA256 capability token.
- Token comparison uses `hmac.compare_digest`.
- API input lengths are bounded and blank questions/revision feedback are
  rejected.
- CORS origins are explicit and configurable.
- Raw backend exception details are logged server-side and not exposed in SSE.
- Researcher receives only the read-only `web_search` tool.
- Retrieved instructions are treated as untrusted content.
- Citation URLs require HTTP(S) and a valid network location.
- Research sources and both revision loops are capped.
- Human approval is mandatory before completion.

These controls reduce OWASP LLM10 Excessive Agency risk: model access is
least-privileged, work is bounded, and consequential release remains under
human control.

Remaining production risks:

| Priority | Risk | Required control |
|---|---|---|
| High | Capability token is not user identity | OAuth2/OIDC plus thread ownership |
| High | Expensive endpoints have no rate limit | Per-user/IP limits backed by shared storage |
| Medium | Transient OpenAI failures end a run | Bounded exponential backoff |
| Medium | Limited operational visibility | Structured logs, request IDs, metrics, alerts |
| Medium | No browser end-to-end test | Playwright happy path against a mocked backend |

## LLM evaluation status

Software behavior is evaluated; answer quality from a real model is not yet
measured. Current tests intentionally use deterministic mock LLMs, so they
verify orchestration without cost or network variability. They do **not** prove
factual correctness, citation entailment, recommendation quality, or resistance
to novel prompt-injection content.

A production evaluation should use a versioned decision dataset and score:

| Dimension | Suggested measurement |
|---|---|
| Groundedness | Every material factual claim is supported by a cited source |
| Citation quality | Source is authoritative, reachable, and relevant |
| Completeness | Requested criteria and plan sections are addressed |
| Decision usefulness | Recommendation follows from evidence and trade-offs |
| Safety | Retrieved prompt injections cannot alter tool scope or instructions |
| Reliability | Run completes under transient failures within bounded retries |
| Cost/latency | Tokens, web calls, wall time, and revision count per case |

Use at least 20 representative questions across technology, procurement,
privacy, compliance, and ambiguous trade-offs. Store model name, prompt version,
date, scores, latency, and cost with each run. Keep this separate from unit tests
because model evaluations are slower, probabilistic, and billable.

## CI quality gate

`.github/workflows/ci.yml` runs two least-privilege jobs:

- Backend: locked dependency sync, lint, format, typing, tests, and minimum 80%
  coverage.
- Frontend: clean install, critical vulnerability audit, lint, tests, and
  production build.

No OpenAI key is required in CI because workflow tests use mock LLMs.

## Prioritized roadmap

### Before public deployment

1. Add OAuth2/OIDC and bind checkpoint access to authenticated users.
2. Add rate limiting and request-size limits at the reverse proxy.
3. Add bounded retry/backoff for retryable OpenAI failures.
4. Add structured logs, correlation IDs, metrics, and alerting.
5. Add Playwright coverage for start, review, revise, approve, and recovery.

### When scale requires it

1. Replace SQLite checkpoints with a shared production database.
2. Move long workflows to background workers if request concurrency becomes a
   bottleneck.
3. Add a Redis-backed limiter only when multiple API instances exist.

### Intentionally deferred

- `Makefile`: documented commands and CI already provide one source of truth.
- `pytest-mock`: built-in `monkeypatch` covers current needs.
- Real-API tests on every commit: costly and non-deterministic; run them in a
  scheduled evaluation job instead.

## Conclusion

Step 11 is complete for engineering evaluation: documentation is reproducible,
quality gates are automated, both application layers have tests, and known
limits are explicit. The project is ready for portfolio demonstration and
controlled MVP use. It should not be described as production-ready until the
high-priority identity and abuse controls are implemented and real-model output
quality has a measured baseline.
