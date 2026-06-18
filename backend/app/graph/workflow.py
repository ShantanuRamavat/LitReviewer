"""
ResearchWorkflow — the top-level LangGraph orchestration graph.

Wires all four agents into a single compiled graph with a quality-gate loop.

Graph structure
---------------

    START
      │
      ▼
    research  ─── (failed) ──────────────────────────────────→ END
      │
      ▼
    fact_check ── (failed) ──────────────────────────────────→ END
      │
      ▼
    critique  ─── (failed) ──────────────────────────────────→ END
      │
      ├── (loop: quality insufficient, iteration < max) ──────→ research  (increment iteration)
      │
      │── (continue: quality sufficient or max iterations hit)
      ▼
    write  ───── (failed) ───────────────────────────────────→ END
      │
      ▼
     END

The loop passes critique.suggestions back to ResearchAgent so it targets
identified research gaps on subsequent iterations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.critic.graph import CriticAgent
from app.agents.factchecker.graph import FactCheckerAgent
from app.agents.research.graph import ResearchAgent
from app.agents.writer.graph import WriterAgent
from app.agents.writer.schemas import Report, ReportCitation
from app.core.exceptions import AgentExecutionError
from app.graph.nodes import (
    make_critique_node,
    make_factcheck_node,
    make_research_node,
    make_write_node,
    route_after_critique,
    route_on_status,
)
from app.graph.state import ResearchWorkflowState, WorkflowOutput

logger = logging.getLogger(__name__)

_WORKFLOW_TIMEOUT_SECONDS = 1800  # 30 minutes — long-form sectional writing needs time


def _increment_iteration(state: ResearchWorkflowState) -> dict[str, Any]:
    """Increment the loop counter when routing back to research."""
    return {"iteration": state.get("iteration", 0) + 1}


def _build_graph(
    research_agent: ResearchAgent,
    factchecker_agent: FactCheckerAgent,
    critic_agent: CriticAgent,
    writer_agent: WriterAgent,
) -> StateGraph:
    graph = StateGraph(ResearchWorkflowState)

    # ---- Nodes ---------------------------------------------------------------
    graph.add_node("research", make_research_node(research_agent))
    graph.add_node("fact_check", make_factcheck_node(factchecker_agent))
    graph.add_node("critique", make_critique_node(critic_agent))
    graph.add_node("increment_iteration", _increment_iteration)
    graph.add_node("write", make_write_node(writer_agent))

    # ---- Entry ---------------------------------------------------------------
    graph.add_edge(START, "research")

    # ---- research → fact_check (or fail, or skip to write on loop fallback) --
    graph.add_conditional_edges(
        "research",
        route_on_status,
        {"continue": "fact_check", "skip_to_write": "write", "failed": END},
    )

    # ---- fact_check → critique (or fail) -------------------------------------
    graph.add_conditional_edges(
        "fact_check",
        route_on_status,
        {"continue": "critique", "failed": END},
    )

    # ---- critique → loop or write (or fail) ----------------------------------
    graph.add_conditional_edges(
        "critique",
        route_after_critique,
        {"continue": "write", "loop": "increment_iteration", "failed": END},
    )

    # ---- loop: increment then back to research --------------------------------
    graph.add_edge("increment_iteration", "research")

    # ---- write → END (complete or failed) ------------------------------------
    graph.add_conditional_edges(
        "write",
        route_on_status,
        {"continue": END, "failed": END},
    )

    return graph


class ResearchWorkflow:
    """End-to-end research pipeline: query → findings → verify → critique → report.

    Compiles and owns the LangGraph orchestration graph.  All four sub-agents
    are created internally and their subgraphs compiled at init time.

    The pipeline runs up to ``settings.max_iterations`` research loops.  On
    each loop the Critic's gap suggestions are fed back to the ResearchAgent to
    improve coverage.

    Example::

        workflow = ResearchWorkflow()
        output = await workflow.run(
            query="What are the latest advances in quantum error correction?",
            session_id="sess-abc-123",
        )
        print(output.report.title)
        print(f"Quality score: {output.quality_score:.2f}")
    """

    def __init__(self) -> None:
        self._research_agent = ResearchAgent()
        self._factchecker_agent = FactCheckerAgent()
        self._critic_agent = CriticAgent()
        self._writer_agent = WriterAgent()
        self._graph = _build_graph(
            self._research_agent,
            self._factchecker_agent,
            self._critic_agent,
            self._writer_agent,
        ).compile()
        logger.info("ResearchWorkflow: compiled and ready.")

    async def run(self, query: str, session_id: str, mode: str = "general") -> WorkflowOutput:
        """Execute the full research-to-report pipeline.

        Args:
            query: The user's research question.
            session_id: Research session UUID.

        Returns:
            ``WorkflowOutput`` with the complete report, citations, and quality score.

        Raises:
            AgentExecutionError: If the workflow exits with status="failed".
        """
        started_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            "ResearchWorkflow: starting.",
            extra={"session_id": session_id, "query": query[:120]},
        )

        initial_state: ResearchWorkflowState = {
            "query": query,
            "session_id": session_id,
            "mode": mode,
            "iteration": 0,
            "critique_suggestions": [],
            "findings": [],
            "queries_executed": [],
            "total_rag_results": 0,
            "total_web_results": 0,
            "verified_findings": [],
            "quality_score": 0.0,
            "critique": None,
            "report": None,
            "citations": [],
            "status": "researching",
            "error": None,
            "started_at": started_at,
            "completed_at": None,
        }

        final_state: ResearchWorkflowState = await asyncio.wait_for(
            self._graph.ainvoke(initial_state),
            timeout=_WORKFLOW_TIMEOUT_SECONDS,
        )

        if final_state.get("status") == "failed":
            error_msg = final_state.get("error") or "Unknown workflow failure."
            logger.error(
                "ResearchWorkflow: failed.",
                extra={"session_id": session_id, "error": error_msg},
            )
            raise AgentExecutionError(detail=error_msg)

        report = Report.model_validate(final_state["report"])
        citations = [ReportCitation.model_validate(c) for c in final_state.get("citations", [])]
        completed_at = final_state.get("completed_at") or datetime.now(timezone.utc).isoformat()
        quality_score = final_state.get("quality_score", 0.0)
        iterations_completed = final_state.get("iteration", 0) + 1

        logger.info(
            "ResearchWorkflow: complete.",
            extra={
                "session_id": session_id,
                "title": report.title,
                "word_count": report.word_count,
                "quality_score": quality_score,
                "iterations": iterations_completed,
                "citations": len(citations),
            },
        )

        return WorkflowOutput(
            session_id=session_id,
            query=query,
            report=report,
            citations=citations,
            queries_executed=final_state.get("queries_executed", []),
            total_rag_results=final_state.get("total_rag_results", 0),
            total_web_results=final_state.get("total_web_results", 0),
            quality_score=quality_score,
            iterations_completed=iterations_completed,
            started_at=started_at,
            completed_at=completed_at,
        )
