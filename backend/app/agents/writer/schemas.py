"""
Data contracts for the Writer Agent.

Three categories:
1. ``WriterAgentState``   — LangGraph TypedDict flowing between nodes.
2. Structured-output models — Pydantic models used with ``.with_structured_output()``.
3. ``WriterAgentOutput``  — Final result returned by ``WriterAgent.run()``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, computed_field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# LangGraph state
# ---------------------------------------------------------------------------


class WriterAgentState(TypedDict):
    query: str
    session_id: str
    mode: Literal["general", "phd"]
    findings: list[dict[str, Any]]
    citation_map: list[dict[str, Any]]
    outline: ReportOutline | None
    report: Report | None
    status: Literal["outlining", "writing", "complete", "failed"]
    error: str | None


# ---------------------------------------------------------------------------
# Structured-output models
# ---------------------------------------------------------------------------


class EvidenceGroup(BaseModel):
    """Maps a thematic body section heading to its supporting finding indices."""

    heading: Annotated[
        str,
        Field(description="Thematic section heading, e.g. 'Transformer-based Architectures'."),
    ]
    finding_indices: Annotated[
        list[int],
        Field(
            description=(
                "Zero-based indices from the input findings list that belong to this section. "
                "Must contain at least one index."
            )
        ),
    ]


class ReportOutline(BaseModel):
    """High-level blueprint for the literature review produced by the outline node."""

    title: Annotated[
        str,
        Field(description="Concise, academic title for the literature review (under 15 words)."),
    ]
    thesis_statement: Annotated[
        str,
        Field(
            description=(
                "One or two sentences summarising the current state of the research or the "
                "central argument the review will make. Placed at the end of the introduction."
            )
        ),
    ]
    introduction_points: Annotated[
        list[str],
        Field(
            min_length=3,
            description=(
                "3–6 bullet points the Introduction must cover: topic definition, background "
                "context, purpose of the review, and the thesis statement."
            ),
        ),
    ]
    key_themes: Annotated[
        list[str],
        Field(
            min_length=2,
            description=(
                "Overarching themes the findings cluster around. "
                "2–3 themes for general mode; 3–5 themes for PhD mode."
            ),
        ),
    ]
    evidence_groups: Annotated[
        list[EvidenceGroup],
        Field(
            min_length=2,
            description=(
                "How findings should be grouped into thematic body sections. "
                "2–3 groups for general mode; 3–5 groups for PhD mode. "
                "Every finding index must appear in exactly one group. "
                "Each section should compare and contrast multiple sources."
            ),
        ),
    ]
    synthesis_points: Annotated[
        list[str],
        Field(
            min_length=2,
            description=(
                "2–5 points the Synthesis section must make about how the literature "
                "collectively advances the field."
            ),
        ),
    ]
    research_gaps: Annotated[
        list[str],
        Field(
            min_length=2,
            description="2–5 identified gaps or unresolved questions in the literature.",
        ),
    ]


class BodySection(BaseModel):
    """A fully written thematic body section."""

    heading: Annotated[str, Field(description="Section heading matching the outline.")]
    body: Annotated[
        str,
        Field(
            description=(
                "Analytical prose for this thematic section. "
                "Compare and contrast how different studies approach the topic. "
                "Identify patterns, trends, and contradictions. "
                "Discuss state-of-the-art methods and their nuances. "
                "Every factual sentence must carry at least one inline [N] citation."
            )
        ),
    ]
    citation_numbers: Annotated[
        list[int],
        Field(description="All citation [N] numbers referenced in this section's body."),
    ]


class PhDAnnotations(BaseModel):
    """PhD-mode supplementary analysis appended below the main literature review."""

    state_of_art_analysis: Annotated[
        str,
        Field(
            description=(
                "200–300 words. Identify and critically evaluate the current state-of-the-art "
                "methods and papers in the field. Name specific approaches, benchmarks, and "
                "performance metrics where available. Include inline [N] citations."
            )
        ),
    ]
    future_possibilities: Annotated[
        str,
        Field(
            description=(
                "150–250 words. Synthesise what the surveyed literature suggests as the most "
                "promising future research directions, open problems, and underexplored areas. "
                "Include inline [N] citations where papers explicitly discuss future work."
            )
        ),
    ]
    topic_overlap_and_inform: Annotated[
        str,
        Field(
            description=(
                "150–250 words. Analyse how the student's specific research topic overlaps with, "
                "builds on, or is informed by the existing literature. Highlight which existing "
                "methods or findings are most directly relevant."
            )
        ),
    ]
    novelty_assessment: Annotated[
        str,
        Field(
            description=(
                "100–200 words. Assess the novelty of the student's research topic relative to "
                "the surveyed literature. Identify what, if anything, appears to be genuinely "
                "new, underexplored, or differentiated from existing work."
            )
        ),
    ]
    current_researchers: Annotated[
        str,
        Field(
            description=(
                "150–250 words. Identify the key research groups, institutions, and individual "
                "researchers actively working on this topic. Describe the current status of their "
                "work based on the surveyed sources. Include inline [N] citations."
            )
        ),
    ]


class Report(BaseModel):
    """Complete literature review produced by the write node."""

    title: Annotated[str, Field(description="Literature review title from the outline.")]
    introduction: Annotated[
        str,
        Field(
            description=(
                "Formal academic prose introduction. "
                "Define the topic, provide background context, establish scope. "
                "End with the thesis statement summarising the current state of the research. "
                "No inline citations."
            )
        ),
    ]
    body_sections: Annotated[
        list[BodySection],
        Field(
            min_length=2,
            description=(
                "One section per thematic group defined in the outline. "
                "Each section compares, contrasts, and critiques how different studies "
                "approach the topic, identifying patterns, trends, and contradictions."
            ),
        ),
    ]
    synthesis: Annotated[
        str,
        Field(
            description=(
                "Integrative synthesis showing how the body sections collectively advance the field. "
                "Do not summarise individual sources — synthesise across them. "
                "Include inline [N] citations."
            )
        ),
    ]
    conclusion: Annotated[
        str,
        Field(
            description=(
                "Conclusion covering major insights, research gaps, and future directions. "
                "No inline citations."
            )
        ),
    ]
    phd_annotations: PhDAnnotations | None = Field(
        default=None,
        description="PhD-mode supplementary analysis. None in general mode.",
    )

    @computed_field  # type: ignore[misc]
    @property
    def word_count(self) -> int:
        parts = [
            self.introduction,
            *[s.body for s in self.body_sections],
            self.synthesis,
            self.conclusion,
        ]
        if self.phd_annotations:
            a = self.phd_annotations
            parts += [
                a.state_of_art_analysis,
                a.future_possibilities,
                a.topic_overlap_and_inform,
                a.novelty_assessment,
                a.current_researchers,
            ]
        return sum(len(p.split()) for p in parts)


# ---------------------------------------------------------------------------
# Citation type (assembled by the writer, not produced by the LLM)
# ---------------------------------------------------------------------------


class ProseSection(BaseModel):
    """Plain prose for introduction, synthesis, and conclusion (no citation tracking needed)."""

    text: Annotated[str, Field(description="The full written prose for this section.")]


class ReportCitation(BaseModel):
    number: int
    source_url: str
    source_type: Literal["rag", "web"]


# ---------------------------------------------------------------------------
# Final agent output
# ---------------------------------------------------------------------------


class WriterAgentOutput(BaseModel):
    report: Report
    citations: list[ReportCitation]
    session_id: str
