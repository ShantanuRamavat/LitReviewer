"""LangGraph node functions for the Critic Agent.

Single node:
    critique_node — pure LLM reasoning, no external tools.

Hard-fail: any unhandled exception sets status="failed".
"""

from __future__ import annotations

import logging
from typing import Any

from app.agents.base import ainvoke_with_retry
from app.agents.critic.prompts import CRITIC_SYSTEM_PROMPT
from app.agents.critic.schemas import CriticAgentState, CritiqueOutput
from app.llm import get_model_for_agent

logger = logging.getLogger(__name__)


async def critique_node(state: CriticAgentState) -> dict[str, Any]:
    """Assess research quality and decide whether to loop or proceed to writing.

    Passes all verified findings + iteration context to the LLM.  The model
    scores quality and coverage and returns a ``CritiqueOutput`` with
    ``is_sufficient`` to control the outer loop.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with ``critique`` and ``status``.
    """
    findings = state["verified_findings"]
    iteration = state.get("iteration", 0)

    logger.info(
        "CriticAgent: critiquing.",
        extra={
            "session_id": state["session_id"],
            "findings": len(findings),
            "iteration": iteration,
        },
    )

    if not findings:
        logger.warning(
            "CriticAgent: no findings to critique; marking insufficient.",
            extra={"session_id": state["session_id"]},
        )
        return {
            "critique": CritiqueOutput(
                quality_score=0.0,
                coverage_score=0.0,
                gaps=["No research findings were produced."],
                strengths=[],
                is_sufficient=iteration >= 2,
                suggestions=["Retry the original research query"] if iteration < 2 else [],
            ),
            "status": "complete",
        }

    findings_text = _format_findings_for_prompt(findings)

    try:
        model = get_model_for_agent("critic").with_structured_output(CritiqueOutput)

        critique: CritiqueOutput = await ainvoke_with_retry(
            model,
            [
                {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
                {
                    "role": "human",
                    "content": (
                        f"Research query: {state['query']}\n"
                        f"Iteration: {iteration}\n\n"
                        f"Fact-checked findings:\n{findings_text}"
                    ),
                },
            ],
        )

        logger.info(
            "CriticAgent: critique complete.",
            extra={
                "session_id": state["session_id"],
                "quality_score": critique.quality_score,
                "coverage_score": critique.coverage_score,
                "is_sufficient": critique.is_sufficient,
                "gaps": len(critique.gaps),
            },
        )

        return {
            "critique": critique,
            "status": "complete",
        }

    except Exception as exc:
        logger.error(
            "CriticAgent: critique failed: %s",
            exc,
            exc_info=True,
            extra={"session_id": state["session_id"]},
        )
        return {
            "status": "failed",
            "error": f"Critique failed: {exc}",
        }


def _format_findings_for_prompt(findings: list[dict]) -> str:
    lines: list[str] = []
    for i, f in enumerate(findings, start=1):
        verified = f.get("verified", True)
        confidence = f.get("confidence", 0.7)
        relevance = f.get("relevance_score", 0.0)
        note = f.get("verification_note", "")
        text = str(f.get("text", ""))[:300]
        status = "✓" if verified else "✗"
        lines.append(
            f"[{i}] {status} confidence={confidence:.2f} relevance={relevance:.2f}\n"
            f"  {text}\n"
            f"  Note: {note}"
        )
    return "\n\n".join(lines)
