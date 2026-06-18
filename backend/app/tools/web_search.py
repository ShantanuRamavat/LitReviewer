"""
Tavily web search tool.

Wraps the Tavily async client with:
- Structured ``WebSearchResult`` return type
- Per-call retry (2 attempts, 1 s fixed wait) for transient network errors
- Graceful empty-list return on all failures so callers never crash

The client is created lazily per call — Tavily's ``AsyncTavilyClient`` is
lightweight and stateless, so there is no benefit to a singleton here.
"""

import logging
from dataclasses import dataclass

from tavily import AsyncTavilyClient
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class WebSearchResult:
    """A single result returned by the Tavily search API.

    Attributes:
        title: Page title.
        url: Canonical URL of the result.
        content: Extracted text snippet from the page.
        score: Relevance score assigned by Tavily (0.0–1.0).
    """

    title: str
    url: str
    content: str
    score: float


async def web_search(
    query: str,
    *,
    settings: Settings | None = None,
) -> list[WebSearchResult]:
    """Search the web using Tavily and return structured results.

    On any error the function logs a warning and returns an empty list so
    callers (LangGraph nodes) can treat a failed search as zero results rather
    than an exception that aborts the graph.

    Args:
        query: Natural-language search query.
        settings: Application settings; defaults to the cached singleton.

    Returns:
        Up to ``settings.tavily_max_results`` ``WebSearchResult`` objects
        sorted by Tavily's relevance score (descending).  Empty list on error.
    """
    if settings is None:
        settings = get_settings()

    if not settings.tavily_api_key.get_secret_value():
        logger.warning("Tavily API key not configured; skipping web search.")
        return []

    try:
        return await _search_with_retry(query, settings)
    except Exception as exc:
        logger.warning(
            "Web search failed after retries; returning empty results.",
            extra={"query": query, "error": str(exc)},
        )
        return []


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(2),
    wait=wait_fixed(1),
    reraise=True,
)
async def _search_with_retry(query: str, settings: Settings) -> list[WebSearchResult]:
    """Execute one Tavily search with a single retry on failure."""
    client = AsyncTavilyClient(api_key=settings.tavily_api_key.get_secret_value())

    response = await client.search(
        query=query,
        max_results=settings.tavily_max_results,
        search_depth="advanced",
        include_answer=False,
    )

    results = []
    for hit in response.get("results", []):
        results.append(
            WebSearchResult(
                title=str(hit.get("title", "")),
                url=str(hit.get("url", "")),
                content=str(hit.get("content", "")),
                score=float(hit.get("score", 0.0)),
            )
        )

    logger.debug(
        "Web search complete.",
        extra={"query": query, "results": len(results)},
    )
    return results
