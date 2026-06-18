"""
Google Gemini provider implementation.

Uses ``langchain-google-genai`` (``ChatGoogleGenerativeAI``) as the underlying
SDK so the returned model is a first-class LangChain ``BaseChatModel``.  This
makes it directly usable in LangGraph nodes via ``.with_structured_output()``,
``.bind_tools()``, and ``.ainvoke()``.

Exception mapping
-----------------
``GeminiProvider.complete()`` catches every Google-SDK and network exception
and re-raises it as the appropriate type from ``app.llm.exceptions``:

    google.api_core.exceptions.DeadlineExceeded     → LLMTimeoutError
    google.api_core.exceptions.ResourceExhausted    → LLMRateLimitError
    google.api_core.exceptions.Unauthenticated      → LLMAuthError
    google.api_core.exceptions.PermissionDenied     → LLMAuthError
    google.api_core.exceptions.InvalidArgument      → LLMBadRequestError
    google.api_core.exceptions.GoogleAPICallError   → LLMServerError  (catch-all)
    httpx.TimeoutException                          → LLMTimeoutError
    httpx.ConnectError                              → LLMServerError

The provider never retries.  Retry logic lives entirely in ``LLMClient``.

Model configuration
-------------------
``ChatGoogleGenerativeAI`` is initialised with:
- ``convert_system_message_to_human=False`` — Gemini 1.5+ natively supports
  system messages via the ``system_instruction`` parameter; no conversion needed.
- ``max_retries=0`` — disables LangChain's built-in retry so our tenacity-based
  retry in ``LLMClient`` is the sole retry mechanism.  Double-retry would break
  the backoff math.
"""

import logging

import httpx
from google.api_core import exceptions as google_exceptions
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from app.llm.exceptions import (
    LLMAuthError,
    LLMBadRequestError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "gemini"


class GeminiProvider(BaseLLMProvider):
    """LLM provider backed by Google Gemini via ``langchain-google-genai``.

    Instantiates a single ``ChatGoogleGenerativeAI`` object and reuses it
    across all calls.  ``ChatGoogleGenerativeAI`` is stateless and async-safe.

    Args:
        api_key: Google AI Studio or Vertex AI API key.
        model: Gemini model identifier (e.g. ``"gemini-2.5-flash"``).
        temperature: Sampling temperature in [0.0, 2.0].  Lower values produce
            more deterministic output, which is preferable for structured agent
            outputs.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
    ) -> None:
        self._model_name = model
        self._api_key = api_key  # stored for repr only; never logged

        self._llm = ChatGoogleGenerativeAI(
            model=model,
            google_api_key=api_key,
            temperature=temperature,
            # Disable LangChain's own retry so our tenacity wrapper is the only
            # retry mechanism.  Stacking two retry loops produces unpredictable
            # wait times and exhausts quota faster.
            max_retries=0,
            # Gemini 1.5+ supports system messages natively.  Setting this to
            # False prevents the LangChain wrapper from converting them to human
            # messages, which would lose the system-message semantics.
            convert_system_message_to_human=False,
        )

        logger.info(
            "GeminiProvider initialised.",
            extra={"model": model},
        )

    # -------------------------------------------------------------------------
    # BaseLLMProvider interface
    # -------------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the provider identifier string."""
        return _PROVIDER_NAME

    @property
    def model_name(self) -> str:
        """Return the configured Gemini model name."""
        return self._model_name

    def get_model(self) -> BaseChatModel:
        """Return the underlying ``ChatGoogleGenerativeAI`` instance.

        The returned model is a LangChain ``BaseChatModel`` — callers can use
        ``.with_structured_output()``, ``.bind_tools()``, ``.ainvoke()``, and
        ``.astream()`` directly.

        Returns:
            The shared ``ChatGoogleGenerativeAI`` instance.
        """
        return self._llm

    async def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send messages to Gemini and return the completion.

        Converts ``LLMMessage`` objects to LangChain message types, calls
        ``ChatGoogleGenerativeAI.ainvoke()``, extracts the response content and
        token usage, then maps any SDK exception to our exception hierarchy.

        Args:
            messages: Ordered list of ``LLMMessage`` objects.
            system_prompt: If provided, prepended as a ``SystemMessage`` before
                the first human message.

        Returns:
            ``LLMResponse`` containing generated text, model name, and token
            usage (if reported by the Gemini API).

        Raises:
            LLMTimeoutError: Request timed out at the network level.
            LLMRateLimitError: Gemini API rate limit exceeded (HTTP 429).
            LLMAuthError: API key is invalid or lacks required permissions.
            LLMBadRequestError: Prompt is malformed or violates content policy.
            LLMServerError: Unexpected Gemini API server error (HTTP 5xx).
        """
        lc_messages = self._build_langchain_messages(messages, system_prompt)

        try:
            response: AIMessage = await self._llm.ainvoke(lc_messages)
        except google_exceptions.DeadlineExceeded as exc:
            raise LLMTimeoutError(
                detail=f"Gemini request timed out: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except google_exceptions.ResourceExhausted as exc:
            raise LLMRateLimitError(
                detail=f"Gemini rate limit exceeded: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except (google_exceptions.Unauthenticated, google_exceptions.PermissionDenied) as exc:
            raise LLMAuthError(
                detail=f"Gemini authentication failed: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except google_exceptions.InvalidArgument as exc:
            raise LLMBadRequestError(
                detail=f"Gemini bad request — check the prompt for policy violations: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except google_exceptions.GoogleAPICallError as exc:
            # Catches InternalServerError (500), ServiceUnavailable (503),
            # and any other Google API error not matched above.
            raise LLMServerError(
                detail=f"Gemini API error: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                detail=f"Network timeout connecting to Gemini API: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMServerError(
                detail=f"Could not connect to Gemini API: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc

        return self._build_response(response)

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _build_langchain_messages(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None,
    ) -> list[BaseMessage]:
        """Convert ``LLMMessage`` list to LangChain message objects.

        If ``system_prompt`` is provided it is prepended as a ``SystemMessage``
        regardless of whether a system message already exists in ``messages``.
        This means callers should not include a system message in ``messages``
        when also passing ``system_prompt`` — doing so would result in two
        system messages.

        Args:
            messages: List of ``LLMMessage`` objects to convert.
            system_prompt: Optional system-level instruction to prepend.

        Returns:
            List of LangChain ``BaseMessage`` subclass instances.
        """
        result: list[BaseMessage] = []

        if system_prompt:
            result.append(SystemMessage(content=system_prompt))

        for msg in messages:
            role = msg.role.lower()
            if role == "human":
                result.append(HumanMessage(content=msg.content))
            elif role in ("ai", "assistant"):
                result.append(AIMessage(content=msg.content))
            elif role == "system":
                # Support system messages embedded in the messages list.
                # They are placed in order, not hoisted to the front.
                result.append(SystemMessage(content=msg.content))
            else:
                logger.warning(
                    "Unknown LLMMessage role; treating as human.",
                    extra={"role": role},
                )
                result.append(HumanMessage(content=msg.content))

        return result

    def _build_response(self, response: AIMessage) -> LLMResponse:
        """Extract text content and token usage from a LangChain ``AIMessage``.

        ``usage_metadata`` is a ``UsageMetadata`` TypedDict attached to
        ``AIMessage`` by LangChain Core >= 0.2.  It may be ``None`` if the
        provider did not return usage information.

        Args:
            response: The ``AIMessage`` returned by ``ChatGoogleGenerativeAI``.

        Returns:
            An ``LLMResponse`` with extracted content and token counts.
        """
        content = response.content if isinstance(response.content, str) else str(response.content)

        usage = getattr(response, "usage_metadata", None)

        return LLMResponse(
            content=content,
            model=self._model_name,
            input_tokens=usage.get("input_tokens") if usage else None,
            output_tokens=usage.get("output_tokens") if usage else None,
            total_tokens=usage.get("total_tokens") if usage else None,
        )

    def __repr__(self) -> str:
        """Return a safe string representation that does not expose the API key."""
        return f"GeminiProvider(model={self._model_name!r})"
