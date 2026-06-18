"""
Abstract base types for the LLM provider layer.

Defines the shared data contracts (``LLMMessage``, ``LLMResponse``) and the
``BaseLLMProvider`` abstract class that every provider must implement.

Design contract
---------------
- ``get_model()`` returns a LangChain ``BaseChatModel`` so LangGraph nodes can
  call ``.with_structured_output()``, ``.bind_tools()``, and ``.ainvoke()``
  directly.  This is the primary path used by agents.
- ``complete()`` is a convenience wrapper for one-off completions outside the
  LangGraph graph (e.g. a service-layer call that needs a simple string back).
  Retry logic lives in ``LLMClient``, not here — providers are responsible only
  for translating SDK exceptions into our exception hierarchy.

Adding a new provider
---------------------
1. Create ``app/llm/providers/{name}.py`` with a class that inherits
   ``BaseLLMProvider`` and implements all abstract methods.
2. Add a branch to ``app/llm/client._create_provider()`` for the new provider.
3. No other files need to change.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class LLMMessage:
    """A single message in a conversation turn.

    Attributes:
        role: The speaker — ``"system"``, ``"human"``, or ``"ai"``.
        content: The text content of the message.
    """

    role: str  # Literal["system", "human", "ai"] — kept as str for flexibility
    content: str


@dataclass
class LLMResponse:
    """The output of a single LLM completion call.

    Attributes:
        content: The generated text from the model.
        model: The model identifier that produced the response.
        input_tokens: Number of tokens in the prompt (if reported by the API).
        output_tokens: Number of tokens in the completion (if reported).
        total_tokens: Sum of input and output tokens (if reported).
    """

    content: str
    model: str
    input_tokens: int | None = field(default=None)
    output_tokens: int | None = field(default=None)
    total_tokens: int | None = field(default=None)

    @property
    def has_usage(self) -> bool:
        """Return True if token usage data was returned by the API."""
        return self.input_tokens is not None


class BaseLLMProvider(ABC):
    """Abstract interface that all LLM providers must implement.

    The two methods serve different call sites:
    - ``get_model()`` — used by LangGraph agent nodes that need a full
      LangChain ``BaseChatModel`` with tool-binding and structured-output
      support.
    - ``complete()`` — used by services that need a simple string completion
      without the LangGraph machinery.

    Providers are responsible for:
    - Constructing the underlying SDK client.
    - Mapping SDK-specific exceptions to the exception types defined in
      ``app.llm.exceptions``.
    - Converting between ``LLMMessage`` and the SDK's native message types.

    Providers are NOT responsible for:
    - Retry logic (handled by ``LLMClient``).
    - Logging retry attempts (handled by ``retry.py``).
    - Singleton lifecycle (handled by ``client.py``).
    """

    @abstractmethod
    def get_model(self):  # -> BaseChatModel
        """Return the underlying LangChain chat model.

        The returned object must be a ``langchain_core.language_models.BaseChatModel``
        instance.  Callers may call ``.with_structured_output()``,
        ``.bind_tools()``, ``.ainvoke()``, and ``.astream()`` on it.

        Returns:
            A ``BaseChatModel`` bound to the configured model and API key.
        """

    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send a list of messages and return a single completion.

        The provider must:
        - Prepend ``system_prompt`` as a system message if provided.
        - Map all SDK exceptions to the types in ``app.llm.exceptions``.
        - Never retry — retry is the caller's responsibility.

        Args:
            messages: Ordered list of conversation messages.
            system_prompt: Optional system-level instruction prepended before
                the first human message.

        Returns:
            ``LLMResponse`` containing the generated text and token usage.

        Raises:
            LLMRateLimitError: API rate limit exceeded (HTTP 429).
            LLMAuthError: Invalid or missing API key (HTTP 401/403).
            LLMBadRequestError: Malformed request (HTTP 400) — do not retry.
            LLMServerError: Upstream server error (HTTP 5xx).
            LLMTimeoutError: Network timeout.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier (e.g. ``"gemini"``).

        Used in log messages and health check responses.
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """The specific model being used (e.g. ``"gemini-2.5-flash"``).

        Used in log messages and stored in ``LLMResponse.model``.
        """
