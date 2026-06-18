"""
Individual async health-check functions.

Each function performs a lightweight probe against one downstream service and
returns a ``ServiceStatus`` object.  Errors are caught internally — a failed
check returns ``ServiceState.DOWN`` rather than raising, so a single
unavailable service does not prevent the other checks from running.

All four checks are fired concurrently by the router using ``asyncio.gather``,
so the total latency of ``GET /health`` is bounded by the slowest individual
check, not their sum.

Notes
-----
The Groq check does **not** make a real API call to avoid consuming free-tier
tokens on every health probe.  It reports ``up`` when the API key is
configured, ``down`` when it is empty.
"""

import time

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.postgres.engine import get_engine
from app.db.qdrant.client import get_qdrant_client
from app.db.redis.client import get_redis_client
from app.features.health.schemas import ServiceState, ServiceStatus

logger = get_logger(__name__)


async def check_postgres() -> ServiceStatus:
    """Probe PostgreSQL by executing ``SELECT 1`` on the async engine.

    Uses the engine directly (not via ``get_db``) to avoid opening a full
    unit-of-work session for a trivial connectivity check.

    Returns:
        ``ServiceStatus`` with ``up`` and latency on success, ``down`` and
        an error message on any exception.
    """
    start = time.monotonic()
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return ServiceStatus(status=ServiceState.UP, latency_ms=latency_ms)
    except Exception as exc:
        logger.warning("PostgreSQL health check failed.", error=str(exc))
        return ServiceStatus(status=ServiceState.DOWN, error=str(exc))


async def check_qdrant() -> ServiceStatus:
    """Probe Qdrant by listing all collections via the async client.

    A successful ``get_collections()`` call confirms both TCP connectivity and
    that the Qdrant HTTP API is responding correctly.

    Returns:
        ``ServiceStatus`` with ``up`` and latency on success, ``down`` and
        an error message on any exception.
    """
    start = time.monotonic()
    try:
        client = get_qdrant_client()
        await client.get_collections()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return ServiceStatus(status=ServiceState.UP, latency_ms=latency_ms)
    except Exception as exc:
        logger.warning("Qdrant health check failed.", error=str(exc))
        return ServiceStatus(status=ServiceState.DOWN, error=str(exc))


async def check_redis() -> ServiceStatus:
    """Probe Redis by sending a ``PING`` command.

    ``PING`` is the canonical Redis connectivity check — it returns ``PONG``
    and has negligible overhead.

    Returns:
        ``ServiceStatus`` with ``up`` and latency on success, ``down`` and
        an error message on any exception.
    """
    start = time.monotonic()
    try:
        client = get_redis_client()
        await client.ping()
        latency_ms = round((time.monotonic() - start) * 1000, 2)
        return ServiceStatus(status=ServiceState.UP, latency_ms=latency_ms)
    except Exception as exc:
        logger.warning("Redis health check failed.", error=str(exc))
        return ServiceStatus(status=ServiceState.DOWN, error=str(exc))


async def check_groq(groq_api_key: str) -> ServiceStatus:
    """Check whether the Groq API key is configured.

    No network call is made — this avoids consuming free-tier tokens on health
    probes.  Reports ``up`` when a non-empty key is present, ``down`` otherwise.

    Args:
        groq_api_key: The configured Groq API key from settings.

    Returns:
        ``ServiceStatus`` indicating whether the key is present.
    """
    if groq_api_key:
        return ServiceStatus(status=ServiceState.UP, latency_ms=0.0)

    return ServiceStatus(
        status=ServiceState.DOWN,
        error="GROQ_API_KEY is not configured.",
    )
