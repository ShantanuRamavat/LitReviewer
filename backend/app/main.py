"""
FastAPI application factory.

This module is the composition root of the backend.  It:
1. Defines the ``lifespan`` context manager that initialises all shared
   resources (DB connections, logging) on startup and tears them down cleanly
   on shutdown.
2. Defines ``create_app()`` which builds and returns the configured
   ``FastAPI`` instance.
3. Exposes the top-level ``app`` object that Uvicorn imports.

Design rules enforced here:
- No business logic lives in this file.
- All wiring (middleware, routers, exception handlers) is registered here and
  nowhere else.
- Every resource initialised in ``lifespan`` must have a matching cleanup step
  in the shutdown branch.

Usage::

    # Run locally
    uvicorn app.main:app --reload

    # Run in Docker
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from importlib.metadata import version, PackageNotFoundError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, get_settings


def _get_version() -> str:
    try:
        return version("litreview")
    except PackageNotFoundError:
        return "0.0.0"
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware, register_exception_handlers
from app.db.postgres.engine import close_engine, init_engine
from app.db.qdrant.client import (
    close_qdrant_client,
    ensure_collection_exists,
    init_qdrant_client,
)
from app.db.redis.client import close_redis_client, init_redis_client
from app.features.health.router import router as health_router
from app.features.research.router import router as research_router
from app.graph.workflow import ResearchWorkflow
from app.llm import close_llm_client, init_llm_client
from app.rag import close_embedder, init_embedder


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown.

    Startup sequence (order matters — logging first, then DB clients):
    1. Configure structured logging so all subsequent log lines are formatted.
    2. Initialise the PostgreSQL async engine and session factory.
    3. Initialise the Qdrant async client and bootstrap the vector collection.
    4. Initialise the Redis async client and verify connectivity via PING.
    5. Initialise the LLM client (validates API key; selects active provider).

    Shutdown sequence (reverse order of startup):
    1. Close Embedder (releases model memory).
    2. Close LLM client.
    3. Close Redis connection pool.
    4. Close Qdrant client.
    5. Dispose the SQLAlchemy engine, draining the connection pool.

    Args:
        app: The FastAPI application instance (provided by the framework).

    Yields:
        Control to the running application.
    """
    settings: Settings = get_settings()

    # Step 1 — logging must be configured before any log calls below.
    configure_logging(settings)
    logger = get_logger(__name__)

    logger.info(
        "Starting LitReviewer API",
        version=_get_version(),
        environment=settings.environment,
    )

    # Step 2 — PostgreSQL
    try:
        init_engine(settings)
        logger.info("PostgreSQL engine ready.")
    except Exception as exc:
        logger.error("Failed to initialise PostgreSQL engine.", error=str(exc))
        raise

    # Step 3 — Qdrant
    try:
        init_qdrant_client(settings)
        await ensure_collection_exists(settings)
        logger.info(
            "Qdrant client ready.",
            collection=settings.qdrant_collection_name,
        )
    except Exception as exc:
        # Qdrant being unavailable at startup should not stop the API from
        # starting — health checks will surface it as degraded.
        logger.warning("Qdrant initialisation failed; health check will report degraded.", error=str(exc))

    # Step 4 — Redis
    try:
        await init_redis_client(settings)
        logger.info("Redis client ready.")
    except Exception as exc:
        logger.warning("Redis initialisation failed; health check will report degraded.", error=str(exc))

    # Step 5 — LLM client
    # A missing or invalid API key is a hard failure: the platform cannot
    # function without an LLM.  We raise here so the process exits with a
    # clear error message rather than serving requests that will all fail.
    try:
        init_llm_client(settings)
        from app.llm import get_llm_client  # noqa: PLC0415
        _ready_client = get_llm_client()
        logger.info(
            "LLM client ready.",
            provider=_ready_client.provider_name,
            model=_ready_client.model_name,
        )
    except Exception as exc:
        logger.error(
            "Failed to initialise LLM client — check API key configuration.",
            error=str(exc),
        )
        raise

    # Step 6 — Embedder
    # Loading sentence-transformers downloads the model on first run (≈1.3 GB
    # for bge-large-en-v1.5) and blocks the event loop briefly.  A missing or
    # incompatible model is a hard failure: RAG cannot function without it.
    try:
        await init_embedder(settings)
        logger.info(
            "Embedder ready.",
            model=settings.embedding_model,
        )
    except Exception as exc:
        logger.error(
            "Failed to initialise embedder — check embedding_model configuration.",
            error=str(exc),
        )
        raise

    # Step 7 — ResearchWorkflow (compiles LangGraph graphs; expensive once, reused per request).
    try:
        app.state.workflow = ResearchWorkflow()
        logger.info("ResearchWorkflow compiled and ready.")
    except Exception as exc:
        logger.error("Failed to compile ResearchWorkflow.", error=str(exc))
        raise

    # Step 8 — Orphan cleanup.
    # Any session left in "running" state from a previous process is now an orphan
    # (its background task is gone). Mark them failed so the frontend stops polling.
    try:
        from datetime import datetime, timezone
        from sqlalchemy import select, update
        from app.db.postgres.engine import get_session_factory
        from app.db.models import ResearchSession

        factory = get_session_factory()
        async with factory() as db:
            result = await db.execute(
                select(ResearchSession).where(ResearchSession.status == "running")
            )
            orphans = result.scalars().all()
            if orphans:
                for s in orphans:
                    s.status = "failed"
                    s.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.warning(
                    "Marked orphaned sessions as failed.",
                    count=len(orphans),
                    ids=[str(s.id) for s in orphans],
                )
    except Exception as exc:
        logger.warning("Orphan cleanup failed (non-fatal).", error=str(exc))

    logger.info("All startup tasks complete.  LitReviewer API is accepting requests.")

    # ---- hand control to the running application ---------------------------
    yield
    # ---- shutdown begins here ----------------------------------------------

    logger.info("Shutting down LitReviewer API.")

    close_embedder()
    logger.info("Embedder closed.")

    close_llm_client()
    logger.info("LLM client closed.")

    await close_redis_client()
    logger.info("Redis client closed.")

    await close_qdrant_client()
    logger.info("Qdrant client closed.")

    await close_engine()
    logger.info("PostgreSQL engine disposed.")

    logger.info("LitReviewer API shutdown complete.")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    Separating construction from the module-level ``app`` assignment makes the
    factory unit-testable: tests can call ``create_app()`` and override
    dependencies without side-effects on the global ``app`` object.

    Returns:
        A fully configured ``FastAPI`` instance ready for Uvicorn.
    """
    settings = get_settings()

    app = FastAPI(
        title="LitReviewer API",
        description=(
            "Multi-Agent Literature Review Platform — orchestrates a team of AI agents "
            "to produce verified, cited academic literature reviews for PhD students."
        ),
        version=_get_version(),
        # Disable Swagger UI and ReDoc in production to reduce attack surface.
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )

    # ---- Middleware (applied in reverse registration order by Starlette) ----

    # CORS — must be registered before RequestIDMiddleware so preflight
    # OPTIONS requests are handled correctly.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    # Request ID — adds X-Request-ID header and binds request_id to structlog.
    app.add_middleware(RequestIDMiddleware)

    # ---- Exception handlers ------------------------------------------------
    register_exception_handlers(app)

    # ---- Routers -----------------------------------------------------------
    # API versioning prefix: /api/v1
    api_prefix = f"/api/{settings.api_version}"

    app.include_router(health_router, prefix=api_prefix)
    app.include_router(research_router, prefix=api_prefix)

    return app


# Module-level app instance — this is what Uvicorn imports.
app: FastAPI = create_app()
