"""
LLM-specific exception hierarchy.

Every exception maps to a specific failure mode so callers can decide whether
to retry, surface an error to the user, or alert on-call.

Hierarchy
---------
``LLMBaseException``
├── ``LLMRateLimitError``        HTTP 429  — retryable, back off
├── ``LLMAuthError``             HTTP 401/403 — not retryable, config problem
├── ``LLMBadRequestError``       HTTP 400  — not retryable, bad prompt
├── ``LLMServerError``           HTTP 500/503 — retryable
├── ``LLMTimeoutError``          Network   — retryable
├── ``LLMRetryExhaustedError``   All retries used — terminal failure
└── ``LLMProviderNotConfiguredError``  Missing API key at startup

Usage in providers::

    except google_exceptions.ResourceExhausted as exc:
        raise LLMRateLimitError(
            provider="gemini",
            model="gemini-2.5-flash",
            detail=str(exc),
        ) from exc

Usage in callers::

    try:
        response = await llm_client.complete(messages)
    except LLMRateLimitError:
        # Already exhausted retries; surface a 503 to the user
        raise ServiceUnavailableError("LLM rate limit reached.")
    except LLMBadRequestError as exc:
        # Bad prompt — log and raise 400
        raise InvalidQueryError(detail=exc.detail)
"""


class LLMBaseException(Exception):
    """Base class for all LLM layer exceptions.

    Attributes:
        provider: Name of the LLM provider (e.g. ``"gemini"``).
        model: Model identifier (e.g. ``"gemini-2.5-flash"``).
        detail: Human-readable description of the error.
    """

    def __init__(
        self,
        detail: str,
        provider: str = "unknown",
        model: str = "unknown",
    ) -> None:
        self.detail = detail
        self.provider = provider
        self.model = model
        super().__init__(detail)

    def __str__(self) -> str:
        return f"[{self.provider}/{self.model}] {self.detail}"


class LLMRateLimitError(LLMBaseException):
    """The LLM API returned HTTP 429 (rate limit exceeded).

    This error is **retryable** — ``LLMClient`` will back off and retry.
    If all retries are exhausted, ``LLMRetryExhaustedError`` is raised instead.
    """


class LLMAuthError(LLMBaseException):
    """The API key is invalid, expired, or missing required permissions.

    Maps to HTTP 401 (Unauthenticated) or 403 (PermissionDenied).
    This error is **not retryable** — retrying will not fix an auth problem.
    Operators must check the API key configuration.
    """


class LLMBadRequestError(LLMBaseException):
    """The request was malformed or the prompt violated content policy.

    Maps to HTTP 400 (InvalidArgument) or content-safety rejections.
    This error is **not retryable** — the same prompt will fail every time.
    The agent layer should re-prompt with a corrected message.
    """


class LLMServerError(LLMBaseException):
    """The LLM API returned an unexpected server-side error.

    Maps to HTTP 500 (InternalServerError) or 503 (ServiceUnavailable).
    This error is **retryable** — transient upstream failures often resolve
    within seconds.
    """


class LLMTimeoutError(LLMBaseException):
    """The network connection to the LLM API timed out.

    This error is **retryable** — network issues are often transient.
    """


class LLMRetryExhaustedError(LLMBaseException):
    """All retry attempts were used without a successful completion.

    Raised by ``LLMClient.complete()`` after ``max_retries`` retryable failures.
    Wraps the last underlying ``LLMBaseException`` as the cause.

    Attributes:
        attempts: Number of attempts made before giving up.
        last_error: The final underlying exception.
    """

    def __init__(
        self,
        detail: str,
        attempts: int,
        last_error: LLMBaseException | None = None,
        provider: str = "unknown",
        model: str = "unknown",
    ) -> None:
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(detail=detail, provider=provider, model=model)


class LLMProviderNotConfiguredError(LLMBaseException):
    """A required provider configuration value is missing.

    Raised during ``init_llm_client()`` when the API key is empty or the
    requested provider name is unknown.  This is a startup-time failure —
    the process should not continue without a valid LLM configuration.
    """
