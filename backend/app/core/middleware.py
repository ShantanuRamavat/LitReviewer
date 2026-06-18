"""
FastAPI middleware and exception handlers.

Registers two cross-cutting behaviours:

1. **RequestIDMiddleware** — assigns a UUID to every incoming request, injects
   it into the structlog context so every log line emitted during the request
   carries ``request_id``, and adds it as an ``X-Request-ID`` response header
   for client-side correlation.

2. **register_exception_handlers** — maps every ``NexusBaseException`` subclass
   to a structured JSON 4xx/5xx response.  Unhandled exceptions produce a
   generic 500 with the full traceback logged server-side but not exposed to
   the client.
"""

import uuid

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.exceptions import NexusBaseException
from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every HTTP request.

    The ID is:
    - Bound into the structlog context-var store so all log lines for this
      request automatically include ``request_id``.
    - Added to the response as the ``X-Request-ID`` header so clients and
      load balancers can correlate logs with specific requests.
    - Cleared from the context-var store after the response is sent to
      prevent context leakage between requests on the same worker.

    Args:
        app: The ASGI application being wrapped.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        """Process the request, injecting a request ID into the log context.

        Args:
            request: Incoming Starlette request.
            call_next: ASGI callable for the next middleware / route handler.

        Returns:
            The HTTP response with the ``X-Request-ID`` header set.
        """
        request_id = str(uuid.uuid4())

        # Bind request_id so every log line in this request includes it.
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        finally:
            # Always clear context variables — prevents leakage if the worker
            # is reused for a different request.
            structlog.contextvars.clear_contextvars()

        response.headers["X-Request-ID"] = request_id
        return response


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI application.

    Two handlers are registered:

    - ``NexusBaseException`` and its subclasses produce a JSON response with
      the exception's ``status_code`` and ``detail`` string.
    - All other ``Exception`` types produce a ``500`` response.  The full
      traceback is logged at ERROR level but is **not** included in the
      response body to avoid leaking internal details.

    Args:
        app: The FastAPI application instance to attach handlers to.
    """

    @app.exception_handler(NexusBaseException)
    async def nexus_exception_handler(
        request: Request,
        exc: NexusBaseException,
    ) -> JSONResponse:
        """Handle all known Nexus domain exceptions.

        Args:
            request: The request that triggered the exception.
            exc: The domain exception instance.

        Returns:
            JSON response with the appropriate HTTP status code.
        """
        logger.warning(
            "Domain exception",
            exc_type=type(exc).__name__,
            detail=exc.detail,
            status_code=exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle all unexpected exceptions as generic 500 errors.

        The full traceback is written to the log so engineers can diagnose
        the problem, but only a generic message is returned to the client.

        Args:
            request: The request that triggered the exception.
            exc: The unexpected exception instance.

        Returns:
            JSON 500 response with a generic error message.
        """
        logger.exception(
            "Unhandled exception",
            exc_type=type(exc).__name__,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected internal error occurred."},
        )
