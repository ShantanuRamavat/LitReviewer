"""
SQLAlchemy ORM models for the LitReviewer platform.

All models inherit from ``Base`` (defined in ``app.db.postgres.engine``) so
Alembic can discover them via a single metadata import.

Tables
------
research_sessions   — one row per user research request.
reports             — one report per completed session.
citations           — numbered bibliography entries for a report.
agent_logs          — per-agent execution records for observability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres.engine import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# research_sessions
# ---------------------------------------------------------------------------


class ResearchSession(Base):
    """Represents one research request from a user.

    Lifecycle: running → complete | failed.
    """

    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
        index=True,
    )
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )

    # Relationships
    report: Mapped[Report | None] = relationship(
        "Report",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    agent_logs: Mapped[list[AgentLog]] = relationship(
        "AgentLog",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<ResearchSession id={self.id} status={self.status!r}>"


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------


class Report(Base):
    """Final written report produced for a research session."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Full structured content: {key_findings, supporting_evidence, conclusion}
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
    )

    # Relationships
    session: Mapped[ResearchSession] = relationship(
        "ResearchSession",
        back_populates="report",
    )
    citations: Mapped[list[Citation]] = relationship(
        "Citation",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="Citation.citation_number",
    )

    def __repr__(self) -> str:
        return f"<Report id={self.id} title={self.title!r}>"


# ---------------------------------------------------------------------------
# citations
# ---------------------------------------------------------------------------


class Citation(Base):
    """One numbered bibliography entry attached to a report."""

    __tablename__ = "citations"
    __table_args__ = (
        UniqueConstraint("report_id", "citation_number", name="uq_report_citation_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    citation_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
    )

    # Relationships
    report: Mapped[Report] = relationship("Report", back_populates="citations")

    def __repr__(self) -> str:
        return f"<Citation [{self.citation_number}] {self.source_url!r}>"


# ---------------------------------------------------------------------------
# agent_logs
# ---------------------------------------------------------------------------


class AgentLog(Base):
    """Execution record for one agent invocation within a session."""

    __tablename__ = "agent_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
        nullable=False,
    )

    # Relationships
    session: Mapped[ResearchSession] = relationship(
        "ResearchSession",
        back_populates="agent_logs",
    )

    def __repr__(self) -> str:
        return f"<AgentLog agent={self.agent_name!r} session={self.session_id}>"
