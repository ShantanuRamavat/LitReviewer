"""
Shared state and output types for the top-level research workflow graph.

``ResearchWorkflowState`` is the TypedDict that flows between every node in
the orchestration graph.  It is distinct from the per-agent state objects
(``ResearchAgentState``, etc.) — those are internal to each subgraph.

``WorkflowOutput`` is the structured result returned by ``ResearchWorkflow.run()``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel
from typing_extensions import TypedDict

from app.agents.writer.schemas import Report, ReportCitation


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------


class ResearchWorkflowState(TypedDict):
    """Mutable state shared across all orchestration-graph nodes.

    Fields
    ------
    query : str
        Original user research question.
    session_id : str
        Research session UUID used to scope Qdrant queries and DB records.
    iteration : int
        Current research loop counter (0-indexed).  Incremented each time the
        Critic routes back to ResearchAgent.  Max controlled by settings.
    critique_suggestions : list[str]
        Search-query suggestions from the last CriticAgent run.  Passed to
        ResearchAgent on loop iterations to focus on identified gaps.

    findings : list[dict[str, Any]]
        Serialised Finding objects produced by ResearchAgent (current iteration).
    queries_executed : list[str]
        Search queries run by ResearchAgent in the current iteration.
    total_rag_results : int
        Qdrant chunks retrieved across all research queries.
    total_web_results : int
        Tavily pages retrieved across all research queries.

    verified_findings : list[dict[str, Any]]
        Findings annotated by FactCheckerAgent (verified, confidence, note).
    quality_score : float
        Overall quality score assigned by CriticAgent (0–1).
    critique : dict[str, Any] | None
        Full serialised CritiqueOutput from the last CriticAgent run.

    report : dict[str, Any] | None
        Serialised Report object produced by WriterAgent.
    citations : list[dict[str, Any]]
        Serialised ReportCitation list assembled by WriterAgent.

    status : str
        Current workflow phase.  Set to ``"failed"`` to short-circuit to END.
    error : str | None
        Human-readable error message when status == "failed".
    started_at : str
        ISO-8601 timestamp of workflow entry.
    completed_at : str | None
        ISO-8601 timestamp set when the graph reaches END successfully.
    """

    query: str
    session_id: str
    mode: str
    iteration: int
    critique_suggestions: list[str]

    # Research outputs (reset each iteration)
    findings: list[dict[str, Any]]
    queries_executed: list[str]
    total_rag_results: int
    total_web_results: int

    # FactChecker outputs
    verified_findings: list[dict[str, Any]]

    # Critic outputs
    quality_score: float
    critique: dict[str, Any] | None

    # Writer outputs
    report: dict[str, Any] | None
    citations: list[dict[str, Any]]

    # Control
    status: Literal[
        "researching", "fact_checking", "critiquing", "writing", "complete", "failed"
    ]  # "writing" is also used as a skip-to-write signal from the research fallback
    error: str | None
    started_at: str
    completed_at: str | None


# ---------------------------------------------------------------------------
# Final workflow output
# ---------------------------------------------------------------------------


class WorkflowOutput(BaseModel):
    """Structured result returned by ``ResearchWorkflow.run()``."""

    session_id: str
    query: str
    report: Report
    citations: list[ReportCitation]
    queries_executed: list[str]
    total_rag_results: int
    total_web_results: int
    quality_score: float
    iterations_completed: int
    started_at: str
    completed_at: str
