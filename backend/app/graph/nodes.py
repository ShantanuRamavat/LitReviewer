"""
Orchestration-graph node factories for the research workflow.

Each factory receives a pre-compiled agent instance and returns an async node
function that closes over it.  This pattern:
- Pays agent compilation cost once at ResearchWorkflow.__init__().
- Makes agents injectable in tests (pass a mock agent to the factory).
- Keeps node functions pure — no module-level singletons.

Retry policy
------------
All agent-call wrappers use tenacity (3 attempts, exponential backoff 5–30 s)
to handle transient LLM / network errors.

Error handling
--------------
All nodes catch exceptions and convert them to status="failed" state updates.
Unhandled exceptions from LangGraph nodes are swallowed silently, so explicit
conversion is required to surface errors in WorkflowOutput.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.agents.critic.graph import CriticAgent
from app.agents.factchecker.graph import FactCheckerAgent
from app.agents.research.graph import ResearchAgent
from app.agents.writer.graph import WriterAgent
from app.core.exceptions import AgentExecutionError
from app.graph.state import ResearchWorkflowState

logger = logging.getLogger(__name__)

NodeFn = Callable[
    [ResearchWorkflowState],
    Coroutine[Any, Any, dict[str, Any]],
]

_RETRY_KWARGS = dict(
    retry=retry_if_exception_type(AgentExecutionError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=30),
    reraise=True,
)


# ---------------------------------------------------------------------------
# Research node
# ---------------------------------------------------------------------------


def make_research_node(agent: ResearchAgent) -> NodeFn:
    """Return a LangGraph node that runs the Research Agent."""

    @retry(**_RETRY_KWARGS)
    async def _run(query: str, session_id: str, iteration: int, suggestions: list[str], mode: str) -> Any:
        effective_query = query
        if iteration > 0 and suggestions:
            hints = "; ".join(suggestions[:3])
            effective_query = f"{query}\n\nFocus on these gaps: {hints}"
        return await agent.run(query=effective_query, session_id=session_id, iteration=iteration, mode=mode)

    async def research_node(state: ResearchWorkflowState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        logger.info(
            "Workflow: research starting.",
            extra={
                "session_id": state["session_id"],
                "query": state["query"][:120],
                "iteration": iteration,
            },
        )

        try:
            output = await _run(
                state["query"],
                state["session_id"],
                iteration,
                state.get("critique_suggestions", []),
                state.get("mode", "general"),
            )

            logger.info(
                "Workflow: research complete.",
                extra={
                    "session_id": state["session_id"],
                    "findings": len(output.findings),
                    "rag_results": output.total_rag_results,
                    "web_results": output.total_web_results,
                    "iteration": iteration,
                },
            )

            return {
                "findings": [f.model_dump() for f in output.findings],
                "queries_executed": output.queries_executed,
                "total_rag_results": output.total_rag_results,
                "total_web_results": output.total_web_results,
                "status": "fact_checking",
            }

        except AgentExecutionError as exc:
            logger.error(
                "Workflow: research failed after retries: %s",
                exc.detail,
                extra={"session_id": state["session_id"]},
            )
            # On loop iterations we already have verified findings from iteration 0.
            # Fall through to writing rather than hard-failing the entire workflow.
            if iteration > 0 and state.get("verified_findings"):
                logger.warning(
                    "Workflow: research loop failed but have prior verified findings — skipping to write.",
                    extra={"session_id": state["session_id"]},
                )
                return {"status": "writing"}
            return {"status": "failed", "error": f"Research phase failed: {exc.detail}"}
        except Exception as exc:
            logger.error(
                "Workflow: research raised unexpected error: %s",
                exc,
                exc_info=True,
                extra={"session_id": state["session_id"]},
            )
            if iteration > 0 and state.get("verified_findings"):
                logger.warning(
                    "Workflow: research loop errored but have prior verified findings — skipping to write.",
                    extra={"session_id": state["session_id"]},
                )
                return {"status": "writing"}
            return {"status": "failed", "error": f"Research phase error: {exc}"}

    research_node.__name__ = "research_node"
    return research_node


# ---------------------------------------------------------------------------
# FactChecker node
# ---------------------------------------------------------------------------


def make_factcheck_node(agent: FactCheckerAgent) -> NodeFn:
    """Return a LangGraph node that runs the FactChecker Agent."""

    @retry(**_RETRY_KWARGS)
    async def _run(query: str, session_id: str, findings: list[Any]) -> Any:
        return await agent.run(query=query, session_id=session_id, findings=findings)

    async def factcheck_node(state: ResearchWorkflowState) -> dict[str, Any]:
        logger.info(
            "Workflow: fact-checking starting.",
            extra={
                "session_id": state["session_id"],
                "findings": len(state["findings"]),
            },
        )

        try:
            output = await _run(state["query"], state["session_id"], state["findings"])

            logger.info(
                "Workflow: fact-checking complete.",
                extra={
                    "session_id": state["session_id"],
                    "total": output.total_input,
                    "verified": output.total_verified,
                    "disputed": output.total_disputed,
                },
            )

            return {
                "verified_findings": [f.model_dump() for f in output.verified_findings],
                "status": "critiquing",
            }

        except AgentExecutionError as exc:
            logger.error(
                "Workflow: fact-checking failed after retries: %s",
                exc.detail,
                extra={"session_id": state["session_id"]},
            )
            return {"status": "failed", "error": f"FactCheck phase failed: {exc.detail}"}
        except Exception as exc:
            logger.error(
                "Workflow: fact-checking raised unexpected error: %s",
                exc,
                exc_info=True,
                extra={"session_id": state["session_id"]},
            )
            return {"status": "failed", "error": f"FactCheck phase error: {exc}"}

    factcheck_node.__name__ = "factcheck_node"
    return factcheck_node


# ---------------------------------------------------------------------------
# Critique node
# ---------------------------------------------------------------------------


def make_critique_node(agent: CriticAgent) -> NodeFn:
    """Return a LangGraph node that runs the Critic Agent."""

    @retry(**_RETRY_KWARGS)
    async def _run(
        query: str, session_id: str, verified_findings: list[Any], iteration: int
    ) -> Any:
        return await agent.run(
            query=query,
            session_id=session_id,
            verified_findings=verified_findings,
            iteration=iteration,
        )

    async def critique_node(state: ResearchWorkflowState) -> dict[str, Any]:
        iteration = state.get("iteration", 0)
        logger.info(
            "Workflow: critique starting.",
            extra={
                "session_id": state["session_id"],
                "iteration": iteration,
            },
        )

        try:
            output = await _run(
                state["query"],
                state["session_id"],
                state["verified_findings"],
                iteration,
            )

            logger.info(
                "Workflow: critique complete.",
                extra={
                    "session_id": state["session_id"],
                    "quality_score": output.quality_score,
                    "is_sufficient": output.is_sufficient,
                    "iteration": iteration,
                },
            )

            return {
                "quality_score": output.quality_score,
                "critique": output.critique.model_dump(),
                "critique_suggestions": output.suggestions,
                "status": "critiquing",  # routing decides next step
            }

        except AgentExecutionError as exc:
            logger.error(
                "Workflow: critique failed after retries: %s",
                exc.detail,
                extra={"session_id": state["session_id"]},
            )
            return {"status": "failed", "error": f"Critique phase failed: {exc.detail}"}
        except Exception as exc:
            logger.error(
                "Workflow: critique raised unexpected error: %s",
                exc,
                exc_info=True,
                extra={"session_id": state["session_id"]},
            )
            return {"status": "failed", "error": f"Critique phase error: {exc}"}

    critique_node.__name__ = "critique_node"
    return critique_node


# ---------------------------------------------------------------------------
# Write node
# ---------------------------------------------------------------------------


def make_write_node(agent: WriterAgent) -> NodeFn:
    """Return a LangGraph node that runs the Writer Agent."""

    @retry(**_RETRY_KWARGS)
    async def _run(query: str, session_id: str, findings: list[Any], mode: str) -> Any:
        return await agent.run(query=query, session_id=session_id, findings=findings, mode=mode)

    async def write_node(state: ResearchWorkflowState) -> dict[str, Any]:
        findings = state.get("verified_findings") or state["findings"]

        logger.info(
            "Workflow: writing starting.",
            extra={
                "session_id": state["session_id"],
                "num_findings": len(findings),
                "mode": state.get("mode", "general"),
            },
        )

        try:
            output = await _run(state["query"], state["session_id"], findings, state.get("mode", "general"))
            completed_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                "Workflow: writing complete.",
                extra={
                    "session_id": state["session_id"],
                    "title": output.report.title,
                    "word_count": output.report.word_count,
                    "citations": len(output.citations),
                },
            )

            return {
                "report": output.report.model_dump(),
                "citations": [c.model_dump() for c in output.citations],
                "status": "complete",
                "completed_at": completed_at,
            }

        except AgentExecutionError as exc:
            logger.error(
                "Workflow: writing failed after retries: %s",
                exc.detail,
                extra={"session_id": state["session_id"]},
            )
            return {"status": "failed", "error": f"Writing phase failed: {exc.detail}"}
        except Exception as exc:
            logger.error(
                "Workflow: writing raised unexpected error: %s",
                exc,
                exc_info=True,
                extra={"session_id": state["session_id"]},
            )
            return {"status": "failed", "error": f"Writing phase error: {exc}"}

    write_node.__name__ = "write_node"
    return write_node


# ---------------------------------------------------------------------------
# Edge routing helpers
# ---------------------------------------------------------------------------


def route_on_status(state: ResearchWorkflowState) -> str:
    """Return 'continue', 'skip_to_write', or 'failed' based on the current status."""
    status = state.get("status")
    if status == "failed":
        return "failed"
    if status == "writing":
        return "skip_to_write"
    return "continue"


def route_after_critique(state: ResearchWorkflowState) -> str:
    """Decide whether to loop back to research or proceed to writing.

    Uses the numeric quality_score against settings.min_quality_score — simpler
    and more predictable than relying on the LLM's is_sufficient boolean.

    Returns 'loop' if quality < threshold and iterations remain.
    Returns 'continue' to proceed to WriterAgent.
    Returns 'failed' on workflow error.
    """
    from app.config import get_settings  # noqa: PLC0415 — avoid circular at module level

    if state.get("status") == "failed":
        return "failed"

    quality_score = state.get("quality_score", 1.0)
    iteration = state.get("iteration", 0)
    settings = get_settings()

    if quality_score < settings.min_quality_score and iteration < settings.max_iterations - 1:
        logger.info(
            "Workflow: quality insufficient — looping. iteration=%d quality=%.2f threshold=%.2f",
            iteration,
            quality_score,
            settings.min_quality_score,
        )
        return "loop"

    logger.info(
        "Workflow: quality sufficient — proceeding to write. iteration=%d quality=%.2f",
        iteration,
        quality_score,
    )
    return "continue"
