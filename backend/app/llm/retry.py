"""
Retry logic for LLM API calls using tenacity.

Provides ``execute_with_retry`` — a single entry point that wraps any async
callable with exponential backoff and jitter.  It is called exclusively by
``LLMClient.complete()``; providers never retry internally.

Retry policy
------------
+-----------------------+----------+-----------------------------------------+
| Exception             | Retried? | Reason                                  |
+-----------------------+----------+-----------------------------------------+
| LLMRateLimitError     | Yes      | Back-pressure from API; resolve quickly |
| LLMServerError        | Yes      | Transient upstream error                |
| LLMTimeoutError       | Yes      | Network hiccup                          |
| LLMAuthError          | No       | Wrong API key; retrying never helps     |
| LLMBadRequestError    | No       | Bad prompt; same result every time      |
| LLMRetryExhaustedError| N/A      | Already terminal — raised by this module|
+-----------------------+----------+-----------------------------------------+

Backoff
-------
- Initial wait : 1 second
- Multiplier   : exponential (×2 each attempt)
- Maximum wait : 30 seconds
- Jitter       : ±2 seconds (prevents thundering herd when many sessions retry)
- Max attempts : configurable, default 3

Logging
-------
Each sleep between attempts is logged at WARNING with:
- ``attempt``      : current attempt number (1-indexed)
- ``wait_seconds`` : how long tenacity will sleep before the next attempt
- ``exc_type``     : the class name of the exception that triggered the retry
- ``exc_message``  : a short description of the error
"""

import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.llm.exceptions import (
    LLMBaseException,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMServerError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_retryable(exc: BaseException) -> bool:
    """Return True only for exceptions that may resolve on a subsequent attempt.

    Args:
        exc: The exception raised by the LLM provider.

    Returns:
        True if the exception is ``LLMRateLimitError``, ``LLMServerError``,
        or ``LLMTimeoutError``.  False for all other exception types.
    """
    return isinstance(exc, (LLMRateLimitError, LLMServerError, LLMTimeoutError))


def _before_sleep_log(retry_state: RetryCallState) -> None:
    """Log a warning before each retry sleep.

    Called by tenacity immediately before sleeping between attempts.

    Args:
        retry_state: Tenacity state object for the current retry attempt.
    """
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    wait = getattr(retry_state.next_action, "sleep", 0.0)

    logger.warning(
        "LLM call failed — retrying",
        extra={
            "attempt": retry_state.attempt_number,
            "wait_seconds": round(wait, 2),
            "exc_type": type(exc).__name__ if exc else "unknown",
            "exc_message": str(exc) if exc else "",
        },
    )


async def execute_with_retry(
    coro_factory: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 3,
) -> T:
    """Execute an async coroutine factory with exponential backoff retry.

    The ``coro_factory`` pattern (a zero-argument callable that returns a
    coroutine) is used instead of passing ``func, *args, **kwargs`` to avoid
    any ambiguity between arguments intended for the retry wrapper and
    arguments intended for the underlying function.

    Usage::

        response = await execute_with_retry(
            lambda: provider.complete(messages, system_prompt=prompt),
            max_attempts=3,
        )

    Args:
        coro_factory: A callable ``() -> Awaitable[T]`` that creates a fresh
            coroutine on each call.  Must be a new coroutine each time —
            a spent coroutine cannot be awaited again.
        max_attempts: Maximum total attempts (1 = no retry, 3 = try 3 times).

    Returns:
        The result of the first successful coroutine execution.

    Raises:
        LLMAuthError: API key is invalid — not retried, raised immediately.
        LLMBadRequestError: Bad prompt — not retried, raised immediately.
        LLMRetryExhaustedError: All ``max_attempts`` retryable attempts failed.
            The ``last_error`` attribute holds the final underlying exception.
    """
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(_is_retryable),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            # reraise=False: on exhaustion tenacity raises RetryError (caught below).
            # Non-retryable exceptions bypass tenacity and propagate immediately.
            reraise=False,
            before_sleep=_before_sleep_log,
        ):
            with attempt:
                return await coro_factory()

    except RetryError as retry_err:
        # All retryable attempts exhausted.  Unwrap the last underlying error
        # and re-raise as LLMRetryExhaustedError so callers see a consistent type.
        last_exc = retry_err.last_attempt.exception()

        if isinstance(last_exc, LLMBaseException):
            provider = last_exc.provider
            model = last_exc.model
        else:
            provider = model = "unknown"

        raise LLMRetryExhaustedError(
            detail=(
                f"All {max_attempts} attempt(s) failed. "
                f"Last error: {type(last_exc).__name__}: {last_exc}"
            ),
            attempts=max_attempts,
            last_error=last_exc if isinstance(last_exc, LLMBaseException) else None,
            provider=provider,
            model=model,
        ) from last_exc

    # This line is unreachable — tenacity's loop always either returns or raises.
    # It exists only to satisfy the type checker's exhaustiveness analysis.
    raise RuntimeError("execute_with_retry exited without returning or raising")  # pragma: no cover
