"""
LLM client — the single entry point for all LLM interactions.

``LLMClient`` is a thin facade over the active ``BaseLLMProvider``.  It adds:
- **Retry logic** via ``execute_with_retry`` around ``complete()`` calls.
- **Structured logging** of every completion (provider, model, token usage,
  duration).
- **A stable public API** so agents never import provider-specific code.

The module also manages the process-level singleton lifecycle:
- ``init_llm_client(settings)`` — called once in the FastAPI lifespan startup.
- ``get_llm_client()`` — called by services/agents to obtain the client.
- ``close_llm_client()`` — called in lifespan shutdown.

Provider selection
------------------
The active provider is determined by ``settings.llm_provider``:

    LLM_PROVIDER=groq      → GroqProvider  (default)
    LLM_PROVIDER=anthropic → AnthropicProvider

Adding a new provider requires only:
1. A new file in ``app/llm/providers/``.
2. A new branch in ``_create_provider()`` below.
3. Corresponding settings fields in ``app/config.py``.
"""

import logging
import time

from typing import Any, TypeVar

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.exceptions import ConfigurationError
from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from app.llm.exceptions import LLMProviderNotConfiguredError
from app.llm.retry import execute_with_retry

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)

# Process-level singleton — populated by init_llm_client().
_client: "LLMClient | None" = None

# Per-provider model cache for agent overrides (provider_name → BaseChatModel).
_agent_models: dict[str, "BaseChatModel"] = {}


def _create_provider(settings: Settings) -> BaseLLMProvider:
    """Instantiate the configured LLM provider.

    Uses a lazy import pattern so provider packages are only imported when that
    provider is actually selected.  This allows the other provider packages to
    be absent from the environment without causing import errors.

    Args:
        settings: Validated application settings.

    Returns:
        An initialised ``BaseLLMProvider`` instance.

    Raises:
        LLMProviderNotConfiguredError: If the API key for the selected provider
            is not set.
        ConfigurationError: If ``settings.llm_provider`` names an unknown provider.
    """
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        api_key = settings.anthropic_api_key.get_secret_value()
        if not api_key:
            raise LLMProviderNotConfiguredError(
                detail="ANTHROPIC_API_KEY is not set. Configure it before starting the application.",
                provider="anthropic",
            )
        from app.llm.providers.anthropic import AnthropicProvider  # noqa: PLC0415

        return AnthropicProvider(
            api_key=api_key,
            model=settings.anthropic_model,
            temperature=settings.anthropic_temperature,
        )

    if provider == "groq":
        api_key = settings.groq_api_key.get_secret_value()
        if not api_key:
            raise LLMProviderNotConfiguredError(
                detail="GROQ_API_KEY is not set. Get a free key at https://console.groq.com",
                provider="groq",
            )
        from app.llm.providers.groq import GroqProvider  # noqa: PLC0415

        return GroqProvider(
            api_key=api_key,
            model=settings.groq_model,
            temperature=settings.groq_temperature,
        )

    # ---- Future providers ----------------------------------------------------
    # if provider == "openai":
    #     from app.llm.providers.openai import OpenAIProvider
    #     return OpenAIProvider(...)
    # --------------------------------------------------------------------------

    raise ConfigurationError(
        f"Unknown LLM provider: {settings.llm_provider!r}. "
        f"Supported values: 'groq', 'anthropic'. "
        f"Set the LLM_PROVIDER environment variable to a supported provider."
    )


def _create_chat_model(provider: str, settings: Settings) -> "BaseChatModel":
    """Instantiate a raw LangChain BaseChatModel for *provider* using *settings*.

    Used by ``get_model_for_agent`` to build per-agent model instances when an
    agent's provider differs from the global ``llm_provider``.  The returned
    model is **not** wrapped in an ``LLMClient`` — agents use it directly via
    ``.with_structured_output()`` / ``.ainvoke()``.
    """
    if provider == "groq":
        from langchain_groq import ChatGroq  # noqa: PLC0415

        return ChatGroq(
            model=settings.groq_model,
            api_key=settings.groq_api_key.get_secret_value(),
            temperature=settings.groq_temperature,
            max_retries=0,
        )

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        return ChatAnthropic(
            model=settings.anthropic_model,
            api_key=settings.anthropic_api_key.get_secret_value(),
            temperature=settings.anthropic_temperature,
            max_retries=0,
        )

    raise ConfigurationError(
        f"Unknown LLM provider for agent override: {provider!r}. "
        "Supported values: 'groq', 'anthropic'."
    )


def get_model_for_agent(agent: str) -> "BaseChatModel":
    """Return the appropriate BaseChatModel for *agent*, respecting per-agent overrides.

    Checks ``settings.{agent}_llm_provider`` for an override.  If the override
    matches the global provider (or is empty), the main singleton client's model
    is returned — no extra connection is created.  Otherwise a cached per-provider
    model is created on first call and reused on subsequent calls.

    Args:
        agent: Agent name key — one of ``"research"``, ``"writer"``,
               ``"critic"``, ``"factchecker"``.

    Returns:
        A ``BaseChatModel`` instance ready for ``.with_structured_output()``
        and ``.ainvoke()`` calls.
    """
    settings = get_settings()
    override: str = getattr(settings, f"{agent}_llm_provider", "")
    provider = override or settings.llm_provider

    # Re-use the global client when the provider is the same — avoids a second
    # connection object and keeps logging/retry behaviour consistent.
    if provider == settings.llm_provider:
        return get_llm_client().get_model()

    # Cache by provider name so each provider gets exactly one model instance.
    if provider not in _agent_models:
        logger.info("Creating per-agent LLM model.", extra={"agent": agent, "provider": provider})
        _agent_models[provider] = _create_chat_model(provider, settings)

    return _agent_models[provider]


def init_llm_client(settings: Settings) -> None:
    """Create and cache the ``LLMClient`` singleton.

    Should be called once during application startup inside the FastAPI
    ``lifespan`` context manager.  Raises ``RuntimeError`` on double-init.

    Args:
        settings: Validated application settings.

    Raises:
        RuntimeError: If the client is already initialised.
        LLMProviderNotConfiguredError: If the required API key is missing.
        ConfigurationError: If the provider name is unknown.
    """
    global _client

    if _client is not None:
        raise RuntimeError("LLM client is already initialised.")

    provider = _create_provider(settings)
    _client = LLMClient(provider)

    logger.info(
        "LLM client initialised.",
        extra={
            "provider": provider.provider_name,
            "model": provider.model_name,
        },
    )


def get_llm_client() -> "LLMClient":
    """Return the cached ``LLMClient`` singleton.

    Returns:
        The active ``LLMClient`` instance.

    Raises:
        RuntimeError: If ``init_llm_client`` has not been called.
    """
    if _client is None:
        raise RuntimeError(
            "LLM client is not initialised. "
            "Ensure init_llm_client() is called during application startup."
        )
    return _client


def close_llm_client() -> None:
    """Release the LLM client singleton.

    Called during application shutdown.  Safe to call even if the client was
    never initialised (no-op in that case).
    """
    global _client

    if _client is not None:
        _client = None
        logger.info("LLM client closed.")


class LLMClient:
    """Facade over an ``BaseLLMProvider`` instance.

    Agents and services interact exclusively with this class — they never
    import or reference provider-specific code.

    Responsibilities:
    - Delegates ``get_model()`` directly to the provider (no retry needed —
      ``get_model()`` is synchronous and makes no network calls).
    - Wraps ``complete()`` with ``execute_with_retry`` for resilience.
    - Logs every completion with provider, model, duration, and token usage.

    Args:
        provider: The active ``BaseLLMProvider`` implementation.
    """

    def __init__(self, provider: BaseLLMProvider) -> None:
        self._provider = provider

    @property
    def provider_name(self) -> str:
        """The name of the active LLM provider (e.g. ``"gemini"``).

        Returns:
            Provider identifier string.
        """
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        """The model identifier currently in use (e.g. ``"gemini-2.5-flash"``).

        Returns:
            Model name string.
        """
        return self._provider.model_name

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        schema: type[T],
        system_prompt: str | None = None,
        max_retries: int = 3,
    ) -> T:
        """Send messages and parse the response into a Pydantic model.

        Calls ``.with_structured_output(schema)`` on the underlying model so the
        LLM returns JSON that is validated and coerced into ``schema``.  Wrapped
        with the same retry logic as ``complete()``.

        Args:
            messages: Ordered conversation messages.
            schema: A Pydantic ``BaseModel`` subclass that defines the expected
                output shape.
            system_prompt: Optional system instruction prepended before messages.
            max_retries: Maximum total attempts.

        Returns:
            A validated instance of ``schema``.

        Raises:
            LLMRetryExhaustedError: All retryable attempts failed.
        """
        start = time.monotonic()

        lc_messages: list[Any] = []
        if system_prompt:
            from langchain_core.messages import SystemMessage  # noqa: PLC0415

            lc_messages.append(SystemMessage(content=system_prompt))
        from langchain_core.messages import HumanMessage  # noqa: PLC0415

        for msg in messages:
            if msg.role == "human":
                lc_messages.append(HumanMessage(content=msg.content))
            else:
                from langchain_core.messages import AIMessage  # noqa: PLC0415

                lc_messages.append(AIMessage(content=msg.content))

        structured_model = self._provider.get_model().with_structured_output(schema)

        result: T = await execute_with_retry(
            lambda: structured_model.ainvoke(lc_messages),
            max_attempts=max_retries,
        )

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        logger.debug(
            "LLM structured completion succeeded.",
            extra={
                "provider": self._provider.provider_name,
                "schema": schema.__name__,
                "duration_ms": duration_ms,
            },
        )

        return result

    def get_model(self) -> BaseChatModel:
        """Return the raw LangChain ``BaseChatModel`` for use in LangGraph nodes.

        Use this method when an agent needs to call ``.with_structured_output()``,
        ``.bind_tools()``, or ``.astream()`` directly.

        Returns:
            A ``BaseChatModel`` instance bound to the configured model and key.

        Example::

            model = llm_client.get_model()
            structured = model.with_structured_output(ResearchOutput)
            result = await structured.ainvoke(messages)
        """
        return self._provider.get_model()

    async def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
        max_retries: int = 3,
    ) -> LLMResponse:
        """Send messages and return a completion, with automatic retry.

        Wraps the provider's ``complete()`` method with exponential backoff
        retry.  Retryable errors (rate limits, server errors, timeouts) are
        retried up to ``max_retries`` times.  Non-retryable errors
        (auth failures, bad requests) propagate immediately.

        Token usage and duration are logged at DEBUG level after each
        successful call.

        Args:
            messages: Ordered list of conversation messages.
            system_prompt: Optional system instruction prepended before the
                first message.  Useful for one-shot completions where the
                full system prompt is passed here rather than in ``messages``.
            max_retries: Maximum total attempts (1 = no retry).  Defaults to
                3 to match the behaviour configured in settings.

        Returns:
            ``LLMResponse`` with the generated text and optional token usage.

        Raises:
            LLMAuthError: API key is invalid — raised immediately, no retry.
            LLMBadRequestError: Prompt violated content policy or is malformed.
            LLMRetryExhaustedError: All retryable attempts failed.

        Example::

            from app.llm.base import LLMMessage

            response = await llm_client.complete(
                messages=[LLMMessage(role="human", content="Summarise quantum computing.")],
                system_prompt="You are a research assistant. Be concise and accurate.",
            )
            print(response.content)
        """
        start = time.monotonic()

        response = await execute_with_retry(
            lambda: self._provider.complete(messages, system_prompt=system_prompt),
            max_attempts=max_retries,
        )

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        logger.debug(
            "LLM completion succeeded.",
            extra={
                "provider": self._provider.provider_name,
                "model": self._provider.model_name,
                "duration_ms": duration_ms,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "total_tokens": response.total_tokens,
            },
        )

        return response
