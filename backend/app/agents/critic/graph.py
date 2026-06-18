"""
Critic Agent — LangGraph graph compilation and public class.

Graph topology
--------------

    START
      │
      ▼
    critique  ──── (status == "failed") ──→ END
      │
      ▼
     END
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.agents.critic.nodes import critique_node
from app.agents.critic.schemas import CriticAgentState, CriticOutput, CritiqueOutput
from app.core.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    graph = StateGraph(CriticAgentState)
    graph.add_node("critique", critique_node)
    graph.add_edge(START, "critique")
    graph.add_edge("critique", END)
    return graph


class CriticAgent(BaseAgent):
    """Assesses research quality and decides if more research is needed.

    Pure LLM reasoning — no external tools.  Scores the verified findings on
    quality and coverage, then returns ``is_sufficient`` to control the loop.

    Stateless — compile once, call run() many times.
    """

    def __init__(self) -> None:
        self._graph = _build_graph().compile()

    @property
    def name(self) -> str:
        return "CriticAgent"

    async def run(
        self,
        query: str,
        session_id: str,
        *,
        verified_findings: list[dict[str, Any]],
        iteration: int = 0,
        **kwargs: Any,
    ) -> CriticOutput:
        """Critique the research and return a quality assessment.

        Args:
            query: The original research question.
            session_id: Research session UUID.
            verified_findings: Dicts from FactCheckerAgent.
            iteration: Current loop iteration (0-indexed).

        Returns:
            ``CriticOutput`` with quality scores and loop decision.

        Raises:
            AgentExecutionError: If the graph exits with status="failed".
        """
        logger.info(
            "CriticAgent: starting.",
            extra={
                "session_id": session_id,
                "num_findings": len(verified_findings),
                "iteration": iteration,
            },
        )

        initial_state: CriticAgentState = {
            "query": query,
            "session_id": session_id,
            "iteration": iteration,
            "verified_findings": verified_findings,
            "critique": None,
            "status": "critiquing",
            "error": None,
        }

        final_state: CriticAgentState = await self._graph.ainvoke(initial_state)

        if final_state.get("status") == "failed":
            error_msg = final_state.get("error") or "Unknown Critic failure."
            logger.error(
                "CriticAgent: graph exited with failure.",
                extra={"session_id": session_id, "error": error_msg},
            )
            raise AgentExecutionError(detail=f"CriticAgent failed: {error_msg}")

        critique: CritiqueOutput = final_state["critique"]

        logger.info(
            "CriticAgent: complete.",
            extra={
                "session_id": session_id,
                "quality_score": critique.quality_score,
                "is_sufficient": critique.is_sufficient,
            },
        )

        return CriticOutput(
            critique=critique,
            quality_score=critique.quality_score,
            is_sufficient=critique.is_sufficient,
            suggestions=critique.suggestions,
        )
