"""Data contracts for the Critic Agent."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class CriticAgentState(TypedDict):
    """Mutable state passed between Critic nodes."""

    query: str
    session_id: str
    iteration: int
    verified_findings: list[dict[str, Any]]
    critique: CritiqueOutput | None
    status: Literal["critiquing", "complete", "failed"]
    error: str | None


class CritiqueOutput(BaseModel):
    """LLM structured output from the critique node."""

    quality_score: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description=(
                "Overall research quality: 0.9+ excellent, 0.7–0.89 good (sufficient), "
                "0.4–0.69 fair (needs more), below 0.4 poor."
            ),
        ),
    ]
    coverage_score: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description="How completely the research covers all relevant angles of the query.",
        ),
    ]
    gaps: Annotated[
        list[str],
        Field(description="Specific topics, angles, or facts that are missing or under-researched."),
    ]
    strengths: Annotated[
        list[str],
        Field(description="What the research covers well."),
    ]
    is_sufficient: Annotated[
        bool,
        Field(
            description=(
                "True if quality_score >= 0.7 AND coverage_score >= 0.6. "
                "Set to True if iteration >= 2 regardless of scores."
            )
        ),
    ]
    suggestions: Annotated[
        list[str],
        Field(
            description=(
                "If is_sufficient is False: 2–4 specific search queries that would fill the gaps. "
                "If is_sufficient is True: empty list."
            )
        ),
    ]


class CriticOutput(BaseModel):
    """Result returned by CriticAgent.run()."""

    critique: CritiqueOutput
    quality_score: float
    is_sufficient: bool
    suggestions: list[str]
