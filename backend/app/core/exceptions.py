"""
Custom exception hierarchy for LitReviewer.

Every domain exception maps to an HTTP status code so the global exception
handler in ``middleware.py`` can produce consistent JSON error responses
without requiring try/except blocks in route handlers.

Usage::

    raise SessionNotFoundError(session_id="abc-123")
    raise AgentExecutionError(agent="ResearchAgent", detail="Tavily timed out")
"""


class NexusBaseException(Exception):
    """Base class for all Nexus Research application exceptions.

    Subclasses must set ``status_code`` and a default ``detail`` string.
    Either may be overridden at raise time by passing ``detail=...``.
    """

    status_code: int = 500
    detail: str = "An unexpected error occurred."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


# -----------------------------------------------------------------------------
# 400 — Bad Request
# -----------------------------------------------------------------------------


class InvalidQueryError(NexusBaseException):
    """The research query failed validation (e.g. empty, too long)."""

    status_code = 400
    detail = "The research query is invalid."


# -----------------------------------------------------------------------------
# 404 — Not Found
# -----------------------------------------------------------------------------


class SessionNotFoundError(NexusBaseException):
    """A research session with the given ID does not exist."""

    status_code = 404
    detail = "Research session not found."

    def __init__(self, session_id: str | None = None) -> None:
        detail = f"Research session '{session_id}' not found." if session_id else self.__class__.detail
        super().__init__(detail=detail)


class ReportNotFoundError(NexusBaseException):
    """A report with the given ID does not exist."""

    status_code = 404
    detail = "Report not found."

    def __init__(self, report_id: str | None = None) -> None:
        detail = f"Report '{report_id}' not found." if report_id else self.__class__.detail
        super().__init__(detail=detail)


# -----------------------------------------------------------------------------
# 429 — Rate Limited
# -----------------------------------------------------------------------------


class RateLimitExceededError(NexusBaseException):
    """The client has exceeded the allowed request rate."""

    status_code = 429
    detail = "Too many requests. Please wait before submitting another research query."


# -----------------------------------------------------------------------------
# 503 — Service Unavailable
# -----------------------------------------------------------------------------


class DatabaseConnectionError(NexusBaseException):
    """A required database (Postgres / Qdrant / Redis) is unreachable."""

    status_code = 503
    detail = "A required database service is currently unavailable."


class ServiceUnavailableError(NexusBaseException):
    """A downstream service (LLM API, search API) is unavailable."""

    status_code = 503
    detail = "A downstream service is currently unavailable."


# -----------------------------------------------------------------------------
# 500 — Internal Server Error
# -----------------------------------------------------------------------------


class AgentExecutionError(NexusBaseException):
    """An agent failed to produce a valid output after all retries."""

    status_code = 500
    detail = "An agent encountered an unrecoverable error."

    def __init__(self, agent: str | None = None, detail: str | None = None) -> None:
        msg = detail or (f"Agent '{agent}' failed." if agent else self.__class__.detail)
        super().__init__(detail=msg)


class ConfigurationError(NexusBaseException):
    """A required configuration value is missing or invalid at runtime."""

    status_code = 500
    detail = "A required configuration value is missing or invalid."


class PDFGenerationError(NexusBaseException):
    """PDF rendering failed for the given report."""

    status_code = 500
    detail = "Failed to generate the PDF report."
