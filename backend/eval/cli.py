"""
CLI entry point for the Nexus Research evaluation harness.

Usage
-----
    # Full run (all 20 queries)
    uv run python -m eval.cli

    # Quick smoke-test with 2 queries
    uv run python -m eval.cli --dry-run

    # Run first N queries
    uv run python -m eval.cli --queries 5

    # Custom output path
    uv run python -m eval.cli --output results/eval_2024.json

    # Quieter logging
    uv run python -m eval.cli --log-level WARNING

Output
------
Prints a per-query comparison table and a summary block to stdout.
Writes the full EvalReport as JSON to --output (default: eval_results.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup (must happen before any app imports so structlog sees the level)
# ---------------------------------------------------------------------------


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# Table rendering (no third-party deps — plain text with aligned columns)
# ---------------------------------------------------------------------------

_COL_WIDTHS = {
    "id": 4,
    "domain": 18,
    "s_judge": 8,
    "m_judge": 8,
    "delta": 7,
    "improved": 8,
    "s_quality": 9,
    "m_quality": 9,
    "s_iters": 6,
    "m_iters": 6,
}

_HEADER = (
    f"{'ID':<{_COL_WIDTHS['id']}}  "
    f"{'Domain':<{_COL_WIDTHS['domain']}}  "
    f"{'1-iter':>{_COL_WIDTHS['s_judge']}}  "
    f"{'N-iter':>{_COL_WIDTHS['m_judge']}}  "
    f"{'Delta':>{_COL_WIDTHS['delta']}}  "
    f"{'Better?':<{_COL_WIDTHS['improved']}}  "
    f"{'Crit-1':>{_COL_WIDTHS['s_quality']}}  "
    f"{'Crit-N':>{_COL_WIDTHS['m_quality']}}  "
    f"{'It-1':>{_COL_WIDTHS['s_iters']}}  "
    f"{'It-N':>{_COL_WIDTHS['m_iters']}}"
)

_SEPARATOR = "-" * len(_HEADER)


def _format_row(result) -> str:
    from eval.schemas import QueryEvalResult

    r: QueryEvalResult = result

    if r.error or not r.single_iter or not r.multi_iter:
        return (
            f"{r.query_id:<{_COL_WIDTHS['id']}}  "
            f"{r.domain:<{_COL_WIDTHS['domain']}}  "
            f"{'ERROR':<{_COL_WIDTHS['s_judge'] + _COL_WIDTHS['m_judge'] + 2}}  "
            f"{str(r.error or 'unknown')[:40]}"
        )

    s = r.single_iter
    m = r.multi_iter
    improved_str = "YES  +" if r.improved else ("NO" if r.delta < 0 else "TIE")

    return (
        f"{r.query_id:<{_COL_WIDTHS['id']}}  "
        f"{r.domain:<{_COL_WIDTHS['domain']}}  "
        f"{s.judge_score.overall:>{_COL_WIDTHS['s_judge']}.2f}  "
        f"{m.judge_score.overall:>{_COL_WIDTHS['m_judge']}.2f}  "
        f"{r.delta:>+{_COL_WIDTHS['delta']}.2f}  "
        f"{improved_str:<{_COL_WIDTHS['improved']}}  "
        f"{s.self_reported_quality:>{_COL_WIDTHS['s_quality']}.2f}  "
        f"{m.self_reported_quality:>{_COL_WIDTHS['m_quality']}.2f}  "
        f"{s.iterations_completed:>{_COL_WIDTHS['s_iters']}}  "
        f"{m.iterations_completed:>{_COL_WIDTHS['m_iters']}}"
    )


def print_table(report) -> None:
    from eval.schemas import EvalReport

    r: EvalReport = report

    print()
    print("=" * len(_HEADER))
    print("  NEXUS RESEARCH — EVALUATION RESULTS")
    print(f"  Model: {r.llm_provider} / {r.llm_model}   MAX_ITERATIONS={r.max_iterations_tested}")
    print(f"  Timestamp: {r.timestamp}")
    print("=" * len(_HEADER))
    print()
    print("Columns: 1-iter/N-iter = judge score (1–5 avg), Delta = N-iter minus 1-iter,")
    print("         Crit-1/Crit-N = Critic agent's self-reported quality, It = iterations run.")
    print()
    print(_HEADER)
    print(_SEPARATOR)

    for result in r.results:
        print(_format_row(result))

    print(_SEPARATOR)

    if r.summary:
        s = r.summary
        print()
        print("SUMMARY")
        print(f"  Queries evaluated  : {s.queries_evaluated}  "
              f"(failed: {r.failed_queries})")
        print(f"  Judge score 1-iter : {s.avg_judge_single:.3f} / 5.00")
        print(f"  Judge score N-iter : {s.avg_judge_multi:.3f} / 5.00")
        print(f"  Average delta      : {s.avg_delta:+.3f}")
        print(f"  Queries improved   : {s.pct_improved * 100:.1f}%")
        print()
        print("  N-iter dimension breakdown:")
        print(f"    Factual coverage       : {s.avg_factual_coverage:.3f}")
        print(f"    Citation groundedness  : {s.avg_citation_groundedness:.3f}")
        print(f"    Coherence              : {s.avg_coherence:.3f}")
        print(f"    Gap closure            : {s.avg_gap_closure:.3f}")
        print()
        print("  Self-reported quality (Critic agent):")
        print(f"    1-iter average : {s.avg_self_reported_single:.3f}")
        print(f"    N-iter average : {s.avg_self_reported_multi:.3f}")

        calibration_note = (
            "  NOTE: Compare Crit-N vs N-iter judge scores per row to check "
            "whether the Critic's self-reported quality tracks the independent judge."
        )
        print()
        print(calibration_note)

    print()


# ---------------------------------------------------------------------------
# Progress callback (live updates during the run)
# ---------------------------------------------------------------------------


async def _progress(query_id: str, result) -> None:
    if result.error:
        print(f"  [{query_id}] FAILED — {result.error[:80]}")
    elif result.single_iter and result.multi_iter:
        s = result.single_iter.judge_score.overall
        m = result.multi_iter.judge_score.overall
        print(f"  [{query_id}] done  1-iter={s:.2f}  N-iter={m:.2f}  delta={result.delta:+.2f}")
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _main(args: argparse.Namespace) -> int:
    _setup_logging(args.log_level)

    queries_path = Path(__file__).parent / "queries.json"
    with open(queries_path, encoding="utf-8") as f:
        all_queries: list[dict] = json.load(f)

    if args.dry_run:
        queries = all_queries[:2]
        print(f"Dry-run mode: evaluating {len(queries)} queries.")
    elif args.queries:
        queries = all_queries[: args.queries]
        print(f"Evaluating first {len(queries)} queries.")
    else:
        queries = all_queries
        print(f"Evaluating all {len(queries)} queries.")

    output_path = args.output or "eval_results.json"
    print(f"Results will be written to: {output_path}")
    print()
    print("Progress:")

    # App imports are deferred so --help works without initialised services
    from eval.harness import run_evaluation

    try:
        report = await run_evaluation(
            queries=queries,
            output_path=output_path,
            progress_callback=_progress,
        )
    except KeyboardInterrupt:
        print("\nInterrupted — partial results may have been saved.")
        return 1
    except Exception as exc:
        logging.getLogger(__name__).exception("Evaluation failed: %s", exc)
        return 1

    print_table(report)
    print(f"Full results written to: {output_path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nexus Research evaluation harness — compares single-iteration vs multi-iteration reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--queries",
        type=int,
        default=None,
        metavar="N",
        help="Evaluate only the first N queries (default: all 20).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate only 2 queries — quick smoke-test.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="eval_results.json",
        metavar="PATH",
        help="Output file path for the JSON report (default: eval_results.json).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )

    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args)))


if __name__ == "__main__":
    main()
