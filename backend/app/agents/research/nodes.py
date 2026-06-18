"""
LangGraph node functions for the Research Agent.

Each function receives the full ``ResearchAgentState`` and returns a partial
dict that LangGraph merges back into the state.  Nodes never mutate state
in-place — they only return the fields they changed.

Node execution order:
    plan_node → rag_search_node → web_search_node → synthesize_node

Failure model:
    - plan_node / synthesize_node  → hard fail: set status="failed", return immediately
    - rag_search_node              → soft fail: log warning, return empty rag_results
    - web_search_node              → soft fail per query: partial results continue
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from app.agents.base import ainvoke_with_retry
from app.agents.research.prompts import PLANNER_PHD_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT, SYNTHESIZER_SYSTEM_PROMPT
from app.agents.research.schemas import (
    FindingList,
    ResearchAgentState,
    ResearchPlan,
)
from app.config import get_settings
from app.llm import get_model_for_agent
from app.rag import retrieve
from app.rag.schemas import RetrievalQuery
from app.tools.web_search import web_search

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1 — Planner
# ---------------------------------------------------------------------------


async def plan_node(state: ResearchAgentState) -> dict[str, Any]:
    """Generate a research plan: break the query into targeted search queries.

    Uses the LLM with structured output to produce a ``ResearchPlan``.
    On failure, sets ``status="failed"`` so the conditional edge routes to END.

    Args:
        state: Current graph state.

    Returns:
        Partial state update with ``research_plan`` and ``status``.
    """
    logger.info(
        "ResearchAgent: planning.",
        extra={"session_id": state["session_id"], "query": state["query"][:120]},
    )

    try:
        mode = state.get("mode", "general")
        system_prompt = PLANNER_PHD_SYSTEM_PROMPT if mode == "phd" else PLANNER_SYSTEM_PROMPT
        model = get_model_for_agent("research").with_structured_output(ResearchPlan)

        plan: ResearchPlan = await ainvoke_with_retry(
            model,
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "human",
                    "content": f"Research query: {state['query']}",
                },
            ],
        )

        logger.info(
            "ResearchAgent: plan ready.",
            extra={
                "session_id": state["session_id"],
                "num_queries": len(plan.queries),
                "reasoning": plan.reasoning[:200],
            },
        )

        return {
            "research_plan": plan.queries,
            "status": "rag_searching",
        }

    except Exception as exc:
        logger.error(
            "ResearchAgent: planning failed.",
            extra={"session_id": state["session_id"], "error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Planning failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Node 2 — RAG search
# ---------------------------------------------------------------------------


async def rag_search_node(state: ResearchAgentState) -> dict[str, Any]:
    """Run all plan queries against the Qdrant knowledge base concurrently.

    Failures are caught per-query and logged; partial results are acceptable.
    If ALL queries fail the node still returns an empty list rather than
    aborting — the synthesizer will simply have fewer sources.

    Args:
        state: Current graph state (reads ``research_plan``, ``session_id``).

    Returns:
        Partial state update with ``rag_results`` and ``status``.
    """
    settings = get_settings()
    queries = state["research_plan"]

    logger.info(
        "ResearchAgent: RAG search.",
        extra={"session_id": state["session_id"], "num_queries": len(queries)},
    )

    async def _query_one(q: str) -> list[dict[str, Any]]:
        try:
            results = await retrieve(
                RetrievalQuery(
                    text=q,
                    session_id=state["session_id"],
                    k=settings.rag_top_k,
                )
            )
            return [
                {
                    "text": r.text,
                    "source_url": r.source_url,
                    "score": r.score,
                    "source_type": "rag",
                    "query_used": q,
                }
                for r in results
            ]
        except Exception as exc:
            logger.warning(
                "RAG query failed; skipping.",
                extra={"query": q, "error": str(exc)},
            )
            return []

    batches = await asyncio.gather(*[_query_one(q) for q in queries])
    rag_results = [item for batch in batches for item in batch]

    logger.info(
        "ResearchAgent: RAG search complete.",
        extra={"session_id": state["session_id"], "total_results": len(rag_results)},
    )

    return {
        "rag_results": rag_results,
        "status": "web_searching",
    }


# ---------------------------------------------------------------------------
# Node 3 — Web search
# ---------------------------------------------------------------------------


async def web_search_node(state: ResearchAgentState) -> dict[str, Any]:
    """Run all plan queries against Tavily concurrently.

    Each query failure is isolated — the rest of the batch continues.

    Args:
        state: Current graph state (reads ``research_plan``).

    Returns:
        Partial state update with ``web_results`` and ``status``.
    """
    queries = state["research_plan"]
    settings = get_settings()

    logger.info(
        "ResearchAgent: web search.",
        extra={"session_id": state["session_id"], "num_queries": len(queries)},
    )

    async def _search_one(q: str) -> list[dict[str, Any]]:
        results = await web_search(q, settings=settings)
        return [
            {
                "text": r.content,
                "source_url": r.url,
                "title": r.title,
                "score": r.score,
                "source_type": "web",
                "query_used": q,
            }
            for r in results
        ]

    batches = await asyncio.gather(*[_search_one(q) for q in queries])
    all_results = [item for batch in batches for item in batch]

    # Deduplicate by URL — multiple queries often surface the same paper.
    seen: set[str] = set()
    web_results: list[dict[str, Any]] = []
    for r in sorted(all_results, key=lambda x: x.get("score", 0.0), reverse=True):
        url = r.get("source_url", "")
        if url and url not in seen:
            seen.add(url)
            web_results.append(r)

    logger.info(
        "ResearchAgent: web search complete.",
        extra={
            "session_id": state["session_id"],
            "raw_results": len(all_results),
            "unique_results": len(web_results),
        },
    )

    return {
        "web_results": web_results,
        "status": "synthesizing",
    }


# ---------------------------------------------------------------------------
# Node 4 — Synthesizer
# ---------------------------------------------------------------------------


async def synthesize_node(state: ResearchAgentState) -> dict[str, Any]:
    """Synthesize raw search results into structured ``Finding`` objects.

    Passes all RAG + web results to the LLM with structured output.
    On failure, sets ``status="failed"``.

    Args:
        state: Current graph state (reads ``query``, ``rag_results``, ``web_results``).

    Returns:
        Partial state update with ``findings`` and ``status``.
    """
    rag_results = state["rag_results"]
    web_results = state["web_results"]
    all_results = rag_results + web_results

    logger.info(
        "ResearchAgent: synthesizing.",
        extra={
            "session_id": state["session_id"],
            "rag_count": len(rag_results),
            "web_count": len(web_results),
        },
    )

    if not all_results:
        logger.warning(
            "ResearchAgent: no search results to synthesize; returning empty findings.",
            extra={"session_id": state["session_id"]},
        )
        return {"findings": [], "status": "complete"}

    results_text = _format_results_for_prompt(all_results)

    try:
        model = get_model_for_agent("research").with_structured_output(FindingList)

        output: FindingList = await ainvoke_with_retry(
            model,
            [
                {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
                {
                    "role": "human",
                    "content": (
                        f"Original query: {state['query']}\n\n"
                        f"Search results:\n{results_text}"
                    ),
                },
            ]
        )

        # Sort by relevance descending.
        sorted_findings = sorted(
            output.findings, key=lambda f: f.relevance_score, reverse=True
        )

        logger.info(
            "ResearchAgent: synthesis complete.",
            extra={
                "session_id": state["session_id"],
                "findings": len(sorted_findings),
            },
        )

        return {
            "findings": sorted_findings,
            "status": "complete",
        }

    except Exception as exc:
        logger.error(
            "ResearchAgent: synthesis failed.",
            extra={"session_id": state["session_id"], "error": str(exc)},
        )
        return {
            "status": "failed",
            "error": f"Synthesis failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


_MAX_RESULTS_FOR_SYNTHESIS = 40  # cap total results sent to synthesizer
_MAX_CHARS_PER_RESULT = 400      # ~100 tokens per result; 40 results ≈ 4,000 tokens


def _format_results_for_prompt(results: list[dict[str, Any]]) -> str:
    """Render search results as numbered text blocks for the LLM prompt.

    Caps at _MAX_RESULTS_FOR_SYNTHESIS total results and truncates each snippet
    to _MAX_CHARS_PER_RESULT characters to stay within Groq's 12k TPM limit.
    """
    capped = results[:_MAX_RESULTS_FOR_SYNTHESIS]
    lines: list[str] = []
    for i, r in enumerate(capped, start=1):
        source_type = r.get("source_type", "web")
        url = r.get("source_url", "")
        text = str(r.get("text", ""))[:_MAX_CHARS_PER_RESULT]
        lines.append(f"[{i}] ({source_type}) — {url}\n{text}")
    return "\n\n".join(lines)
