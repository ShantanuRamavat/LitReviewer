"""
Research API router.

Endpoints
---------
POST /research/start        — kick off a new research session
GET  /research/{session_id} — poll session status
GET  /reports/{report_id}   — retrieve the full report
GET  /history               — list past sessions (paginated)
DELETE /history/{session_id} — delete a session and its report
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

from app.db.postgres.session import get_db as get_db_session
from app.features.research import schemas
from app.features.research import service
from app.graph.workflow import ResearchWorkflow

router = APIRouter()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_workflow(request: Request) -> ResearchWorkflow:
    """Pull the ResearchWorkflow singleton from app.state."""
    workflow: ResearchWorkflow = request.app.state.workflow
    return workflow


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Workflow = Annotated[ResearchWorkflow, Depends(get_workflow)]


# ---------------------------------------------------------------------------
# Research endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/research/start",
    response_model=schemas.ResearchSessionResponse,
    status_code=202,
    summary="Start a new research session",
)
async def start_research(
    body: schemas.StartResearchRequest,
    workflow: Workflow,
    db: DbSession,
) -> schemas.ResearchSessionResponse:
    """Create a research session and run the multi-agent pipeline.

    Blocks until the pipeline completes (or fails) then returns the session
    record.  The ``report_id`` field is populated on success.
    """
    db_session = await service.create_session_row(query=body.query, db=db)
    asyncio.create_task(
        service.run_workflow_background(
            session_id=db_session.id,
            query=body.query,
            workflow=workflow,
            mode=body.mode,
        )
    )
    return schemas.ResearchSessionResponse(
        session_id=db_session.id,
        query=db_session.query,
        status=db_session.status,
        report_id=None,
        created_at=db_session.created_at,
        completed_at=db_session.completed_at,
    )


@router.get(
    "/research/{session_id}",
    response_model=schemas.ResearchSessionResponse,
    summary="Get research session status",
)
async def get_research_session(
    session_id: uuid.UUID,
    db: DbSession,
) -> schemas.ResearchSessionResponse:
    """Return status and report_id for a research session."""
    db_session = await service.get_session(session_id, db)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    report_id = db_session.report.id if db_session.report else None
    error_msg = (db_session.metadata_ or {}).get("error") if db_session.status == "failed" else None
    return schemas.ResearchSessionResponse(
        session_id=db_session.id,
        query=db_session.query,
        status=db_session.status,
        report_id=report_id,
        error=error_msg,
        created_at=db_session.created_at,
        completed_at=db_session.completed_at,
    )


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/reports/{report_id}",
    response_model=schemas.ReportResponse,
    summary="Get a completed research report",
)
async def get_report(
    report_id: uuid.UUID,
    db: DbSession,
) -> schemas.ReportResponse:
    """Return the full report including all sections and citations."""
    db_report = await service.get_report(report_id, db)
    if db_report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    phd_data = db_report.content.get("phd_annotations")
    phd_annotations = schemas.PhDAnnotationsResponse(**phd_data) if phd_data else None

    content = schemas.ReportContentResponse(
        body_sections=[
            schemas.BodySectionResponse(**s)
            for s in db_report.content.get("body_sections", [])
        ],
        synthesis=db_report.content.get("synthesis", ""),
        conclusion=db_report.content.get("conclusion", ""),
        phd_annotations=phd_annotations,
    )

    return schemas.ReportResponse(
        id=db_report.id,
        session_id=db_report.session_id,
        title=db_report.title,
        introduction=db_report.executive_summary,
        content=content,
        word_count=db_report.word_count,
        quality_score=db_report.quality_score,
        citations=[
            schemas.CitationResponse(
                number=c.citation_number,
                source_url=c.source_url,
                source_type=c.source_type,
            )
            for c in db_report.citations
        ],
        created_at=db_report.created_at,
    )


# ---------------------------------------------------------------------------
# History endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/history",
    response_model=schemas.HistoryResponse,
    summary="List research history",
)
async def list_history(
    db: DbSession,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> schemas.HistoryResponse:
    """Return a paginated list of past research sessions."""
    sessions, total = await service.list_sessions(db, page=page, limit=limit)
    items = [
        schemas.HistoryItemResponse(
            session_id=s.id,
            query=s.query,
            status=s.status,
            report_id=s.report.id if s.report else None,
            created_at=s.created_at,
            completed_at=s.completed_at,
        )
        for s in sessions
    ]
    return schemas.HistoryResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
    )


@router.delete(
    "/history/{session_id}",
    status_code=204,
    summary="Delete a research session",
)
async def delete_session(
    session_id: uuid.UUID,
    db: DbSession,
) -> None:
    """Delete a session and all associated reports and citations (cascade)."""
    db_session = await service.get_session(session_id, db)
    if db_session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    await db.delete(db_session)
    await db.commit()
