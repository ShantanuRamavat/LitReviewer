"""
Request / response schemas for the research API.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class StartResearchRequest(BaseModel):
    """Body for POST /research/start."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=2000,
        description="The research question.",
    )
    mode: str = Field(
        default="general",
        description="'general' for a standard literature review, 'phd' for PhD-level analysis.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class ResearchSessionResponse(BaseModel):
    """Returned by GET /research/{session_id} and POST /research/start."""

    session_id: uuid.UUID
    query: str
    status: str
    report_id: uuid.UUID | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class BodySectionResponse(BaseModel):
    heading: str
    body: str
    citation_numbers: list[int]


class PhDAnnotationsResponse(BaseModel):
    state_of_art_analysis: str
    future_possibilities: str
    topic_overlap_and_inform: str
    novelty_assessment: str
    current_researchers: str


class ReportContentResponse(BaseModel):
    body_sections: list[BodySectionResponse]
    synthesis: str
    conclusion: str
    phd_annotations: PhDAnnotationsResponse | None = None


class CitationResponse(BaseModel):
    number: int
    source_url: str
    source_type: str


class ReportResponse(BaseModel):
    """Returned by GET /reports/{report_id}."""

    id: uuid.UUID
    session_id: uuid.UUID
    title: str
    introduction: str
    content: ReportContentResponse
    word_count: int
    quality_score: float | None = None
    citations: list[CitationResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class HistoryItemResponse(BaseModel):
    """One item in the GET /history list."""

    session_id: uuid.UUID
    query: str
    status: str
    report_id: uuid.UUID | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    items: list[HistoryItemResponse]
    total: int
    page: int
    limit: int
