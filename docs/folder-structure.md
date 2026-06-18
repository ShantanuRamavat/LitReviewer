# Production Folder Structure
## Multi-Agent Research Platform

| Field | Value |
|---|---|
| Version | 1.0 |
| Architecture Style | Feature-based, vertical slice |
| Date | 2026-06-08 |

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Top-Level Monorepo](#2-top-level-monorepo)
3. [Backend — Detailed Breakdown](#3-backend--detailed-breakdown)
4. [Frontend — Detailed Breakdown](#4-frontend--detailed-breakdown)
5. [Infrastructure](#5-infrastructure)
6. [Docs](#6-docs)
7. [File Naming Conventions](#7-file-naming-conventions)
8. [Dependency Rules](#8-dependency-rules)

---

## 1. Design Philosophy

### Feature-Based, Not Layer-Based

This project uses **feature-based (vertical slice) architecture**, not the traditional layer-based approach.

**Layer-based (avoid):**
```
models/
    session.py
    report.py
    finding.py
services/
    session.py
    report.py
    finding.py
routes/
    session.py
    report.py
```
Every feature is split across 3+ directories. Adding a feature or changing a concept requires touching multiple folders. Files grow large because they aggregate all concerns of a layer.

**Feature-based (use):**
```
features/
    research/
        router.py
        service.py
        schemas.py
        models.py
    reports/
        router.py
        service.py
        schemas.py
        models.py
```
Every feature owns its full vertical slice. Adding a feature means adding one folder. Files stay small because they only contain one feature's concerns.

### Small File Rule

No single file should exceed ~200 lines. If it grows beyond that, it is doing too much and should be split. Specific hard limits:

| File Type | Max Lines |
|---|---|
| Route handler | 80 lines |
| Service class | 150 lines |
| Agent class | 120 lines |
| Schema file | 100 lines |
| Utility module | 80 lines |

### One Responsibility Per Module

Every Python module (`.py` file) has exactly one job, clearly described by its name. If you cannot describe what a file does in one sentence, it should be split.

---

## 2. Top-Level Monorepo

```
nexus-research/
│
├── backend/                    # Python FastAPI application
├── frontend/                   # Next.js 15 application
├── infrastructure/             # Docker, compose, config files
├── docs/                       # All architecture and planning docs
├── .env.example                # Template for all required env vars
├── .gitignore
├── README.md
└── Makefile                    # Developer convenience commands
```

### Why a Monorepo?

- Backend and frontend are tightly coupled (shared type contracts, coordinated deploys)
- Single `docker compose up` brings everything up
- Simpler CI/CD pipeline for a single-team project
- Easy to enforce consistent tooling (linting, formatting) across both

---

## 3. Backend — Detailed Breakdown

```
backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   │
│   ├── features/
│   │   ├── research/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   └── dependencies.py
│   │   │
│   │   ├── reports/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   ├── schemas.py
│   │   │   └── pdf_renderer.py
│   │   │
│   │   ├── history/
│   │   │   ├── __init__.py
│   │   │   ├── router.py
│   │   │   ├── service.py
│   │   │   └── schemas.py
│   │   │
│   │   └── health/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       └── checks.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── research/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── output_parser.py
│   │   ├── factchecker/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── output_parser.py
│   │   ├── critic/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── output_parser.py
│   │   ├── writer/
│   │   │   ├── __init__.py
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── output_parser.py
│   │   └── citation/
│   │       ├── __init__.py
│   │       ├── agent.py
│   │       ├── prompt.py
│   │       └── output_parser.py
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── builder.py
│   │   ├── nodes.py
│   │   └── edges.py
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embedder.py
│   │   ├── ingestion.py
│   │   ├── retriever.py
│   │   └── chunker.py
│   │
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── web_search.py
│   │   └── vector_search.py
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── postgres/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── session.py
│   │   │   └── models/
│   │   │       ├── __init__.py
│   │   │       ├── session.py
│   │   │       ├── report.py
│   │   │       ├── finding.py
│   │   │       ├── citation.py
│   │   │       └── agent_log.py
│   │   ├── qdrant/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   └── collections.py
│   │   └── redis/
│   │       ├── __init__.py
│   │       └── client.py
│   │
│   ├── streaming/
│   │   ├── __init__.py
│   │   ├── emitter.py
│   │   └── events.py
│   │
│   └── core/
│       ├── __init__.py
│       ├── exceptions.py
│       ├── middleware.py
│       ├── logging.py
│       └── rate_limiter.py
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   └── agents.py
│   ├── unit/
│   │   ├── agents/
│   │   │   ├── test_research_agent.py
│   │   │   ├── test_factchecker_agent.py
│   │   │   ├── test_critic_agent.py
│   │   │   ├── test_writer_agent.py
│   │   │   └── test_citation_agent.py
│   │   ├── rag/
│   │   │   ├── test_embedder.py
│   │   │   ├── test_chunker.py
│   │   │   └── test_retriever.py
│   │   ├── graph/
│   │   │   ├── test_state.py
│   │   │   └── test_edges.py
│   │   └── features/
│   │       ├── test_research_service.py
│   │       └── test_report_service.py
│   └── integration/
│       ├── test_research_flow.py
│       ├── test_api_research.py
│       ├── test_api_reports.py
│       └── test_api_history.py
│
├── Dockerfile
├── pyproject.toml
├── .env.example
└── alembic.ini
```

---

### 3.1 `app/main.py`

**Purpose:** FastAPI application factory. Creates the app instance, registers all feature routers, attaches middleware, and sets up lifespan handlers (startup/shutdown).

Startup hooks: initialize DB connection pool, warm up the embedding model, verify Qdrant collection exists.
Shutdown hooks: flush pending logs, close DB connections.

This file never contains business logic — it only wires things together.

---

### 3.2 `app/config.py`

**Purpose:** Single source of truth for all configuration. Uses `pydantic-settings` to read from environment variables with type validation and default values.

Every other module imports from `config.py` — never reads `os.environ` directly. This enforces a single validation point and makes test overrides trivial (`Settings(gemini_api_key="test-key")`).

Groups of settings defined here:
- LLM settings (model name, temperature, max tokens)
- Search settings (API key, max results per query)
- Database URLs (Postgres, Qdrant, Redis)
- Research tuning (max iterations, quality threshold, RAG top-k)
- App settings (environment name, log level, CORS origins)

---

### 3.3 `app/features/`

**Purpose:** The vertical slice layer. Each subdirectory is a self-contained feature with its own router, service, and schemas. Features never import from each other directly — shared concerns live in `core/`, `db/`, or `agents/`.

---

#### `app/features/research/`

| File | Purpose |
|---|---|
| `router.py` | FastAPI router. Defines `POST /research/start` and `GET /research/stream/{session_id}` and `GET /research/{session_id}`. Thin — delegates immediately to service. |
| `service.py` | `ResearchService` class. Creates the session record, dispatches the LangGraph graph as a background task, and writes results to the database when complete. Contains all orchestration logic for the research lifecycle. |
| `schemas.py` | Pydantic request/response models for this feature: `ResearchStartRequest`, `ResearchStartResponse`, `SessionStatusResponse`. No SQLAlchemy models here — only API-layer contracts. |
| `dependencies.py` | FastAPI dependency functions specific to this feature, e.g., `get_session_or_404` — fetches a session by ID and raises `404` if missing. |

---

#### `app/features/reports/`

| File | Purpose |
|---|---|
| `router.py` | Defines `GET /reports/{report_id}` and `GET /reports/{report_id}/export/pdf`. |
| `service.py` | `ReportService` class. Fetches report data from the database with its citations. |
| `schemas.py` | `ReportResponse`, `SectionResponse`, `CitationResponse` — the full nested report response shape. |
| `pdf_renderer.py` | Isolated PDF generation logic. Accepts a `ReportResponse` object, renders a Jinja2 HTML template, calls WeasyPrint, and returns `bytes`. Isolated here so it can be tested and swapped independently. |

---

#### `app/features/history/`

| File | Purpose |
|---|---|
| `router.py` | Defines `GET /history` (paginated list) and `DELETE /history/{session_id}`. |
| `service.py` | `HistoryService` class. Paginated session query, cascade delete logic. |
| `schemas.py` | `HistoryListResponse`, `HistoryItemResponse`, `PaginationMeta`. |

---

#### `app/features/health/`

| File | Purpose |
|---|---|
| `router.py` | Defines `GET /health`. |
| `checks.py` | Individual async check functions: `check_postgres()`, `check_qdrant()`, `check_redis()`, `check_gemini()`. Each returns `{"status": "up"/"down", "latency_ms": N}`. Isolated so new checks can be added without touching the router. |

---

### 3.4 `app/agents/`

**Purpose:** All agent logic lives here, completely isolated from the API layer. Each agent is a subdirectory with three focused files. This structure makes it trivial to add a new agent without touching any existing code.

---

#### `app/agents/base.py`

**Purpose:** `BaseAgent` abstract class. Defines the interface every agent must implement:
- `name: str` — used in logging and SSE events
- `run(state: GraphState) -> GraphState` — the single entry point
- `_build_messages(state)` — assembles the prompt from state
- `_log(session_id, input, output, duration)` — persists to `agent_logs`
- `_emit(event)` — pushes SSE event to the streaming service

No agent contains logging, retry logic, or SSE emission code — those live here once.

---

#### `app/agents/{name}/agent.py`

**Purpose:** The agent class itself. Inherits `BaseAgent`. Implements `run(state)` and any agent-specific private methods. Holds references to its tools and the LLM client. Contains no prompt strings — those live in `prompt.py`.

Keeping the agent logic separate from prompts means prompt iteration (a frequent activity) does not require touching the agent logic, and vice versa.

---

#### `app/agents/{name}/prompt.py`

**Purpose:** All prompt strings for this agent. Contains the system prompt as a module-level constant and a `build_human_prompt(state: GraphState) -> str` function that assembles the dynamic portion from state.

Isolation rationale: prompt engineering is a separate discipline from software engineering. Product/ML teams frequently iterate on prompts. Putting prompts in their own files makes diffs readable and review focused.

---

#### `app/agents/{name}/output_parser.py`

**Purpose:** Parses and validates the raw LLM response string into the agent's Pydantic output model. Contains the retry logic for malformed JSON (re-prompt with stricter instruction up to 2 times). Returns a typed object, never a raw string.

Isolation rationale: LLM output parsing is fragile and changes frequently as models evolve. Isolating it means parsing logic can be updated or tested without touching the agent or prompt.

---

### 3.5 `app/graph/`

**Purpose:** The LangGraph state machine. Completely independent of the API layer — could be run as a standalone script, in tests, or in a worker process without any FastAPI context.

| File | Purpose |
|---|---|
| `state.py` | The `GraphState` TypedDict. The single shared data structure passed between all nodes. Every field is explicitly typed. This is the contract between agents — changes here affect everyone. |
| `builder.py` | `build_graph()` function. Constructs and compiles the `StateGraph` by adding nodes, edges, and conditional edges. Returns a compiled `CompiledGraph`. Called once at startup and reused across sessions. |
| `nodes.py` | Thin wrapper functions that adapt each `Agent.run()` call to the LangGraph node interface. A node function receives `GraphState`, calls the agent, and returns the state delta. No business logic here. |
| `edges.py` | Conditional edge functions. `quality_gate(state) -> str` is the primary example — reads `state.critique.quality_score` and `state.iteration` and returns the next node name string. |

---

### 3.6 `app/rag/`

**Purpose:** The full Retrieval-Augmented Generation pipeline. Completely stateless and independently testable — each module accepts inputs and returns outputs with no side effects beyond Qdrant writes.

| File | Purpose |
|---|---|
| `chunker.py` | `chunk_text(text, chunk_size, overlap) -> list[str]`. Wraps `RecursiveCharacterTextSplitter`. Pure function — no I/O. Fully unit testable. |
| `embedder.py` | `Embedder` class. Loads the BAAI/bge-large-en-v1.5 model once at initialization. Exposes `embed_texts(texts) -> list[list[float]]` and `embed_query(query) -> list[float]` (query uses the instruction prefix). |
| `ingestion.py` | `RAGIngestionService`. Accepts `(text, source_url, session_id)` tuples, calls `chunker`, then `embedder`, then upserts to Qdrant. Handles deduplication by checking if the source URL already exists for this session. |
| `retriever.py` | `RAGRetriever`. Accepts a `(query, session_id, k)` and returns top-k matching chunks with their source URLs and scores. Used by `vector_search.py` tool. |

---

### 3.7 `app/tools/`

**Purpose:** LangChain-compatible tool wrappers. Each tool exposes a clean interface that agents can call. Tools are the only modules in `agents/` that are allowed to perform I/O (API calls, DB queries).

| File | Purpose |
|---|---|
| `web_search.py` | `TavilySearchTool`. Wraps the Tavily Python client. Exposes `search(query, max_results) -> list[SearchResult]`. Handles API errors and returns an empty list with a warning on failure. |
| `vector_search.py` | `QdrantSearchTool`. Wraps `RAGRetriever`. Exposes `search(query, session_id, k) -> list[RetrievalResult]`. Formats results as context strings ready for injection into prompts. |

New tools (e.g., a calculator, a code executor, a knowledge graph lookup) are added here without touching agent code — agents reference tools by name.

---

### 3.8 `app/db/`

**Purpose:** All database client initialization and SQLAlchemy models. The `db/` layer is the only layer permitted to know the database schema. Features and agents access data only through service classes — never by importing models directly.

---

#### `app/db/postgres/`

| File | Purpose |
|---|---|
| `engine.py` | Creates the async SQLAlchemy engine using the `POSTGRES_URL` from config. Configures connection pool settings (pool size, max overflow, timeout). |
| `session.py` | `AsyncSession` factory. Exposes `get_db()` as a FastAPI dependency that yields a session and handles commit/rollback/close automatically. |
| `models/__init__.py` | Imports all models in one place so Alembic's `env.py` can discover them via `Base.metadata`. |
| `models/session.py` | `ResearchSession` ORM model. Maps to the `research_sessions` table. |
| `models/report.py` | `Report` ORM model. Includes the `content` JSONB column. |
| `models/finding.py` | `Finding` ORM model. |
| `models/citation.py` | `Citation` ORM model. |
| `models/agent_log.py` | `AgentLog` ORM model. |

Each model is in its own file. Why: SQLAlchemy model files grow with relationships, validators, and hybrid properties. One model per file prevents any single file from becoming unwieldy.

---

#### `app/db/qdrant/`

| File | Purpose |
|---|---|
| `client.py` | `QdrantClientSingleton`. Creates and caches the `QdrantClient` instance. Exposes `get_client()` used by `ingestion.py` and `retriever.py`. |
| `collections.py` | `ensure_collection_exists()` startup function. Checks if the `research_docs` collection exists; creates it with the correct vector config if not. Called in `main.py` lifespan. |

---

#### `app/db/redis/`

| File | Purpose |
|---|---|
| `client.py` | `RedisClientSingleton`. Creates and caches the `aioredis` connection pool. Exposes `get_client()`. Used by `StreamingService` and `ResearchService` for the SSE event queue. |

---

### 3.9 `app/streaming/`

**Purpose:** All Server-Sent Events logic. Completely decoupled from the agent and graph layers — agents push events to Redis; the streaming layer reads from Redis and formats SSE responses.

| File | Purpose |
|---|---|
| `events.py` | `AgentEvent` Pydantic model and `EventType` enum. Defines the exact shape of every SSE event: `event_type`, `agent_name`, `data`, `timestamp`. Shared by the emitter and the API router. |
| `emitter.py` | `StreamEmitter`. `push(session_id, event)` serializes the event and `RPUSH`es it to Redis list `stream:{session_id}`. `consume(session_id)` is an `async generator` that `BLPOP`s from Redis and yields formatted SSE strings until a terminal event is seen. |

Decoupling rationale: the graph runs in a background task; the SSE endpoint runs in a separate async context. Redis is the message bus between them. This design survives horizontal scaling (multiple backend replicas) because Redis is shared.

---

### 3.10 `app/core/`

**Purpose:** Cross-cutting infrastructure concerns shared across all features. Nothing in `core/` is specific to any feature or agent.

| File | Purpose |
|---|---|
| `exceptions.py` | Custom exception classes: `SessionNotFoundError`, `ReportNotFoundError`, `AgentExecutionError`, `RateLimitExceededError`. Each maps to a specific HTTP status code via the exception handler in `middleware.py`. |
| `middleware.py` | FastAPI middleware: exception handler (formats all unhandled errors as JSON), request ID injection (adds `X-Request-ID` to every response for tracing). |
| `logging.py` | Configures `structlog` for JSON structured logging. Exposes a `get_logger(name)` function used everywhere. Log fields: `timestamp`, `level`, `logger`, `request_id`, `session_id`, `agent_name`, `duration_ms`. |
| `rate_limiter.py` | Sliding window rate limiter using Redis. Middleware-level, keyed by IP. Applied to `POST /research/start` only. Configurable via `API_RATE_LIMIT` env var. |

---

### 3.11 `migrations/`

**Purpose:** Alembic database migrations. Every schema change is a versioned, reversible migration file — no manual `ALTER TABLE` commands.

| Path | Purpose |
|---|---|
| `env.py` | Alembic environment config. Imports `Base.metadata` from `app/db/postgres/models/__init__.py` so autogenerate can detect schema changes. |
| `script.py.mako` | Template for new migration files. |
| `versions/` | Numbered migration files in chronological order. Each file has an `upgrade()` and `downgrade()` function. |

Convention: migration file names follow `{NNN}_{description}.py` (e.g., `001_initial_schema.py`, `002_add_confidence_to_findings.py`).

---

### 3.12 `tests/`

**Purpose:** All test code. Mirrors the `app/` structure so any test is easy to locate by its subject.

| Path | Purpose |
|---|---|
| `conftest.py` | Top-level pytest fixtures: test database session, mock LLM client, mock Tavily responses, mock Qdrant client. All external I/O is mocked at this level. |
| `fixtures/db.py` | Database test fixtures: creates a fresh test database, runs migrations, and tears down after the test session. Uses a separate `TEST_POSTGRES_URL`. |
| `fixtures/agents.py` | Pre-built `GraphState` instances for each stage of the pipeline (post-research, post-factcheck, etc.). Agents can be tested in isolation by injecting a pre-built state. |
| `unit/agents/` | One test file per agent. Tests `run(state)` with mocked LLM and tool responses. Verifies output schema correctness, state mutation, and error handling. |
| `unit/rag/` | Tests chunker (pure function), embedder (mock model), retriever (mock Qdrant). |
| `unit/graph/` | Tests `GraphState` initialization and the `quality_gate` conditional edge logic with various score/iteration combinations. |
| `unit/features/` | Tests service-layer logic with mocked DB sessions. |
| `integration/` | Tests that hit a real test database and real Qdrant instance. Verifies full pipeline behavior: session created → graph runs → report persisted → API returns correct response. |

---

## 4. Frontend — Detailed Breakdown

```
frontend/
│
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── globals.css
│   │   ├── history/
│   │   │   └── page.tsx
│   │   └── reports/
│   │       └── [id]/
│   │           └── page.tsx
│   │
│   ├── features/
│   │   ├── research/
│   │   │   ├── components/
│   │   │   │   ├── ResearchForm.tsx
│   │   │   │   ├── AgentTimeline.tsx
│   │   │   │   ├── AgentStep.tsx
│   │   │   │   └── StreamingBadge.tsx
│   │   │   ├── hooks/
│   │   │   │   ├── useStartResearch.ts
│   │   │   │   └── useAgentStream.ts
│   │   │   └── types.ts
│   │   │
│   │   ├── reports/
│   │   │   ├── components/
│   │   │   │   ├── ReportViewer.tsx
│   │   │   │   ├── ReportSection.tsx
│   │   │   │   ├── InlineCitation.tsx
│   │   │   │   ├── CitationList.tsx
│   │   │   │   ├── SourcePanel.tsx
│   │   │   │   └── ExportButton.tsx
│   │   │   ├── hooks/
│   │   │   │   └── useReport.ts
│   │   │   └── types.ts
│   │   │
│   │   └── history/
│   │       ├── components/
│   │       │   ├── HistoryList.tsx
│   │       │   ├── HistoryItem.tsx
│   │       │   └── HistoryFilters.tsx
│   │       ├── hooks/
│   │       │   └── useHistory.ts
│   │       └── types.ts
│   │
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts
│   │   │   ├── research.ts
│   │   │   ├── reports.ts
│   │   │   └── history.ts
│   │   ├── sse/
│   │   │   ├── EventSourceManager.ts
│   │   │   └── parseEvent.ts
│   │   └── utils/
│   │       ├── formatDate.ts
│   │       ├── formatDuration.ts
│   │       └── cn.ts
│   │
│   ├── components/
│   │   └── ui/
│   │       └── (shadcn components)
│   │
│   └── types/
│       ├── api.ts
│       └── events.ts
│
├── public/
│   └── fonts/
│
├── Dockerfile
├── next.config.ts
├── tailwind.config.ts
├── components.json
├── tsconfig.json
└── package.json
```

---

### 4.1 `src/app/`

**Purpose:** Next.js 15 App Router pages. These files are thin — they import and compose feature components, set page metadata, and handle routing. No business logic lives here.

| File | Purpose |
|---|---|
| `layout.tsx` | Root layout. Wraps all pages with `TanStack QueryProvider`, `ThemeProvider`, and the global navigation shell. |
| `page.tsx` | Home page (`/`). Renders `ResearchForm` and `AgentTimeline` side by side. |
| `globals.css` | Tailwind base imports and CSS custom properties for design tokens (colors, spacing). |
| `history/page.tsx` | History page. Renders `HistoryList` and `HistoryFilters`. |
| `reports/[id]/page.tsx` | Report page. Receives `report_id` from the URL segment, renders `ReportViewer`, `CitationList`, and `SourcePanel`. |

---

### 4.2 `src/features/`

**Purpose:** Feature-based component organization mirroring the backend. Each feature directory owns its components, hooks, and local types. Features never import from each other.

---

#### `src/features/research/`

| File | Purpose |
|---|---|
| `components/ResearchForm.tsx` | The query input form. A controlled textarea, optional settings panel (collapsed by default), and submit button. Calls `useStartResearch` on submit. |
| `components/AgentTimeline.tsx` | Vertical timeline of agent steps. Renders a list of `AgentStep` components. Receives `events: AgentEvent[]` as props — no data fetching. |
| `components/AgentStep.tsx` | A single timeline entry. Shows agent icon, agent name, status (pending/active/complete/failed), description text, and elapsed time. Purely presentational. |
| `components/StreamingBadge.tsx` | Small animated badge showing the currently active agent name. Shown in the page header during a running session. |
| `hooks/useStartResearch.ts` | Calls `POST /research/start`, stores the returned `session_id` in state, then calls `useAgentStream` to open the SSE connection. |
| `hooks/useAgentStream.ts` | Opens an `EventSource` for the given `session_id`. Appends incoming events to a local `events` array. Sets `reportId` when `graph_complete` is received. Cleans up on unmount. |
| `types.ts` | `AgentEvent`, `AgentEventType`, `SessionStatus` TypeScript types local to this feature. |

---

#### `src/features/reports/`

| File | Purpose |
|---|---|
| `components/ReportViewer.tsx` | Top-level report renderer. Renders the title, quality score badge, executive summary, and a list of `ReportSection` components. |
| `components/ReportSection.tsx` | Renders a single report section (heading + body). Parses `[N]` citation markers in the body text and replaces them with `InlineCitation` components. |
| `components/InlineCitation.tsx` | The `[N]` superscript. Renders as a tooltip-enabled link that shows the source title on hover and opens the source URL on click. |
| `components/CitationList.tsx` | The numbered bibliography at the bottom of the report. Each row shows number, title, domain, and a link icon. |
| `components/SourcePanel.tsx` | Sidebar panel listing all sources the Research Agent found (not just cited ones). Shows favicon, domain, title. |
| `components/ExportButton.tsx` | A single button. On click, triggers a `GET /reports/{id}/export/pdf` fetch and downloads the response as a file. Shows a loading spinner during generation. |
| `hooks/useReport.ts` | TanStack Query hook. Fetches `GET /reports/{id}` and returns the full `ReportResponse`. Handles loading and error states. |
| `types.ts` | `ReportResponse`, `SectionResponse`, `CitationResponse`, `SourceResponse` TypeScript types. |

---

#### `src/features/history/`

| File | Purpose |
|---|---|
| `components/HistoryList.tsx` | Renders the paginated list of `HistoryItem` rows. Handles empty state (no past sessions) and loading skeleton. |
| `components/HistoryItem.tsx` | Single row. Shows query preview (truncated to 80 chars), status badge, date, and actions (view report, delete). |
| `components/HistoryFilters.tsx` | Filter bar with status pills and sort selector. Controlled by URL search params so filters are bookmarkable. |
| `hooks/useHistory.ts` | TanStack Query hook. Fetches paginated history with filters. Handles pagination state and optimistic deletion. |
| `types.ts` | `HistoryItem`, `HistoryFilters`, `PaginatedResponse` types. |

---

### 4.3 `src/lib/`

**Purpose:** Shared utilities, API clients, and infrastructure code. Has no UI components and no knowledge of specific features.

---

#### `src/lib/api/`

| File | Purpose |
|---|---|
| `client.ts` | Base `apiFetch` wrapper around the native `fetch` API. Handles base URL injection, JSON serialization, error normalization (network errors → typed `ApiError`), and auth header injection (no-op in MVP; ready for tokens in v2). |
| `research.ts` | Typed functions for research endpoints: `startResearch(query, options)`, `getSession(sessionId)`. Each returns a typed response. |
| `reports.ts` | Typed functions: `getReport(reportId)`. |
| `history.ts` | Typed functions: `getHistory(filters, page)`, `deleteSession(sessionId)`. |

Separating API functions by domain means adding a new backend feature only requires adding a new `lib/api/{feature}.ts` file.

---

#### `src/lib/sse/`

| File | Purpose |
|---|---|
| `EventSourceManager.ts` | Class wrapping the native `EventSource` API. Handles open/close lifecycle, event listener registration, automatic reconnection on disconnect (exponential backoff), and cleanup. |
| `parseEvent.ts` | Pure function: `parseAgentEvent(rawEvent: MessageEvent) -> AgentEvent`. Validates and deserializes the raw SSE data string into a typed `AgentEvent`. Returns `null` for unparseable events. |

---

#### `src/lib/utils/`

| File | Purpose |
|---|---|
| `formatDate.ts` | `formatRelativeDate(iso: string)` — "2 hours ago", "Yesterday", "Jun 5". |
| `formatDuration.ts` | `formatDurationMs(ms: number)` — "4.2s", "1m 3s". Used in agent step elapsed time. |
| `cn.ts` | The standard Shadcn `cn()` helper that merges Tailwind class names. |

---

### 4.4 `src/types/`

**Purpose:** TypeScript types shared across multiple features. Only truly shared types live here — feature-specific types live in `features/{name}/types.ts`.

| File | Purpose |
|---|---|
| `api.ts` | `ApiError`, `PaginatedResponse<T>`, `ApiResponse<T>` — generic wrapper types used by all API functions. |
| `events.ts` | `AgentEvent`, `EventType` — SSE event types shared by the streaming hook and the timeline components. |

---

## 5. Infrastructure

```
infrastructure/
│
├── docker-compose.yml
├── docker-compose.dev.yml
├── docker-compose.test.yml
│
├── postgres/
│   └── init.sql
│
├── qdrant/
│   └── config.yaml
│
└── nginx/
    └── nginx.conf
```

| File | Purpose |
|---|---|
| `docker-compose.yml` | Production compose file. Defines all 5 services with resource limits, health checks, and named volumes. No bind mounts. |
| `docker-compose.dev.yml` | Dev override. Adds `volumes` bind mounts for hot reload on backend and frontend. Exposes extra debug ports. Used with `docker compose -f docker-compose.yml -f docker-compose.dev.yml up`. |
| `docker-compose.test.yml` | Test override. Spins up PostgreSQL and Qdrant on alternate ports with ephemeral volumes. Used in CI. |
| `postgres/init.sql` | One-time SQL run on first Postgres container startup. Creates the `research` database and the `research` user with correct permissions. Does not create tables — that is Alembic's job. |
| `qdrant/config.yaml` | Qdrant server configuration: storage path, CORS settings, gRPC port, log level. |
| `nginx/nginx.conf` | Optional reverse proxy config. Routes `/api` to the FastAPI container and `/` to the Next.js container. Used when running without a cloud load balancer. |

---

## 6. Docs

```
docs/
│
├── PRD.md
├── system-design.md
├── folder-structure.md
├── api-spec.md
├── roadmap.md
│
└── adr/
    ├── 001-langgraph-vs-crewai.md
    ├── 002-feature-based-architecture.md
    ├── 003-sse-vs-websocket.md
    └── 004-qdrant-single-collection.md
```

| File | Purpose |
|---|---|
| `PRD.md` | Product Requirements Document. |
| `system-design.md` | System architecture with Mermaid diagrams. |
| `folder-structure.md` | This document. |
| `api-spec.md` | Full REST + SSE API contract with request/response examples. |
| `roadmap.md` | Development milestones with acceptance criteria. |
| `adr/` | Architecture Decision Records. Every non-obvious technical decision gets a short ADR explaining what was decided, why, and what alternatives were rejected. |

**ADR format:**

```
# ADR-{N}: {Decision Title}
Status: Accepted
Date: YYYY-MM-DD

## Context
What situation forced a decision?

## Decision
What was decided?

## Consequences
What are the tradeoffs?

## Rejected Alternatives
What else was considered and why was it rejected?
```

---

## 7. File Naming Conventions

### Python (Backend)

| Type | Convention | Example |
|---|---|---|
| Modules | `snake_case.py` | `research_agent.py` |
| Classes | `PascalCase` | `ResearchAgent` |
| Functions | `snake_case` | `build_graph()` |
| Constants | `UPPER_SNAKE_CASE` | `SYSTEM_PROMPT` |
| Test files | `test_{module}.py` | `test_research_agent.py` |

### TypeScript (Frontend)

| Type | Convention | Example |
|---|---|---|
| Components | `PascalCase.tsx` | `ReportViewer.tsx` |
| Hooks | `camelCase.ts`, prefixed `use` | `useAgentStream.ts` |
| Utilities | `camelCase.ts` | `formatDate.ts` |
| Types | `camelCase.ts` or `PascalCase` | `types.ts` / `ApiError` |
| Constants | `UPPER_SNAKE_CASE` | `API_BASE_URL` |

---

## 8. Dependency Rules

These rules are enforced by code review and optionally by import linters. Violations are architecture violations.

```
┌───────────────────────────────────────────────────────────┐
│                    Dependency Rules                       │
│                                                           │
│  features/ ──► agents/    ✓ Services call agents          │
│  features/ ──► db/        ✓ Services call DB              │
│  features/ ──► streaming/ ✓ Services emit events          │
│  features/ ──► core/      ✓ Services use exceptions/log   │
│                                                           │
│  agents/   ──► tools/     ✓ Agents use tools              │
│  agents/   ──► rag/       ✗ Agents use tools, not RAG     │
│  agents/   ──► features/  ✗ Never — would create cycle    │
│  agents/   ──► db/        ✗ Never — only via base._log()  │
│                                                           │
│  graph/    ──► agents/    ✓ Nodes wrap agent calls        │
│  graph/    ──► features/  ✗ Never                         │
│                                                           │
│  rag/      ──► db/qdrant/ ✓ RAG writes/reads Qdrant       │
│  rag/      ──► features/  ✗ Never                         │
│                                                           │
│  core/     ──► anything   ✗ core/ has zero internal deps  │
│                                                           │
│  features/ ──► features/  ✗ Never — use shared services   │
└───────────────────────────────────────────────────────────┘
```

### The Golden Rule

> **Arrows point inward. Features and agents depend on infrastructure, never on each other.**

This rule ensures that:
- Any agent can be replaced without touching other agents
- Any feature can be removed without breaking other features
- The graph, RAG, and streaming layers can all be tested in isolation
- The entire system composes cleanly from the bottom up

---

*Document ends. Next document: `docs/api-spec.md`.*
