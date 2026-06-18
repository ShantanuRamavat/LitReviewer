"""
Redis async client singleton.

Redis is used for two purposes in Nexus Research:
1. **SSE event queue** — agents push events to a Redis list keyed by
   ``stream:{session_id}``; the SSE endpoint consumes from the same list.
2. **Rate limiting** — a sliding window counter is maintained per client IP.

The client is created during application startup (``init_redis_client``) and
closed on shutdown (``close_redis_client``).  The ``hiredis`` C extension is
used for parsing if available (installed via ``redis[hiredis]``), which
provides a significant throughput improvement over the pure-Python parser.
"""

import logging

import redis.asyncio as aioredis

from app.config import Settings

logger = logging.getLogger(__name__)

_client: aioredis.Redis | None = None  # type: ignore[type-arg]


async def init_redis_client(settings: Settings) -> None:
    """Create and cache the async Redis client singleton.

    Uses a connection pool under the hood (redis-py default behaviour) so
    concurrent requests do not block waiting for a single connection.

    Should be called once during application startup.  Calling it a second
    time raises a ``RuntimeError``.

    Args:
        settings: Validated application settings providing the Redis URL.

    Raises:
        RuntimeError: If the client has already been initialised.
    """
    global _client

    if _client is not None:
        raise RuntimeError("Redis client is already initialised.")

    _client = aioredis.from_url(
        settings.redis_url,
        # decode_responses=True makes all Redis responses str instead of bytes,
        # which is more ergonomic for the SSE event queue and rate limiter.
        decode_responses=True,
        # Use hiredis parser if available; falls back to pure-Python silently.
        encoding="utf-8",
    )

    # Verify connectivity at startup rather than at first use.
    await _client.ping()

    logger.info("Redis async client initialised.", extra={"url": settings.redis_url})


def get_redis_client() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return the cached Redis client.

    Returns:
        The ``aioredis.Redis`` singleton.

    Raises:
        RuntimeError: If ``init_redis_client`` has not been called yet.
    """
    if _client is None:
        raise RuntimeError(
            "Redis client is not initialised. "
            "Ensure init_redis_client() is called during application startup."
        )
    return _client


async def close_redis_client() -> None:
    """Close the Redis connection pool.

    Should be called during application shutdown.  Safe to call if the client
    was never initialised (no-op in that case).
    """
    global _client

    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Redis async client closed.")
