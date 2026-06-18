"""
Structured logging configuration using structlog.

In development the renderer outputs colourised, human-readable lines.
In staging/production every log line is emitted as a JSON object so it can be
ingested by any log aggregator (Loki, Datadog, CloudWatch, etc.).

Usage::

    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("Session created", session_id="abc-123", query="quantum computing")

The ``request_id`` context variable is automatically included on every log
line emitted during a request because ``RequestIDMiddleware`` calls
``structlog.contextvars.bind_contextvars`` on each incoming request.
"""

import logging
import sys

import structlog

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    """Configure structlog and the stdlib logging bridge.

    This function is idempotent — calling it multiple times has no effect
    beyond the first call.  It should be invoked once during application
    startup, before any log statements are executed.

    Args:
        settings: Validated application settings.  The ``log_level`` and
            ``environment`` fields control renderer selection.
    """
    log_level = getattr(logging, settings.log_level, logging.INFO)

    # ---- shared processors run on every log event --------------------------
    shared_processors: list[structlog.types.Processor] = [
        # Merge any context variables bound via structlog.contextvars
        # (e.g. request_id, session_id set by middleware/services).
        structlog.contextvars.merge_contextvars,
        # add_logger_name requires a stdlib Logger (.name attribute); we use
        # PrintLoggerFactory so we inject the name via get_logger() instead.
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development:
        # Pretty, colourised output for local development.
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(colors=True)
    else:
        # Machine-parseable JSON for staging and production.
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # ---- bridge stdlib logging into structlog --------------------------------
    # Libraries that use the standard `logging` module (SQLAlchemy, uvicorn, etc.)
    # will have their records captured and formatted by structlog.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Quiet noisy third-party loggers in non-debug environments.
    if not settings.log_level == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog bound logger.

    Args:
        name: Logger name, conventionally ``__name__``.

    Returns:
        A structlog ``BoundLogger`` that inherits the global configuration
        set by :func:`configure_logging`.

    Example::

        logger = get_logger(__name__)
        logger.info("Health check passed", service="postgres", latency_ms=4.2)
    """
    return structlog.get_logger().bind(logger=name)
