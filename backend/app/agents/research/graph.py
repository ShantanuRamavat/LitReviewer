"""
Research Agent — LangGraph graph compilation and public ``ResearchAgent`` class.

Graph topology
--------------

    START
      │
      ▼
    plan_node  ──── (status == "failed") ───→ END
      │
      ▼
    rag_search_node
      │
      ▼
    web_search_node
      │
      ▼
    synthesize_node  ── (status == "failed") ─→ END
      │
      ▼
     END

The graph is compiled once at ``ResearchAgent.__init__()`` and reused across
all ``run()`` calls — compilation is expensive; invocation is cheap.

Usage
-----
    from app.agents.research import ResearchAgent

    agent = ResearchAgent()
    output = await agent.run(query="...", session_id="...")
    for finding in output.findings:
        print(finding.text, finding.source_url)
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agents.base import BaseAgent
from app.agents.research.nodes import (
    plan_node,
    rag_search_node,
    synthesize_node,
    web_search_node,
)
from app.agents.research.schemas import (
    Finding,
    ResearchAgentOutput,
    ResearchAgentState,
)
from app.core.exceptions import AgentExecutionError

logger = logging.getLogger(__name__)



def _build_graph() -> StateGraph:
    """Construct and compile the Research Agent state graph."""
    graph = StateGraph(ResearchAgentState)

    # ---- Nodes ----------------------------------------------------------------
    graph.add_node("plan", plan_node)
    graph.add_node("rag_search", rag_search_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("synthesize", synthesize_node)

    # ---- Entry ----------------------------------------------------------------
    graph.add_edge(START, "plan")

    # ---- plan → (conditional) -------------------------------------------------
    graph.add_conditional_edges(
        "plan",
        _route_after_plan,
        {"rag_search": "rag_search", END: END},
    )

    # ---- Linear middle --------------------------------------------------------
    graph.add_edge("rag_search", "web_search")

    # ---- web_search → synthesize ----------------------------------------------
    graph.add_edge("web_search", "synthesize")

    # ---- synthesize → END (terminal node — always ends) ----------------------
    graph.add_edge("synthesize", END)

    return graph


def _route_after_plan(state: ResearchAgentState) -> str:
    """Route to END if planning failed, otherwise continue to RAG search."""
    if state.get("status") == "failed":
        return END
    return "rag_search"


# ---------------------------------------------------------------------------
# Public agent class
# ---------------------------------------------------------------------------


class ResearchAgent(BaseAgent):
    """Self-contained Research Agent backed by a compiled LangGraph graph.

    The agent is stateless — all per-request data lives inside
    ``ResearchAgentState``.  Instantiate once and call ``run()`` many times.

    Example::

        agent = ResearchAgent()
        output = await agent.run(
            query="Latest breakthroughs in quantum error correction",
            session_id="sess-abc-123",
            iteration=0,
        )
        print(f"Found {len(output.findings)} findings.")
    """

    def __init__(self) -> None:
        self._graph = _build_graph().compile()

    @property
    def name(self) -> str:
        return "ResearchAgent"

    async def run(
        self,
        query: str,
        session_id: str,
        *,
        iteration: int = 0,
        **kwargs: Any,
    ) -> ResearchAgentOutput:
        """Execute the research pipeline and return structured findings.

        Args:
            query: The user's research question.
            session_id: Research session UUID for Qdrant scoping.
            iteration: Loop counter from the outer orchestration graph.
            **kwargs: Ignored; present for ``BaseAgent`` interface compatibility.

        Returns:
            ``ResearchAgentOutput`` with findings sorted by relevance.

        Raises:
            AgentExecutionError: If the graph exits with ``status="failed"``.
        """
        logger.info(
            "ResearchAgent: starting.",
            extra={
                "session_id": session_id,
                "iteration": iteration,
                "query": query[:120],
            },
        )

        mode = kwargs.get("mode", "general")

        initial_state: ResearchAgentState = {
            "query": query,
            "session_id": session_id,
            "mode": mode,
            "iteration": iteration,
            "research_plan": [],
            "rag_results": [],
            "web_results": [],
            "findings": [],
            "status": "planning",
            "error": None,
        }

        final_state: ResearchAgentState = await self._graph.ainvoke(initial_state)

        if final_state.get("status") == "failed":
            error_msg = final_state.get("error") or "Unknown research agent failure."
            logger.error(
                "ResearchAgent: graph exited with failure.",
                extra={"session_id": session_id, "error": error_msg},
            )
            raise AgentExecutionError(
                detail=f"ResearchAgent failed: {error_msg}"
            )

        findings: list[Finding] = final_state.get("findings", [])
        queries: list[str] = final_state.get("research_plan", [])
        rag_results: list[dict] = final_state.get("rag_results", [])
        web_results: list[dict] = final_state.get("web_results", [])

        logger.info(
            "ResearchAgent: complete.",
            extra={
                "session_id": session_id,
                "iteration": iteration,
                "findings": len(findings),
                "rag_results": len(rag_results),
                "web_results": len(web_results),
            },
        )

        return ResearchAgentOutput(
            findings=findings,
            queries_executed=queries,
            total_rag_results=len(rag_results),
            total_web_results=len(web_results),
            iteration=iteration,
        )
