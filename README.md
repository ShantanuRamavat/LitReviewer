# LitReviewer

A production-grade Multi-Agent Literature Review Platform built for PhD students. LitReviewer orchestrates a team of specialised AI agents to automatically conduct, fact-check, critique, and write structured academic literature review reports — complete with inline citations and research gap analysis.

**PhD mode** produces 10,000–20,000-word literature review reports with annotated research gaps, methodological critiques, and PhD-specific supplementary annotations. **General mode** produces 3,000–5,000-word research summaries.

---

## Prerequisites

| Tool | Version | Purpose |
|---|---|---|
| Docker Desktop | ≥ 4.30 | Container runtime |
| Docker Compose | V2 (bundled with Docker Desktop) | Service orchestration |
| Python | 3.12+ | Local development only |
| [uv](https://docs.astral.sh/uv/) | latest | Python package manager |

---

## Quick Start (Docker)

### 1. Clone and configure

```bash
git clone <repo-url> nexus-research
cd nexus-research

# Copy the environment template
cp .env.example .env
```

Open `.env` and fill in the required API keys:

```dotenv
GROQ_API_KEY=your-groq-key-here
TAVILY_API_KEY=your-tavily-key-here
```

All other values have sensible defaults and do not need to be changed for local development.

### 2. Start all services

```bash
cd infrastructure
docker compose up -d
```

This starts:
- **PostgreSQL 16** on port `5432`
- **Qdrant** on port `6333`
- **Redis 7** on port `6379`
- **FastAPI backend** on port `8000`

All services include health checks — Docker Compose will wait for each dependency to be healthy before starting the backend.

### 3. Verify the health endpoint

```bash
curl http://localhost:8000/api/v1/health | python -m json.tool
```

Expected response when all services are running:

```json
{
    "status": "healthy",
    "version": "1.0.0",
    "environment": "development",
    "services": {
        "postgres": {"status": "up", "latency_ms": 3.4},
        "qdrant":   {"status": "up", "latency_ms": 8.1},
        "redis":    {"status": "up", "latency_ms": 1.2},
        "groq":     {"status": "up", "latency_ms": 0.0}
    }
}
```

HTTP 200 = all healthy. HTTP 503 = one or more services degraded (check the `services` object to identify which).

### 4. Open the API docs

Navigate to [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive Swagger UI (only available in development mode).

---

## Research Modes

Pass `mode` when submitting a research request:

| Mode | Word Count | Use Case |
|---|---|---|
| `general` (default) | 3,000–5,000 words | General research summaries |
| `phd` | 10,000–20,000 words | Full academic literature reviews |

In `phd` mode the WriterAgent produces additional output: annotated research gaps, methodological critique notes, and a supplementary PhD annotations section suitable for including in a thesis introduction or literature review chapter.

---

## Development Mode (Hot Reload)

For development with automatic reload on code changes:

```bash
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

The `backend/app/` directory is bind-mounted into the container. Any change you save is picked up within one second without rebuilding the image.

---

## Local Development (Without Docker)

To run the backend directly on your machine (still requires Docker for PostgreSQL, Qdrant, and Redis):

### 1. Start infrastructure services only

```bash
cd infrastructure
docker compose up -d postgres qdrant redis
```

### 2. Set up the Python environment

```bash
cd backend

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv sync

# Copy the local .env template
cp .env.example .env
# Edit .env — all URLs use "localhost" instead of Docker service names
```

### 3. Run the backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

The API is available at [http://localhost:8000](http://localhost:8000).

---

## Running Tests

```bash
cd backend

# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=app --cov-report=term-missing

# Run a specific test file
uv run pytest tests/unit/features/test_health.py -v
```

---

## Project Structure

```
nexus-research/
├── backend/
│   ├── app/
│   │   ├── main.py              # App factory + lifespan
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── core/                # Logging, exceptions, middleware
│   │   ├── db/                  # Postgres, Qdrant, Redis clients
│   │   ├── llm/                 # Provider-agnostic LLM client (Gemini / Groq / Anthropic)
│   │   ├── rag/                 # Document ingestion, chunking, embedding, retrieval
│   │   ├── agents/
│   │   │   ├── research/        # ResearchAgent — RAG + Tavily web search
│   │   │   ├── factchecker/     # FactCheckerAgent — claim verification
│   │   │   ├── critic/          # CriticAgent — quality scoring + gap detection
│   │   │   └── writer/          # WriterAgent — sectional report generation
│   │   ├── graph/               # ResearchWorkflow — top-level LangGraph orchestration
│   │   └── features/
│   │       ├── health/          # GET /api/v1/health
│   │       └── research/        # POST /api/v1/research
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── infrastructure/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── postgres/init.sql
├── docs/
│   ├── PRD.md
│   ├── system-design.md
│   └── folder-structure.md
└── .env.example
```

---

## Environment Variables Reference

### Required

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key — free tier at [console.groq.com](https://console.groq.com) |
| `TAVILY_API_KEY` | Tavily Search API key — get one at [tavily.com](https://tavily.com) |

### LLM Provider

All agents use **Groq (llama-3.3-70b-versatile)** by default. Anthropic is the only supported alternative:

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `groq` | Global LLM provider: `groq` or `anthropic` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model identifier |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (only needed if `LLM_PROVIDER=anthropic`) |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Anthropic model identifier |
| `RESEARCH_LLM_PROVIDER` | *(inherits)* | Override LLM provider for ResearchAgent only |
| `WRITER_LLM_PROVIDER` | *(inherits)* | Override LLM provider for WriterAgent only |
| `CRITIC_LLM_PROVIDER` | *(inherits)* | Override LLM provider for CriticAgent only |
| `FACTCHECKER_LLM_PROVIDER` | *(inherits)* | Override LLM provider for FactCheckerAgent only |

### Infrastructure

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `POSTGRES_URL` | `postgresql+asyncpg://...@postgres:5432/research` | Async PostgreSQL URL |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant REST API URL |
| `REDIS_URL` | `redis://redis:6379` | Redis connection URL |

### Research Tuning

| Variable | Default | Description |
|---|---|---|
| `MAX_ITERATIONS` | `3` | Max research loop iterations before writing |
| `MIN_QUALITY_SCORE` | `0.7` | Min CriticAgent score required to proceed to writing |
| `RAG_TOP_K` | `8` | Number of chunks retrieved from Qdrant per query |
| `TAVILY_MAX_RESULTS` | `8` | Max web search results per Tavily query |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max research requests per IP per minute |

---

## Useful Commands

```bash
# Stop all services
docker compose -C infrastructure down

# Stop and remove all data volumes (full reset)
docker compose -C infrastructure down -v

# Tail backend logs
docker compose -C infrastructure logs -f backend

# Check health from the terminal
curl -s http://localhost:8000/api/v1/health | python -m json.tool

# Open a psql shell
docker exec -it infrastructure-postgres-1 psql -U research_user -d research

# Open a redis-cli shell
docker exec -it infrastructure-redis-1 redis-cli

# Open the Qdrant web UI
open http://localhost:6333/dashboard
```

---

## Milestone Progress

| Milestone | Status | Description |
|---|---|---|
| M1 — Infrastructure | ✅ Complete | FastAPI, health endpoint, Docker Compose, all DB clients |
| M2 — Database Models | 🔜 Next | SQLAlchemy models, Alembic migrations, session CRUD |
| M3 — Research Agent | ✅ Complete | LangGraph graph, ResearchAgent, Tavily integration, RAG retrieval |
| M4 — Writer Agent | ✅ Complete | WriterAgent, PhD mode, sectional report output |
| M5 — RAG Pipeline | ✅ Complete | Qdrant ingestion, bge-large-en-v1.5 embeddings, chunker |
| M6 — Streaming | 🔜 | SSE endpoint, real-time agent progress |
| M7 — Report API | 🔜 | Report retrieval, history endpoints |
| M8 — Frontend | 🔜 | Next.js UI, streaming display, report viewer |
