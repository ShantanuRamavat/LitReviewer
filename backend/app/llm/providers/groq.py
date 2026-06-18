"""
Groq provider implementation.

Uses ``langchain-groq`` (``ChatGroq``) as the underlying SDK.  Groq offers a
free tier with fast inference on open-source models (Llama 3.3, Gemma2, etc.).
Sign up at https://console.groq.com to get a free API key.

Exception mapping
-----------------
    groq.APITimeoutError            → LLMTimeoutError
    groq.RateLimitError             → LLMRateLimitError
    groq.AuthenticationError        → LLMAuthError
    groq.BadRequestError            → LLMBadRequestError
    groq.APIStatusError             → LLMServerError  (catch-all)
    httpx.TimeoutException          → LLMTimeoutError
    httpx.ConnectError              → LLMServerError
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

_PROVIDER_NAME = "groq"


class GroqProvider(BaseLLMProvider):
    """LLM provider backed by Groq via ``langchain-groq``.

    Args:
        api_key: Groq API key (from console.groq.com).
        model: Model identifier (e.g. ``"llama-3.3-70b-versatile"``).
        temperature: Sampling temperature in [0.0, 1.0].
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
    ) -> None:
        from langchain_groq import ChatGroq  # noqa: PLC0415

        self._model_name = model

        self._llm = ChatGroq(
            model=model,
            api_key=api_key,  # type: ignore[arg-type]
            temperature=temperature,
            max_retries=0,
        )

        logger.info(
            "GroqProvider initialised.",
            extra={"model": model},
        )

    @property
    def provider_name(self) -> str:
        return _PROVIDER_NAME

    @property
    def model_name(self) -> str:
        return self._model_name

    def get_model(self) -> BaseChatModel:
        return self._llm

    async def complete(
        self,
        messages: list[LLMMessage],
        system_prompt: str | None = None,
    ) -> LLMResponse:
        import groq as groq_sdk  # noqa: PLC0415

        lc_messages = self._build_langchain_messages(messages, system_prompt)

        try:
            response: AIMessage = await self._llm.ainvoke(lc_messages)
        except groq_sdk.APITimeoutError as exc:
            raise LLMTimeoutError(
                detail=f"Groq request timed out: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except groq_sdk.RateLimitError as exc:
            raise LLMRateLimitError(
                detail=f"Groq rate limit exceeded: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except groq_sdk.AuthenticationError as exc:
            raise LLMAuthError(
                detail=f"Groq authentication failed: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except groq_sdk.BadRequestError as exc:
            raise LLMBadRequestError(
                detail=f"Groq bad request: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except groq_sdk.APIStatusError as exc:
            raise LLMServerError(
                detail=f"Groq API error: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                detail=f"Network timeout connecting to Groq API: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc
        except httpx.ConnectError as exc:
            raise LLMServerError(
                detail=f"Could not connect to Groq API: {exc}",
                provider=_PROVIDER_NAME,
                model=self._model_name,
            ) from exc

        return self._build_response(response)

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
        return f"GroqProvider(model={self._model_name!r})"
