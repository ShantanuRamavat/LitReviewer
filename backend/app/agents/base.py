"""
Abstract base class for all agents.

Every agent in the system exposes a common async ``run()`` interface so the
outer orchestration graph can call any agent without knowing its internals.

Agents are stateless classes — they hold a compiled LangGraph graph and
configuration but no per-request mutable state.  All per-request data lives
inside the ``TypedDict`` state object passed to ``graph.ainvoke()``.
"""

import asyncio
import re
from abc import ABC, abstractmethod
from typing import Any


def _parse_retry_wait(err: str) -> float:
    """Parse the retry delay from a Groq rate-limit error message.

    Handles three formats:
      "try again in 45.2s"       → 46.2 seconds
      "try again in 2m30.5s"     → 151.5 seconds
      "try again in 40m45.984s"  → 2446.984 seconds
    Returns 30.0 if no match is found.
    """
    # "Nm Ks" format (minutes + seconds)
    m = re.search(r"try again in (\d+)m(\d+\.?\d*)s", err)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2)) + 1.0
    # "Ks" format (seconds only)
    m = re.search(r"try again in (\d+\.?\d*)s", err)
    if m:
        return float(m.group(1)) + 1.0
    return 30.0


async def ainvoke_with_retry(model: Any, messages: Any, *, max_attempts: int = 6) -> Any:
    """Wrap model.ainvoke() with retry/backoff for provider rate-limit errors (429).

    Distinguishes between:
    - TPM (tokens per minute): short wait, retried up to max_attempts times.
    - TPD (tokens per day): daily quota exhausted — raises immediately with a
      clear message rather than looping uselessly for hours.
    """
    for attempt in range(max_attempts):
        try:
            return await model.ainvoke(messages)
        except Exception as exc:
            err = str(exc)
            is_rate_limit = "rate_limit_exceeded" in err or "RESOURCE_EXHAUSTED" in err
            if not is_rate_limit or attempt == max_attempts - 1:
                raise

            # Daily quota exhausted — retrying is pointless; surface a clear error.
            if "tokens per day" in err or "per day" in err.lower():
                wait_secs = _parse_retry_wait(err)
                wait_mins = int(wait_secs // 60)
                raise RuntimeError(
                    f"Groq free-tier daily token limit reached (100k tokens/day). "
                    f"Resets in ~{wait_mins} minutes. "
                    f"Upgrade at https://console.groq.com/settings/billing or try again tomorrow."
                ) from exc

            # TPM (per-minute) limit — wait the exact time Groq specifies and retry.
            wait = _parse_retry_wait(err)
            import logging
            logging.getLogger(__name__).warning(
                "Rate limit hit (TPM). Retrying in %.1fs (attempt %d/%d).", wait, attempt + 1, max_attempts
            )
            await asyncio.sleep(wait)
    raise RuntimeError("unreachable")  # pragma: no cover


class BaseAgent(ABC):
    """Minimal interface shared by all LangGraph agents.

    Subclasses compile a LangGraph graph in ``__init__`` and delegate
    ``run()`` to ``graph.ainvoke()``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent identifier used in logs and SSE events."""

    @abstractmethod
    async def run(self, query: str, session_id: str, **kwargs: Any) -> Any:
        """Execute the agent and return its structured output.

        Args:
            query: The research question or input for this agent.
            session_id: Research session identifier for scoping DB / Qdrant operations.
            **kwargs: Agent-specific parameters (e.g. ``iteration`` for ResearchAgent).

        Returns:
            Agent-specific output dataclass or Pydantic model.

        Raises:
            AgentExecutionError: If the agent fails in a way that cannot be recovered.
        """
