"""
Core evaluation harness for Nexus Research.

Answers the question: does the multi-agent quality-gate loop actually produce
better reports than a single research pass?

Approach
--------
For each benchmark query we run the ResearchWorkflow **twice**:

  1. Single-iteration run  — MAX_ITERATIONS=1 forces the loop to skip after
     the first critique, regardless of quality score.
  2. Full-iteration run    — uses the configured MAX_ITERATIONS (default 3),
     allowing the Critic to loop back when quality is insufficient.

Both reports are then scored independently by an LLM judge that has no access
to the Critic's self-reported quality_score (avoiding grade-inflation bias).

Settings patching
-----------------
``route_after_critique`` in app/graph/nodes.py reads ``get_settings()`` lazily
at call time.  We exploit this by temporarily setting the MAX_ITERATIONS env
var and clearing the lru_cache before each run, then restoring afterwards.
This is safe because the harness is single-threaded (asyncio event loop).

Service requirements
--------------------
The harness initialises the same services the lifespan would:
  - LLM client (required)
  - Sentence-transformers embedder (required for RAG)
  - Qdrant vector client (optional; warns if unavailable, RAG returns empty)

PostgreSQL and Redis are NOT required — they are used only by the API layer
for session persistence and rate limiting, not by the core pipeline.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator, Generator

from app.config import Settings, get_settings
from app.db.qdrant.client import close_qdrant_client, ensure_collection_exists, init_qdrant_client
from app.graph.workflow import ResearchWorkflow
from app.llm import close_llm_client, get_llm_client, init_llm_client
from app.rag import close_embedder, init_embedder

from eval.judge import score_report
from eval.schemas import (
    EvalReport,
    EvalSummary,
    IterationResult,
    QueryEvalResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings patching
# ---------------------------------------------------------------------------


@contextmanager
def _patch_max_iterations(n: int) -> Generator[None, None, None]:
    """Temporarily override MAX_ITERATIONS so get_settings() returns n.

    Clears the lru_cache before and after to ensure all lazy reads inside
    route_after_critique pick up the patched value.
    """
    original = os.environ.get("MAX_ITERATIONS")
    os.environ["MAX_ITERATIONS"] = str(n)
    get_settings.cache_clear()
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("MAX_ITERATIONS", None)
        else:
            os.environ["MAX_ITERATIONS"] = original
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _services(settings: Settings) -> AsyncGenerator[None, None]:
    """Initialise required services and tear them down on exit."""
    # LLM — hard failure; cannot evaluate without it
    init_llm_client(settings)
    client = get_llm_client()
    logger.info("Eval: LLM client ready. provider=%s model=%s", client.provider_name, client.model_name)

    # Qdrant — soft failure; RAG returns empty results but web search still works
    try:
        init_qdrant_client(settings)
        await ensure_collection_exists(settings)
        logger.info("Eval: Qdrant client ready.")
    except Exception as exc:
        logger.warning("Eval: Qdrant unavailable — RAG queries will return empty. error=%s", exc)

    # Embedder — hard failure; ResearchAgent requires it
    await init_embedder(settings)
    logger.info("Eval: Embedder ready. model=%s", settings.embedding_model)

    try:
        yield
    finally:
        close_embedder()
        await close_qdrant_client()
        close_llm_client()
        logger.info("Eval: Services closed.")


# ---------------------------------------------------------------------------
# Per-query evaluation
# ---------------------------------------------------------------------------


def _capture_iteration_result(
    label: str,
    output,  # WorkflowOutput
) -> IterationResult:
    report_dict = output.report.model_dump()
    return IterationResult(
        label=label,
        iterations_completed=output.iterations_completed,
        self_reported_quality=output.quality_score,
        word_count=output.report.word_count,
        citation_count=len(output.citations),
        queries_executed=len(output.queries_executed),
        judge_score=None,  # type: ignore[arg-type]  # filled in after scoring
        _report_dict=report_dict,  # type: ignore[call-arg]  # temp; not in schema
    )


async def evaluate_query(
    query: str,
    query_id: str,
    domain: str,
    workflow: ResearchWorkflow,
    full_max_iterations: int,
) -> QueryEvalResult:
    """Run one query through both single- and multi-iteration pipelines and score them.

    Args:
        query: The research question.
        query_id: Benchmark query identifier (e.g. "q01").
        domain: Thematic domain label for grouping.
        workflow: Pre-compiled ResearchWorkflow instance (shared across queries).
        full_max_iterations: The max_iterations value to use for the full run.

    Returns:
        QueryEvalResult with paired IterationResult objects and delta score.
    """
    result = QueryEvalResult(query_id=query_id, query=query, domain=domain)

    # --- Single-iteration run ------------------------------------------------
    logger.info("Eval [%s]: starting single-iteration run.", query_id)
    single_session = str(uuid.uuid4())
    try:
        with _patch_max_iterations(1):
            single_output = await workflow.run(query=query, session_id=single_session)

        single_report = single_output.report.model_dump()
        single_citations = len(single_output.citations)

        logger.info(
            "Eval [%s]: single-iteration complete. quality=%.2f words=%d",
            query_id, single_output.quality_score, single_output.report.word_count,
        )
    except Exception as exc:
        logger.error("Eval [%s]: single-iteration run failed: %s", query_id, exc)
        result.error = f"Single-iteration run failed: {exc}"
        return result

    # --- Full-iteration run --------------------------------------------------
    logger.info("Eval [%s]: starting full-iteration run (max=%d).", query_id, full_max_iterations)
    full_session = str(uuid.uuid4())
    try:
        with _patch_max_iterations(full_max_iterations):
            full_output = await workflow.run(query=query, session_id=full_session)

        full_report = full_output.report.model_dump()
        full_citations = len(full_output.citations)

        logger.info(
            "Eval [%s]: full-iteration complete. iters=%d quality=%.2f words=%d",
            query_id, full_output.iterations_completed,
            full_output.quality_score, full_output.report.word_count,
        )
    except Exception as exc:
        logger.error("Eval [%s]: full-iteration run failed: %s", query_id, exc)
        result.error = f"Full-iteration run failed: {exc}"
        return result

    # --- Independent judge scoring -------------------------------------------
    logger.info("Eval [%s]: scoring with LLM judge.", query_id)
    try:
        single_score = await score_report(query, single_report, single_citations)
        full_score = await score_report(query, full_report, full_citations)
    except Exception as exc:
        logger.error("Eval [%s]: judge scoring failed: %s", query_id, exc)
        result.error = f"Judge scoring failed: {exc}"
        return result

    # --- Assemble result -----------------------------------------------------
    result.single_iter = IterationResult(
        label="single_iteration",
        iterations_completed=single_output.iterations_completed,
        self_reported_quality=single_output.quality_score,
        word_count=single_output.report.word_count,
        citation_count=single_citations,
        queries_executed=len(single_output.queries_executed),
        judge_score=single_score,
    )
    result.multi_iter = IterationResult(
        label="multi_iteration",
        iterations_completed=full_output.iterations_completed,
        self_reported_quality=full_output.quality_score,
        word_count=full_output.report.word_count,
        citation_count=full_citations,
        queries_executed=len(full_output.queries_executed),
        judge_score=full_score,
    )
    result.delta = round(full_score.overall - single_score.overall, 3)
    result.improved = result.delta > 0

    logger.info(
        "Eval [%s]: done. single=%.2f multi=%.2f delta=%+.2f improved=%s",
        query_id, single_score.overall, full_score.overall, result.delta, result.improved,
    )
    return result


# ---------------------------------------------------------------------------
# Summary computation
# ---------------------------------------------------------------------------


def compute_summary(results: list[QueryEvalResult]) -> EvalSummary:
    """Compute aggregate statistics from completed query results."""
    completed = [r for r in results if r.single_iter and r.multi_iter]
    n = len(completed)
    if n == 0:
        return EvalSummary(
            queries_evaluated=0,
            avg_judge_single=0.0,
            avg_judge_multi=0.0,
            avg_delta=0.0,
            pct_improved=0.0,
            avg_self_reported_single=0.0,
            avg_self_reported_multi=0.0,
            avg_factual_coverage=0.0,
            avg_citation_groundedness=0.0,
            avg_coherence=0.0,
            avg_gap_closure=0.0,
        )

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 3)

    return EvalSummary(
        queries_evaluated=n,
        avg_judge_single=avg([r.single_iter.judge_score.overall for r in completed]),
        avg_judge_multi=avg([r.multi_iter.judge_score.overall for r in completed]),
        avg_delta=avg([r.delta for r in completed]),
        pct_improved=round(sum(1 for r in completed if r.improved) / n, 3),
        avg_self_reported_single=avg([r.single_iter.self_reported_quality for r in completed]),
        avg_self_reported_multi=avg([r.multi_iter.self_reported_quality for r in completed]),
        avg_factual_coverage=avg([r.multi_iter.judge_score.factual_coverage for r in completed]),
        avg_citation_groundedness=avg([r.multi_iter.judge_score.citation_groundedness for r in completed]),
        avg_coherence=avg([r.multi_iter.judge_score.coherence for r in completed]),
        avg_gap_closure=avg([r.multi_iter.judge_score.gap_closure for r in completed]),
    )


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------


async def run_evaluation(
    queries: list[dict],
    *,
    output_path: str | None = None,
    progress_callback=None,
) -> EvalReport:
    """Run the full evaluation harness.

    Args:
        queries: List of query dicts with keys: id, query, domain.
        output_path: If set, write the EvalReport JSON here after each query
                     (incremental saves protect against mid-run crashes).
        progress_callback: Optional async callable(query_id, result) called
                           after each query completes.

    Returns:
        EvalReport with all results and summary statistics.
    """
    settings = get_settings()

    report = EvalReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        llm_provider=settings.llm_provider,
        llm_model=getattr(settings, f"{settings.llm_provider}_model", "unknown"),
        max_iterations_tested=settings.max_iterations,
        total_queries=len(queries),
        completed_queries=0,
        failed_queries=0,
        results=[],
    )

    async with _services(settings):
        # Compile the workflow graph once; reuse it across all queries.
        # The graph's routing reads get_settings() lazily, so our env-var
        # patch inside evaluate_query affects each run correctly.
        workflow = ResearchWorkflow()

        for i, q in enumerate(queries):
            logger.info(
                "Eval: query %d/%d [%s] — %s",
                i + 1, len(queries), q["id"], q["query"][:80],
            )

            result = await evaluate_query(
                query=q["query"],
                query_id=q["id"],
                domain=q["domain"],
                workflow=workflow,
                full_max_iterations=settings.max_iterations,
            )

            report.results.append(result)

            if result.error:
                report.failed_queries += 1
            else:
                report.completed_queries += 1

            if progress_callback:
                await progress_callback(q["id"], result)

            # Incremental save after each query
            if output_path:
                _write_report(report, output_path)

        report.summary = compute_summary(report.results)

        # Final save with summary
        if output_path:
            _write_report(report, output_path)

    return report


def _write_report(report: EvalReport, path: str) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2, default=str)
    logger.debug("Eval: wrote incremental results to %s", path)
