"""
Writer Agent public API.

Import from here::

    from app.agents.writer import WriterAgent, WriterAgentOutput, Report, ReportCitation
"""

from app.agents.writer.graph import WriterAgent
from app.agents.writer.schemas import (
    BodySection,
    PhDAnnotations,
    ProseSection,
    Report,
    ReportCitation,
    WriterAgentOutput,
    WriterAgentState,
)

__all__ = [
    "WriterAgent",
    "WriterAgentOutput",
    "WriterAgentState",
    "Report",
    "ReportCitation",
    "BodySection",
    "PhDAnnotations",
    "ProseSection",
]
