"""
FactChecker Agent — LangGraph graph compilation and public class.

Graph topology
--------------

    START
      │
      ▼
    verify_search  ──── (status == "failed") ────→ END
      │
      ▼
    assess  ──── (status == "failed") ───────────→ END
      │
      ▼
     END
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.agents.factchecker.nodes import assess_node, verify_search_node
from app.agents.factchecker.schemas import (
    FactCheckerAgentState,
    FactCheckerOutput,
    VerifiedFinding,
)
from app.core.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    graph = StateGraph(FactCheckerAgentState)

    graph.add_node("verify_search", verify_search_node)
    graph.add_node("assess", assess_node)

    graph.add_edge(START, "verify_search")

    graph.add_conditional_edges(
        "verify_search",
        _route_on_status,
        {"assess": "assess", END: END},
    )

    graph.add_edge("assess", END)

    return graph


def _route_on_status(state: FactCheckerAgentState) -> str:
    if state.get("status") == "failed":
        return END
    return "assess"


class FactCheckerAgent(BaseAgent):
    """Validates research findings against web sources.

    Takes findings from ResearchAgent and annotates each one with:
    - ``verified``: whether the claim is supported by sources
    - ``confidence``: 0–1 confidence in the finding
    - ``verification_note``: brief explanation

    Stateless — compile once, call run() many times.
    """

    def __init__(self) -> None:
        self._graph = _build_graph().compile()

    @property
    def name(self) -> str:
        return "FactCheckerAgent"

    async def run(
        self,
        query: str,
        session_id: str,
        *,
        findings: list[dict[str, Any]],
        **kwargs: Any,
    ) -> FactCheckerOutput:
        """Verify findings and return annotated results.

        Args:
            query: The original research question.
            session_id: Research session UUID.
            findings: Serialised Finding dicts from ResearchAgent.

        Returns:
            ``FactCheckerOutput`` with all findings annotated.

        Raises:
            AgentExecutionError: If the graph exits with status="failed".
        """
        logger.info(
            "FactCheckerAgent: starting.",
            extra={
                "session_id": session_id,
                "num_findings": len(findings),
            },
        )

        initial_state: FactCheckerAgentState = {
            "query": query,
            "session_id": session_id,
            "findings": findings,
            "verification_context": [],
            "verified_findings": [],
            "status": "searching",
            "error": None,
        }

        final_state: FactCheckerAgentState = await self._graph.ainvoke(initial_state)

        if final_state.get("status") == "failed":
            error_msg = final_state.get("error") or "Unknown FactChecker failure."
            logger.error(
                "FactCheckerAgent: graph exited with failure.",
                extra={"session_id": session_id, "error": error_msg},
            )
            raise AgentExecutionError(detail=f"FactCheckerAgent failed: {error_msg}")

        verified_dicts = final_state.get("verified_findings", [])

        # If LLM returned nothing (edge case), fall back to treating all findings
        # as verified with neutral confidence.
        if not verified_dicts and findings:
            logger.warning(
                "FactCheckerAgent: no verified findings returned; using originals.",
                extra={"session_id": session_id},
            )
            verified_dicts = [
                {**f, "verified": True, "confidence": 0.5, "verification_note": "Unverified (fallback)."}
                for f in findings
            ]

        total = len(verified_dicts)
        verified_count = sum(1 for f in verified_dicts if f.get("verified", True))
        uncertain = sum(
            1 for f in verified_dicts
            if f.get("verified", True) and float(f.get("confidence", 1.0)) < 0.65
        )
        disputed = total - verified_count

        logger.info(
            "FactCheckerAgent: complete.",
            extra={
                "session_id": session_id,
                "total": total,
                "verified": verified_count,
                "disputed": disputed,
            },
        )

        return FactCheckerOutput(
            verified_findings=[VerifiedFinding.model_validate(d) for d in verified_dicts],
            total_input=len(findings),
            total_verified=verified_count,
            total_uncertain=uncertain,
            total_disputed=disputed,
        )
