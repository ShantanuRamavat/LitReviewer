"""
Data contracts for the evaluation harness.

JudgeScore           — four-dimension rubric score from the independent LLM judge.
IterationResult      — captured output from one workflow run (single or multi-iter).
QueryEvalResult      — paired comparison for one benchmark query.
EvalSummary          — aggregate statistics across all queries.
EvalReport           — top-level container written to the output JSON file.
"""

from __future__ import annotations

from pydantic import BaseModel, computed_field


class JudgeScore(BaseModel):
    """Rubric scores assigned by the independent LLM judge (1–5 each)."""

    factual_coverage: int
    citation_groundedness: int
    coherence: int
    gap_closure: int
    reasoning: str

    @computed_field
    @property
    def overall(self) -> float:
        return (
            self.factual_coverage
            + self.citation_groundedness
            + self.coherence
            + self.gap_closure
        ) / 4.0


class IterationResult(BaseModel):
    """Captured output from one workflow run."""

    label: str  # "single_iteration" | "multi_iteration"
    iterations_completed: int
    self_reported_quality: float  # Critic agent's own score
    word_count: int
    citation_count: int
    queries_executed: int
    judge_score: JudgeScore


class QueryEvalResult(BaseModel):
    """Paired evaluation for one benchmark query."""

    query_id: str
    query: str
    domain: str
    single_iter: IterationResult | None = None
    multi_iter: IterationResult | None = None
    improved: bool = False
    delta: float = 0.0  # multi_iter.overall - single_iter.overall
    error: str | None = None


class EvalSummary(BaseModel):
    """Aggregate statistics across all successfully evaluated queries."""

    queries_evaluated: int
    avg_judge_single: float
    avg_judge_multi: float
    avg_delta: float
    pct_improved: float  # fraction of queries where multi > single
    avg_self_reported_single: float
    avg_self_reported_multi: float
    # Per-dimension averages (multi-iteration)
    avg_factual_coverage: float
    avg_citation_groundedness: float
    avg_coherence: float
    avg_gap_closure: float


class EvalReport(BaseModel):
    """Top-level result written to the output JSON file."""

    timestamp: str
    llm_provider: str
    llm_model: str
    max_iterations_tested: int
    total_queries: int
    completed_queries: int
    failed_queries: int
    results: list[QueryEvalResult]
    summary: EvalSummary | None = None
