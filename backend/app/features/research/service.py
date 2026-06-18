"""
Research service — wires the workflow to the DB layer.

Responsibilities:
- Start a new research session (create DB row, launch background workflow task).
- Load session / report rows for API responses.
- List history with pagination.
"""

from __future__ import annotations

import asyncio
import uuid
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import AgentLog, Citation, Report, ResearchSession
from app.db.postgres.engine import get_session_factory
from app.graph.workflow import ResearchWorkflow

logger = logging.getLogger(__name__)


async def create_session_row(
    query: str,
    db: AsyncSession,
) -> ResearchSession:
    """Insert a new session row in ``running`` state and return it.

    Commits immediately so the row is visible to the polling endpoint
    before the workflow background task starts.
    """
    session_id = uuid.uuid4()
    db_session = ResearchSession(
        id=session_id,
        query=query,
        status="running",
    )
    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session


async def run_workflow_background(
    session_id: uuid.UUID,
    query: str,
    workflow: ResearchWorkflow,
    mode: str = "general",
) -> None:
    """Run the full research workflow in a background asyncio task.

    Opens its own DB session (independent of the request session, which is
    already closed by the time this runs).  Persists the report on success
    or marks the session ``failed`` on error.
    """
    factory = get_session_factory()

    async with factory() as db:
        try:
            output = await workflow.run(query=query, session_id=str(session_id), mode=mode)
        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "Workflow failed for session: %s",
                error_msg,
                extra={"session_id": str(session_id)},
            )
            result = await db.execute(
                select(ResearchSession).where(ResearchSession.id == session_id)
            )
            db_session = result.scalar_one()
            db_session.status = "failed"
            db_session.completed_at = datetime.now(timezone.utc)
            db_session.metadata_ = {"error": error_msg}
            await db.commit()
            return

        report_content: dict = {
            "body_sections": [
                {"heading": s.heading, "body": s.body, "citation_numbers": s.citation_numbers}
                for s in output.report.body_sections
            ],
            "synthesis": output.report.synthesis,
            "conclusion": output.report.conclusion,
        }
        if output.report.phd_annotations:
            a = output.report.phd_annotations
            report_content["phd_annotations"] = {
                "state_of_art_analysis": a.state_of_art_analysis,
                "future_possibilities": a.future_possibilities,
                "topic_overlap_and_inform": a.topic_overlap_and_inform,
                "novelty_assessment": a.novelty_assessment,
                "current_researchers": a.current_researchers,
            }

        db_report = Report(
            session_id=session_id,
            title=output.report.title,
            executive_summary=output.report.introduction,
            content=report_content,
            word_count=output.report.word_count,
            quality_score=output.quality_score,
        )
        db.add(db_report)
        await db.flush()

        for c in output.citations:
            db.add(
                Citation(
                    report_id=db_report.id,
                    citation_number=c.number,
                    source_url=c.source_url,
                    source_type=c.source_type,
                )
            )

        db.add(
            AgentLog(
                session_id=session_id,
                agent_name="ResearchWorkflow",
                success=True,
                output_data={
                    "queries_executed": output.queries_executed,
                    "total_rag_results": output.total_rag_results,
                    "total_web_results": output.total_web_results,
                    "word_count": output.report.word_count,
                    "citation_count": len(output.citations),
                    "quality_score": output.quality_score,
                    "iterations_completed": output.iterations_completed,
                },
            )
        )

        result = await db.execute(
            select(ResearchSession).where(ResearchSession.id == session_id)
        )
        db_session = result.scalar_one()
        db_session.status = "complete"
        db_session.completed_at = datetime.now(timezone.utc)

        await db.commit()
        logger.info(
            "Workflow complete for session.",
            extra={"session_id": str(session_id), "title": output.report.title},
        )


async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession,
) -> ResearchSession | None:
    """Load a session by ID, eager-loading its report."""
    result = await db.execute(
        select(ResearchSession)
        .where(ResearchSession.id == session_id)
        .options(selectinload(ResearchSession.report))
    )
    return result.scalar_one_or_none()


async def get_report(
    report_id: uuid.UUID,
    db: AsyncSession,
) -> Report | None:
    """Load a report by ID, eager-loading its citations."""
    result = await db.execute(
        select(Report)
        .where(Report.id == report_id)
        .options(selectinload(Report.citations))
    )
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[ResearchSession], int]:
    """Return a page of sessions ordered by creation time (newest first)."""
    offset = (page - 1) * limit

    total_result = await db.execute(
        select(func.count()).select_from(ResearchSession)
    )
    total = total_result.scalar_one()

    rows_result = await db.execute(
        select(ResearchSession)
        .options(selectinload(ResearchSession.report))
        .order_by(ResearchSession.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    sessions = list(rows_result.scalars())
    return sessions, total
