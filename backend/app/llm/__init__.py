"""
LLM provider abstraction layer.

Public API — import everything agents and services need from here::

    from app.llm import LLMClient, LLMMessage, LLMResponse, get_llm_client

The ``app.llm.providers`` subpackage and ``BaseLLMProvider`` are internal
implementation details.  External code should never import them directly.

Quick reference
---------------

``get_llm_client()``
    Returns the process-level ``LLMClient`` singleton.  Raises ``RuntimeError``
    if called before ``init_llm_client()`` in the application lifespan.

``LLMClient.get_model()``
    Returns a LangChain ``BaseChatModel`` for use in LangGraph nodes.

``LLMClient.complete(messages, system_prompt, max_retries)``
    One-shot text completion with automatic retry.

``LLMMessage(role, content)``
    Input message type.  ``role`` must be ``"system"``, ``"human"``, or ``"ai"``.

``LLMResponse``
    Output type with ``.content``, ``.model``, and optional token counts.
"""

from app.llm.base import LLMMessage, LLMResponse
from app.llm.client import LLMClient, close_llm_client, get_llm_client, get_model_for_agent, init_llm_client
from app.llm.exceptions import (
    LLMAuthError,
    LLMBadRequestError,
    LLMBaseException,
    LLMProviderNotConfiguredError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMServerError,
    LLMTimeoutError,
)

__all__ = [
    # Core types
    "LLMMessage",
    "LLMResponse",
    # Client lifecycle
    "LLMClient",
    "init_llm_client",
    "get_llm_client",
    "get_model_for_agent",
    "close_llm_client",
    # Exceptions — exported so callers can catch specific failure modes
    "LLMBaseException",
    "LLMRateLimitError",
    "LLMAuthError",
    "LLMBadRequestError",
    "LLMServerError",
    "LLMTimeoutError",
    "LLMRetryExhaustedError",
    "LLMProviderNotConfiguredError",
]
