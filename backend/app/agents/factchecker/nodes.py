"""LangGraph node functions for the FactChecker Agent.

Node execution order:
    verify_search_node → assess_node

verify_search_node  — runs targeted Tavily queries to gather counter/supporting evidence.
assess_node         — LLM evaluates every finding against the verification context.

Both nodes are hard-fail: any unhandled exception sets status="failed".
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agents.base import ainvoke_with_retry
from app.agents.factchecker.prompts import VERIFIER_SYSTEM_PROMPT
from app.agents.factchecker.schemas import (
    FactCheckerAgentState,
    VerifiedFindingList,
)
from app.config import get_settings
from app.llm import get_model_for_agent
from app.tools.web_search import web_search

logger = logging.getLogger(__name__)

# Only verify the top N findings to bound Tavily API calls.
_MAX_VERIFICATION_QUERIES = 4


async def verify_search_node(state: FactCheckerAgentState) -> dict[str, Any]:
    """Run targeted verification web searches for the highest-relevance findings.

    Takes the top-N findings by relevance_score and constructs a targeted query
    for each one (e.g. "verify: <claim snippet>").  Runs all queries concurrently
    and stores results in ``verification_context``.

    Soft-fail per query: failures are logged and skipped rather than aborting.
    """
    findings = state["findings"]
    settings = get_settings()

    logger.info(
        "FactCheckerAgent: verification search.",
        extra={
            "session_id": state["session_id"],
            "total_findings": len(findings),
        },
    )

    # Select top findings by relevance to verify.
    sorted_findings = sorted(
        findings, key=lambda f: float(f.get("relevance_score", 0)), reverse=True
    )
    top_findings = sorted_findings[:_MAX_VERIFICATION_QUERIES]

    async def _verify_one(finding: dict[str, Any]) -> list[dict[str, Any]]:
        snippet = str(finding.get("text", ""))[:120]
        query = f"fact check verify: {snippet}"
        try:
            results = await web_search(query, settings=settings)
            return [
                {
                    "text": r.content,
                    "source_url": r.url,
                    "title": r.title,
                    "score": r.score,
                    "original_claim": snippet,
                }
                for r in results[:3]  # limit to 3 results per verification query
            ]
        except Exception as exc:
            logger.warning(
                "FactCheckerAgent: verification query failed; skipping.",
                extra={"query": query[:80], "error": str(exc)},
            )
            return []

    batches = await asyncio.gather(*[_verify_one(f) for f in top_findings])
    verification_context = [item for batch in batches for item in batch]

    logger.info(
        "FactCheckerAgent: verification search complete.",
        extra={
            "session_id": state["session_id"],
            "verification_results": len(verification_context),
        },
    )

    return {
        "verification_context": verification_context,
        "status": "assessing",
    }


async def assess_node(state: FactCheckerAgentState) -> dict[str, Any]:
    """Assess all findings using LLM with the verification context.

    Builds a single prompt containing all original findings and the verification
    web results, then calls the LLM with structured output to get
    ``VerifiedFindingList``.  Returns verified findings as dicts.
    """
    findings = state["findings"]
    verification_context = state["verification_context"]

    logger.info(
        "FactCheckerAgent: assessing findings.",
        extra={
            "session_id": state["session_id"],
            "findings": len(findings),
            "verification_results": len(verification_context),
        },
    )

    findings_text = _format_findings_for_prompt(findings)
    context_text = _format_verification_context(verification_context)

    try:
        model = get_model_for_agent("factchecker").with_structured_output(VerifiedFindingList)

        result: VerifiedFindingList = await ainvoke_with_retry(
            model,
            [
                {"role": "system", "content": VERIFIER_SYSTEM_PROMPT},
                {
                    "role": "human",
                    "content": (
                        f"Research query: {state['query']}\n\n"
                        f"Findings to verify:\n{findings_text}\n\n"
                        f"Verification search results:\n{context_text}"
                    ),
                },
            ],
        )

        verified_dicts = [f.model_dump() for f in result.findings]

        logger.info(
            "FactCheckerAgent: assessment complete.",
            extra={
                "session_id": state["session_id"],
                "total": len(verified_dicts),
                "verified": sum(1 for f in result.findings if f.verified),
            },
        )

        return {
            "verified_findings": verified_dicts,
            "status": "complete",
        }

    except Exception as exc:
        logger.error(
            "FactCheckerAgent: assessment failed: %s",
            exc,
            exc_info=True,
            extra={"session_id": state["session_id"]},
        )
        return {
            "status": "failed",
            "error": f"FactChecker assessment failed: {exc}",
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _format_findings_for_prompt(findings: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, f in enumerate(findings, start=1):
        score = f.get("relevance_score", 0.0)
        url = f.get("source_url", "")
        text = str(f.get("text", ""))[:400]
        lines.append(f"[{i}] (relevance: {score:.2f}) {url}\n{text}")
    return "\n\n".join(lines)


def _format_verification_context(context: list[dict[str, Any]]) -> str:
    if not context:
        return "(No verification search results available.)"
    lines: list[str] = []
    for i, r in enumerate(context, start=1):
        claim = r.get("original_claim", "")
        url = r.get("source_url", "")
        text = str(r.get("text", ""))[:300]
        lines.append(f"[V{i}] Checking claim: \"{claim}\"\n  Source: {url}\n  {text}")
    return "\n\n".join(lines)
