"""
Async SQLAlchemy engine and session factory.

The engine and session factory are module-level singletons initialised once
during application startup (via ``init_engine``) and disposed on shutdown
(via ``close_engine``).  All other modules access them through the
``get_engine`` / ``get_session_factory`` getters, which raise a clear
``RuntimeError`` if called before initialisation.

Why a singleton rather than ``app.state``?
- Avoids passing ``request.app`` through every service and utility layer.
- Makes the DB layer independently testable: call ``init_engine(test_settings)``
  in the test fixture, then call ``close_engine()`` in teardown.
- Mirrors how every production application manages long-lived connection pools.
"""

import logging

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings

logger = logging.getLogger(__name__)

# Module-level singletons — populated by init_engine(), cleared by close_engine().
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models.

    Defined here so every model file can do ``from app.db.postgres.engine import Base``
    and Alembic's ``env.py`` has a single import to discover all metadata.
    """


def init_engine(settings: Settings) -> None:
    """Initialise the async SQLAlchemy engine and session factory.

    Should be called once during application startup (inside the FastAPI
    ``lifespan`` context manager).  Calling it a second time raises a
    ``RuntimeError`` to prevent accidental double-initialisation.

    Args:
        settings: Validated application settings used to configure the
            connection URL and pool parameters.

    Raises:
        RuntimeError: If the engine has already been initialised.
    """
    global _engine, _session_factory

    if _engine is not None:
        raise RuntimeError("PostgreSQL engine is already initialised.")

    _engine = create_async_engine(
        settings.postgres_url.get_secret_value(),
        # Echo SQL statements only in development — avoids log noise in prod.
        echo=settings.is_development,
        pool_size=settings.postgres_pool_size,
        max_overflow=settings.postgres_max_overflow,
        # Recycle idle connections to prevent stale TCP connections being
        # silently dropped by firewalls or cloud load balancers.
        pool_recycle=settings.postgres_pool_recycle,
        # Surface connection errors quickly rather than waiting on a hung pool.
        pool_timeout=30,
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        # expire_on_commit=False prevents lazy-load errors when ORM objects
        # are accessed after the session has been committed.
        expire_on_commit=False,
    )

    logger.info("PostgreSQL async engine initialised.")


def get_engine() -> AsyncEngine:
    """Return the initialised async engine.

    Returns:
        The ``AsyncEngine`` singleton.

    Raises:
        RuntimeError: If ``init_engine`` has not been called yet.
    """
    if _engine is None:
        raise RuntimeError(
            "PostgreSQL engine is not initialised. "
            "Ensure init_engine() is called during application startup."
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the initialised async session factory.

    Returns:
        An ``async_sessionmaker`` that creates ``AsyncSession`` instances.

    Raises:
        RuntimeError: If ``init_engine`` has not been called yet.
    """
    if _session_factory is None:
        raise RuntimeError(
            "Session factory is not initialised. "
            "Ensure init_engine() is called during application startup."
        )
    return _session_factory


async def close_engine() -> None:
    """Dispose the engine and release all pooled connections.

    Should be called during application shutdown.  Safe to call even if
    the engine was never initialised (no-op in that case).
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("PostgreSQL async engine disposed.")
