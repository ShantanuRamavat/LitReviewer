"""Data contracts for the FactChecker Agent."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class FactCheckerAgentState(TypedDict):
    """Mutable state passed between FactChecker nodes."""

    query: str
    session_id: str
    findings: list[dict[str, Any]]
    verification_context: list[dict[str, Any]]  # web results from verification queries
    verified_findings: list[dict[str, Any]]
    status: Literal["searching", "assessing", "complete", "failed"]
    error: str | None


class VerifiedFinding(BaseModel):
    """A research finding annotated with fact-check results."""

    text: Annotated[str, Field(description="The original finding text.")]
    source_url: Annotated[str, Field(description="Original source URL.")]
    relevance_score: Annotated[float, Field(ge=0.0, le=1.0)]
    source_type: Annotated[Literal["rag", "web"], Field(description="'rag' or 'web'.")]
    query_used: Annotated[str, Field(description="Search query that produced this finding.")]
    verified: Annotated[
        bool,
        Field(description="True if the claim is supported by reliable sources."),
    ]
    confidence: Annotated[
        float,
        Field(
            ge=0.0,
            le=1.0,
            description=(
                "Confidence in the finding: 0.9+ = strongly confirmed, "
                "0.6–0.89 = likely correct, 0.3–0.59 = uncertain, below 0.3 = disputed."
            ),
        ),
    ]
    verification_note: Annotated[
        str,
        Field(description="One sentence explaining the verification result."),
    ]


class VerifiedFindingList(BaseModel):
    """LLM structured output from the assess node."""

    findings: Annotated[
        list[VerifiedFinding],
        Field(description="All input findings annotated with verification results."),
    ]


class FactCheckerOutput(BaseModel):
    """Result returned by FactCheckerAgent.run()."""

    verified_findings: list[VerifiedFinding]
    total_input: int
    total_verified: int
    total_uncertain: int
    total_disputed: int
