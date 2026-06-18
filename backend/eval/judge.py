"""
Independent LLM-as-judge for evaluating research reports.

Scores each report on four dimensions (1–5) using a separate LLM call that
has no access to the Critic agent's self-reported quality_score, ensuring the
evaluation is independent of the pipeline being measured.

The judge receives:
- The original research question
- The full report text (title + all sections)
- The citation count (structural signal, not the URLs themselves)

It does NOT receive:
- The self-reported quality_score
- Which iteration produced the report
- The other report in the pair (to avoid ordering/anchoring bias)
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from app.llm import LLMMessage, get_llm_client
from eval.schemas import JudgeScore

_SYSTEM_PROMPT = """\
You are an expert academic evaluator assessing AI-generated research reports.
Your role is to score each report strictly and independently.
Do NOT consider report length as a proxy for quality — depth matters, not verbosity.
Do NOT be lenient: reserve scores of 5 for genuinely excellent work.
"""

_RUBRIC = """\
SCORING RUBRIC (score each dimension 1–5):

factual_coverage
  1 = Highly superficial; misses most key aspects of the topic
  2 = Covers only obvious surface points; important subtopics absent
  3 = Covers major points but skips important mechanisms or nuances
  4 = Good coverage with only minor gaps
  5 = Comprehensive; covers mechanisms, current state, key findings, and debates

citation_groundedness
  1 = Barely any citations; nearly all claims unattributed
  2 = A few citations but most factual claims lack support
  3 = Some claims cited but notable gaps; attribution inconsistent
  4 = Most claims cited; minor omissions
  5 = Nearly every factual claim has a citation; evidence well-attributed throughout

coherence
  1 = Disjointed; hard to follow; no logical flow
  2 = Rough structure but significant logical gaps or repetition
  3 = Reasonable flow but some structural issues or abrupt transitions
  4 = Well-organized; minor rough edges
  5 = Excellent structure; clear logical progression; synthesis integrates findings naturally

gap_closure
  1 = Barely answers the research question; key aspects ignored
  2 = Addresses the question superficially; major gaps remain
  3 = Partially answers the question; some important angles missing
  4 = Mostly answers the question with only minor gaps
  5 = Fully addresses the question; explicitly identifies and discusses remaining gaps
"""

_USER_TEMPLATE = """\
Research question: {query}

Number of citations in report: {citation_count}

Report text:
---
{report_text}
---

Score the above report on the four rubric dimensions and provide 2–3 sentences of reasoning.
"""


def _format_report_text(report_dict: dict) -> str:
    """Flatten a serialised Report dict into plain readable text."""
    parts: list[str] = []

    title = report_dict.get("title", "Untitled")
    parts.append(f"TITLE: {title}\n")

    intro = report_dict.get("introduction", "")
    if intro:
        parts.append(f"INTRODUCTION:\n{intro}\n")

    for section in report_dict.get("body_sections", []):
        heading = section.get("heading", "")
        body = section.get("body", "")
        parts.append(f"SECTION — {heading}:\n{body}\n")

    synthesis = report_dict.get("synthesis", "")
    if synthesis:
        parts.append(f"SYNTHESIS:\n{synthesis}\n")

    conclusion = report_dict.get("conclusion", "")
    if conclusion:
        parts.append(f"CONCLUSION:\n{conclusion}\n")

    return "\n".join(parts)


class _JudgeOutput(BaseModel):
    """Structured output schema for the LLM judge."""

    factual_coverage: int
    citation_groundedness: int
    coherence: int
    gap_closure: int
    reasoning: str

    @field_validator("factual_coverage", "citation_groundedness", "coherence", "gap_closure")
    @classmethod
    def clamp_score(cls, v: int) -> int:
        return max(1, min(5, v))


async def score_report(
    query: str,
    report_dict: dict,
    citation_count: int,
) -> JudgeScore:
    """Score a single report using an independent LLM call.

    Args:
        query: The original research question.
        report_dict: Serialised Report dict (from WorkflowOutput.report.model_dump()).
        citation_count: Number of citations in the report.

    Returns:
        JudgeScore with per-dimension scores (1–5) and reasoning.
    """
    client = get_llm_client()
    report_text = _format_report_text(report_dict)

    user_content = _USER_TEMPLATE.format(
        query=query,
        citation_count=citation_count,
        report_text=report_text,
    )

    output: _JudgeOutput = await client.complete_structured(
        messages=[LLMMessage(role="human", content=user_content)],
        schema=_JudgeOutput,
        system_prompt=_SYSTEM_PROMPT + "\n\n" + _RUBRIC,
    )

    return JudgeScore(
        factual_coverage=output.factual_coverage,
        citation_groundedness=output.citation_groundedness,
        coherence=output.coherence,
        gap_closure=output.gap_closure,
        reasoning=output.reasoning,
    )
