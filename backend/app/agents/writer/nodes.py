"""
LangGraph node functions for the Writer Agent.

Node execution order:
    outline_node → write_node

write_node makes one LLM call per section (mode-aware word budgets):

  PhD mode (10,000–20,000 words):
    1. Introduction       ~10%    (~1,000–2,000 words)
    2. Body sections × N  70–80%  (~2,000–3,500 words each, 3–5 sections)
    3. Synthesis          ~5–8%   (~700–1,000 words)
    4. Conclusion         12–15%  (~1,200–2,500 words)
    5. PhD Annotations    supplementary

  General mode (3,000–5,000 words):
    1. Introduction       ~10%    (~300–500 words)
    2. Body sections × N  70–80%  (~700–1,200 words each, 2–3 sections)
    3. Synthesis          ~5%     (~150–250 words)
    4. Conclusion         12–15%  (~400–650 words)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agents.base import ainvoke_with_retry
from app.agents.writer.prompts import (
    BODY_SECTION_GENERAL_SYSTEM_PROMPT,
    BODY_SECTION_PHD_SYSTEM_PROMPT,
    CONCLUSION_GENERAL_SYSTEM_PROMPT,
    CONCLUSION_PHD_SYSTEM_PROMPT,
    INTRO_GENERAL_SYSTEM_PROMPT,
    INTRO_PHD_SYSTEM_PROMPT,
    OUTLINER_PHD_SYSTEM_PROMPT,
    OUTLINER_SYSTEM_PROMPT,
    PHD_ANNOTATIONS_SYSTEM_PROMPT,
    SYNTHESIS_GENERAL_SYSTEM_PROMPT,
    SYNTHESIS_PHD_SYSTEM_PROMPT,
)
from app.agents.writer.schemas import (
    BodySection,
    PhDAnnotations,
    ProseSection,
    Report,
    ReportCitation,
    ReportOutline,
    WriterAgentState,
)
from app.llm import get_model_for_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node 1 — Outliner
# ---------------------------------------------------------------------------


async def outline_node(state: WriterAgentState) -> dict[str, Any]:
    findings = state["findings"]
    mode = state.get("mode", "general")

    logger.info(
        "WriterAgent: outlining.",
        extra={"session_id": state["session_id"], "num_findings": len(findings), "mode": mode},
    )

    citation_map = _build_citation_map(findings)

    if not findings:
        logger.warning("WriterAgent: no findings provided; cannot outline.", extra={"session_id": state["session_id"]})
        return {"citation_map": citation_map, "status": "failed", "error": "No findings provided to WriterAgent."}

    findings_text = _format_findings_for_prompt(findings, citation_map)
    system_prompt = OUTLINER_PHD_SYSTEM_PROMPT if mode == "phd" else OUTLINER_SYSTEM_PROMPT

    try:
        model = get_model_for_agent("writer").with_structured_output(ReportOutline)

        outline: ReportOutline = await ainvoke_with_retry(
            model,
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "human",
                    "content": (
                        f"Research query: {state['query']}\n\n"
                        f"Research findings:\n{findings_text}"
                    ),
                },
            ],
        )

        logger.info(
            "WriterAgent: outline ready.",
            extra={
                "session_id": state["session_id"],
                "title": outline.title,
                "themes": len(outline.key_themes),
                "body_sections": len(outline.evidence_groups),
            },
        )

        return {"citation_map": citation_map, "outline": outline, "status": "writing"}

    except Exception as exc:
        logger.error("WriterAgent: outline failed: %s", exc, extra={"session_id": state["session_id"]})
        return {"citation_map": citation_map, "status": "failed", "error": f"Outline failed: {exc}"}


# ---------------------------------------------------------------------------
# Node 2 — Writer  (sectional: one LLM call per section)
# ---------------------------------------------------------------------------


async def write_node(state: WriterAgentState) -> dict[str, Any]:
    outline = state["outline"]
    citation_map = state["citation_map"]
    findings = state["findings"]
    mode = state.get("mode", "general")

    logger.info(
        "WriterAgent: writing (sectional mode).",
        extra={
            "session_id": state["session_id"],
            "title": outline.title if outline else "unknown",
            "mode": mode,
            "sections": len(outline.evidence_groups) if outline else 0,
        },
    )

    if not outline:
        return {"status": "failed", "error": "No outline available for write node."}

    citation_list_text = _format_citation_list(citation_map)
    outline_text = _format_outline_for_prompt(outline)

    intro_prompt = INTRO_PHD_SYSTEM_PROMPT if mode == "phd" else INTRO_GENERAL_SYSTEM_PROMPT
    body_prompt = BODY_SECTION_PHD_SYSTEM_PROMPT if mode == "phd" else BODY_SECTION_GENERAL_SYSTEM_PROMPT
    synthesis_prompt = SYNTHESIS_PHD_SYSTEM_PROMPT if mode == "phd" else SYNTHESIS_GENERAL_SYSTEM_PROMPT
    conclusion_prompt = CONCLUSION_PHD_SYSTEM_PROMPT if mode == "phd" else CONCLUSION_GENERAL_SYSTEM_PROMPT

    try:
        # ------------------------------------------------------------------
        # 1. Introduction
        # ------------------------------------------------------------------
        logger.info("WriterAgent: writing introduction.", extra={"session_id": state["session_id"]})
        intro_model = get_model_for_agent("writer").with_structured_output(ProseSection)
        intro_result: ProseSection = await ainvoke_with_retry(
            intro_model,
            [
                {"role": "system", "content": intro_prompt},
                {
                    "role": "human",
                    "content": (
                        f"Research query: {state['query']}\n\n"
                        f"Outline:\n{outline_text}\n\n"
                        f"Citation sources (for context only — no citations in introduction):\n{citation_list_text}"
                    ),
                },
            ],
        )
        introduction = intro_result.text

        # ------------------------------------------------------------------
        # 2. Body sections — all sections run concurrently
        # ------------------------------------------------------------------
        n_sections = len(outline.evidence_groups)
        logger.info(
            "WriterAgent: writing %d body sections in parallel.",
            n_sections,
            extra={"session_id": state["session_id"]},
        )

        async def _write_section(i: int) -> BodySection:
            group = outline.evidence_groups[i]
            relevant_findings = [findings[idx] for idx in group.finding_indices if idx < len(findings)]
            relevant_findings_text = _format_findings_for_prompt(relevant_findings, citation_map)
            theme_index = i if i < len(outline.key_themes) else 0
            related_themes = "\n".join(
                f"- {t}" for j, t in enumerate(outline.key_themes) if j != theme_index
            )
            logger.info(
                "WriterAgent: starting body section %d/%d — '%s' [%d findings]",
                i + 1, n_sections, group.heading,
                len(relevant_findings),
                extra={"session_id": state["session_id"]},
            )
            model = get_model_for_agent("writer").with_structured_output(BodySection)
            section: BodySection = await ainvoke_with_retry(
                model,
                [
                    {"role": "system", "content": body_prompt},
                    {
                        "role": "human",
                        "content": (
                            f"Research query: {state['query']}\n\n"
                            f"Section heading: {group.heading}\n\n"
                            f"Thesis statement: {outline.thesis_statement}\n\n"
                            f"Other themes in this review (for cross-referencing):\n{related_themes}\n\n"
                            f"Research findings relevant to this section:\n{relevant_findings_text}\n\n"
                            f"Full citation source list:\n{citation_list_text}"
                        ),
                    },
                ],
            )
            if section.heading.strip() == "":
                section = BodySection(
                    heading=group.heading,
                    body=section.body,
                    citation_numbers=section.citation_numbers,
                )
            logger.info(
                "WriterAgent: body section %d/%d done — %d words.",
                i + 1, n_sections, len(section.body.split()),
                extra={"session_id": state["session_id"]},
            )
            return section

        body_sections: list[BodySection] = list(
            await asyncio.gather(*[_write_section(i) for i in range(n_sections)])
        )

        # ------------------------------------------------------------------
        # 3. Synthesis
        # ------------------------------------------------------------------
        logger.info("WriterAgent: writing synthesis.", extra={"session_id": state["session_id"]})
        synth_model = get_model_for_agent("writer").with_structured_output(ProseSection)

        sections_overview = "\n\n".join(
            f"Section '{s.heading}' (first 400 chars):\n{s.body[:400]}…"
            for s in body_sections
        )
        synthesis_points_text = "\n".join(f"- {p}" for p in outline.synthesis_points)

        synth_result: ProseSection = await ainvoke_with_retry(
            synth_model,
            [
                {"role": "system", "content": synthesis_prompt},
                {
                    "role": "human",
                    "content": (
                        f"Research query: {state['query']}\n\n"
                        f"Thesis statement: {outline.thesis_statement}\n\n"
                        f"Synthesis points to integrate:\n{synthesis_points_text}\n\n"
                        f"Body sections overview:\n{sections_overview}\n\n"
                        f"Citation sources:\n{citation_list_text}"
                    ),
                },
            ],
        )
        synthesis = synth_result.text

        # ------------------------------------------------------------------
        # 4. Conclusion
        # ------------------------------------------------------------------
        logger.info("WriterAgent: writing conclusion.", extra={"session_id": state["session_id"]})
        concl_model = get_model_for_agent("writer").with_structured_output(ProseSection)

        gaps_text = "\n".join(f"- {g}" for g in outline.research_gaps)
        themes_text = "\n".join(f"- {t}" for t in outline.key_themes)

        concl_result: ProseSection = await ainvoke_with_retry(
            concl_model,
            [
                {"role": "system", "content": conclusion_prompt},
                {
                    "role": "human",
                    "content": (
                        f"Research query: {state['query']}\n\n"
                        f"Thesis statement: {outline.thesis_statement}\n\n"
                        f"Key themes covered:\n{themes_text}\n\n"
                        f"Research gaps identified in the outline:\n{gaps_text}\n\n"
                        f"Synthesis points:\n{synthesis_points_text}"
                    ),
                },
            ],
        )
        conclusion = concl_result.text

        # ------------------------------------------------------------------
        # 5. PhD Annotations (PhD mode only)
        # ------------------------------------------------------------------
        phd_annotations: PhDAnnotations | None = None
        if mode == "phd":
            logger.info("WriterAgent: writing PhD annotations.", extra={"session_id": state["session_id"]})
            phd_model = get_model_for_agent("writer").with_structured_output(PhDAnnotations)
            all_findings_text = _format_findings_for_prompt(findings, citation_map)

            phd_annotations = await ainvoke_with_retry(
                phd_model,
                [
                    {"role": "system", "content": PHD_ANNOTATIONS_SYSTEM_PROMPT},
                    {
                        "role": "human",
                        "content": (
                            f"PhD student's research topic: {state['query']}\n\n"
                            f"Research findings:\n{all_findings_text}\n\n"
                            f"Citation sources:\n{citation_list_text}"
                        ),
                    },
                ],
            )

        # ------------------------------------------------------------------
        # Assemble report
        # ------------------------------------------------------------------
        report = Report(
            title=outline.title,
            introduction=introduction,
            body_sections=body_sections,
            synthesis=synthesis,
            conclusion=conclusion,
            phd_annotations=phd_annotations,
        )

        logger.info(
            "WriterAgent: report written.",
            extra={
                "session_id": state["session_id"],
                "title": report.title,
                "word_count": report.word_count,
                "body_sections": len(report.body_sections),
                "has_phd_annotations": report.phd_annotations is not None,
            },
        )

        return {"report": report, "status": "complete"}

    except Exception as exc:
        logger.error("WriterAgent: write failed: %s", exc, extra={"session_id": state["session_id"]})
        return {"status": "failed", "error": f"Writing failed: {exc}"}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_citation_map(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[str, int] = {}
    result: list[dict[str, Any]] = []
    counter = 1
    for finding in findings:
        url = str(finding.get("source_url", ""))
        if not url or url in seen:
            continue
        seen[url] = counter
        result.append({"number": counter, "source_url": url, "source_type": str(finding.get("source_type", "web"))})
        counter += 1
    return result


def _format_findings_for_prompt(findings: list[dict[str, Any]], citation_map: list[dict[str, Any]]) -> str:
    url_to_number = {e["source_url"]: e["number"] for e in citation_map}
    lines: list[str] = []
    for idx, finding in enumerate(findings):
        url = str(finding.get("source_url", ""))
        citation_num = url_to_number.get(url, "?")
        score = finding.get("relevance_score", 0.0)
        text = str(finding.get("text", ""))[:1200]
        lines.append(f"[Finding {idx}] [Cite as: {citation_num}] (relevance: {score:.2f}) — {url}\n{text}")
    return "\n\n".join(lines)


def _format_citation_list(citation_map: list[dict[str, Any]]) -> str:
    return "\n".join(f"[{e['number']}] ({e['source_type']}) {e['source_url']}" for e in citation_map)


def _format_outline_for_prompt(outline: ReportOutline) -> str:
    lines = [
        f"Title: {outline.title}",
        "",
        f"Thesis statement: {outline.thesis_statement}",
        "",
        "Introduction must cover:",
        *[f"  - {p}" for p in outline.introduction_points],
        "",
        "Key themes:",
        *[f"  - {t}" for t in outline.key_themes],
        "",
        "Body sections:",
    ]
    for group in outline.evidence_groups:
        indices = ", ".join(str(i) for i in group.finding_indices)
        lines.append(f"  Section '{group.heading}' — findings: [{indices}]")
    lines += [
        "",
        "Synthesis must cover:",
        *[f"  - {p}" for p in outline.synthesis_points],
        "",
        "Research gaps (for conclusion):",
        *[f"  - {g}" for g in outline.research_gaps],
    ]
    return "\n".join(lines)
