"""
Writer Agent — LangGraph graph compilation and public ``WriterAgent`` class.

Graph topology
--------------

    START
      │
      ▼
    outline_node  ──── (status == "failed") ────→ END
      │
      ▼
    write_node  ──── (status == "failed") ──────→ END
      │
      ▼
     END

Usage
-----
    from app.agents.writer import WriterAgent
    from app.agents.research import Finding

    agent = WriterAgent()
    output = await agent.run(
        query="...",
        session_id="...",
        findings=[f.model_dump() for f in research_output.findings],
    )
    print(output.report.title)
    print(output.report.executive_summary)
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph


from app.agents.base import BaseAgent
from app.agents.writer.nodes import outline_node, write_node
from app.agents.writer.schemas import (
    Report,
    ReportCitation,
    WriterAgentOutput,
    WriterAgentState,
)
from app.core.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)


def _build_graph() -> StateGraph:
    """Construct the Writer Agent state graph."""
    graph = StateGraph(WriterAgentState)

    graph.add_node("outline", outline_node)
    graph.add_node("write", write_node)

    graph.add_edge(START, "outline")

    graph.add_conditional_edges(
        "outline",
        _route_after_outline,
        {"write": "write", END: END},
    )

    graph.add_edge("write", END)

    return graph


def _route_after_outline(state: WriterAgentState) -> str:
    if state.get("status") == "failed":
        return END
    return "write"


# ---------------------------------------------------------------------------
# Public agent class
# ---------------------------------------------------------------------------


class WriterAgent(BaseAgent):
    """Converts research findings into a structured, cited report.

    Stateless — compile once, call ``run()`` many times.

    The agent accepts findings as plain dicts so it can be called with the
    output of any upstream agent without tight coupling.  Each dict must have
    at minimum the keys ``text``, ``source_url``, and ``source_type``.

    Example::

        agent = WriterAgent()
        output = await agent.run(
            query="Latest advances in quantum computing",
            session_id="sess-abc",
            findings=[f.model_dump() for f in research_output.findings],
        )
        # output.report.key_findings, output.report.supporting_evidence, …
        # output.citations  → [ReportCitation(number=1, source_url=…), …]
    """

    def __init__(self) -> None:
        self._graph = _build_graph().compile()

    @property
    def name(self) -> str:
        return "WriterAgent"

    async def run(
        self,
        query: str,
        session_id: str,
        *,
        findings: list[dict[str, Any]],
        **kwargs: Any,
    ) -> WriterAgentOutput:
        """Write a report from the provided findings.

        Args:
            query: The original research question.
            session_id: Research session UUID.
            findings: List of finding dicts.  Minimum keys per dict:
                ``text``, ``source_url``, ``source_type``.
            **kwargs: Ignored; present for ``BaseAgent`` interface compatibility.

        Returns:
            ``WriterAgentOutput`` containing the complete report and citations.

        Raises:
            AgentExecutionError: If either LLM node fails unrecoverably.
        """
        logger.info(
            "WriterAgent: starting.",
            extra={
                "session_id": session_id,
                "num_findings": len(findings),
                "query": query[:120],
            },
        )

        mode = kwargs.get("mode", "general")

        initial_state: WriterAgentState = {
            "query": query,
            "session_id": session_id,
            "mode": mode,
            "findings": findings,
            "citation_map": [],
            "outline": None,
            "report": None,
            "status": "outlining",
            "error": None,
        }

        final_state: WriterAgentState = await self._graph.ainvoke(initial_state)

        if final_state.get("status") == "failed":
            error_msg = final_state.get("error") or "Unknown writer agent failure."
            logger.error(
                "WriterAgent: graph exited with failure.",
                extra={"session_id": session_id, "error": error_msg},
            )
            raise AgentExecutionError(detail=f"WriterAgent failed: {error_msg}")

        report: Report = final_state["report"]
        citation_map: list[dict[str, Any]] = final_state.get("citation_map", [])

        citations = [
            ReportCitation(
                number=entry["number"],
                source_url=entry["source_url"],
                source_type=entry["source_type"],
            )
            for entry in citation_map
        ]

        logger.info(
            "WriterAgent: complete.",
            extra={
                "session_id": session_id,
                "title": report.title,
                "word_count": report.word_count,
                "citations": len(citations),
            },
        )

        return WriterAgentOutput(
            report=report,
            citations=citations,
            session_id=session_id,
        )
