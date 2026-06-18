"""
Anthropic Claude provider implementation.

Uses ``langchain-anthropic`` (``ChatAnthropic``) as the underlying SDK so the
returned model is a first-class LangChain ``BaseChatModel``.  This makes it
directly usable in LangGraph nodes via ``.with_structured_output()``,
``.bind_tools()``, and ``.ainvoke()``.

Exception mapping
-----------------
``AnthropicProvider.complete()`` catches Anthropic SDK and network exceptions
and re-raises them as the appropriate type from ``app.llm.exceptions``:

    anthropic.APITimeoutError           → LLMTimeoutError
    anthropic.RateLimitError            → LLMRateLimitError
    anthropic.AuthenticationError       → LLMAuthError
    anthropic.PermissionDeniedError     → LLMAuthError
    anthropic.BadRequestError           → LLMBadRequestError
    anthropic.APIStatusError            → LLMServerError  (catch-all)
    httpx.TimeoutException              → LLMTimeoutError
    httpx.ConnectError                  → LLMServerError

The provider never retries.  Retry logic lives entirely in ``LLMClient``.
"""

import logging

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from app.llm.exceptions import (
    LLMAuthError,
    LLMBadRequestError,
    LLMRateLimitError,
    LLMServerError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "anthropic"


class AnthropicProvider(BaseLLMProvider):
    """LLM provider backed by Anthropic Claude via ``langchain-anthropic``.

    Instantiates a single ``ChatAnthropic`` object and reuses it across all
    calls.  ``ChatAnthropic`` is stateless and async-safe.

    Args:
        api_key: Anthropic API key.
        model: Claude model identifier (e.g. ``"claude-sonnet-4-6"``).
        temperature: Sampling temperature in [0.0, 1.0].  Lower values produce
            more deterministic output.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
    ) -> None:
        from langchain_anthropic import ChatAnthropic  # noqa: PLC0415

        self._model_name = model

        self._llm = ChatAnthropic(
            model=model,
            api_key=api_key,  # type: ignore[arg-type]
            temperature=temperature,
            # Disable LangChain's own retry so our tenacity wrapper is the sole
            # retry mechanism.  Stacking two retry loops breaks backoff math.
            max_retries=0,
        )

        logger.info(
            "AnthropicProvider initialised.",
            extra={"model": model},
        )

    # -------------------------------------------------------------------------
    # BaseLLMProvider interface
    # -------------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_model(self) -> BaseChatModel:
        """Return the underlying ``ChatAnthropic`` instance."""
        return self._llm

    async def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        """Send messages to Anthropic and return the completion."""
        import anthropic as anthropic_sdk  # noqa: PLC0415

        lc_messages = self._build_langchain_messages(messages, system_prompt)

        try:
            response: AIMessage = await self._llm.ainvoke(lc_messages)
        except anthropic_sdk.APITimeoutError as exc:
            raise LLMTimeoutError(
                detail=f"Anthropic request timed out: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except anthropic_sdk.RateLimitError as exc:
            raise LLMRateLimitError(
                detail=f"Anthropic rate limit exceeded: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except (anthropic_sdk.AuthenticationError, anthropic_sdk.PermissionDeniedError) as exc:
            raise LLMAuthError(
                detail=f"Anthropic authentication failed: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except anthropic_sdk.BadRequestError as exc:
            raise LLMBadRequestError(
                detail=f"Anthropic bad request: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except anthropic_sdk.APIStatusError as exc:
            raise LLMServerError(
                detail=f"Anthropic API error: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                detail=f"Network timeout connecting to Anthropic API: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMServerError(
                detail=f"Could not connect to Anthropic API: {exc}",
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
                result.append(SystemMessage(content=msg.content))
            else:
                logger.warning(
                    "Unknown LLMMessage role; treating as human.",
                    extra={"role": role},
                )
                result.append(HumanMessage(content=msg.content))

        return result

    def _build_response(self, response: AIMessage) -> LLMResponse:
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
        return f"AnthropicProvider(model={self._model_name!r})"
