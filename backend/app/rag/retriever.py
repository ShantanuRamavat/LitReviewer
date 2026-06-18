"""
Vector similarity retriever backed by Qdrant.

``retrieve()`` is the single entry point used by agents.  It:
1. Embeds the query with the BGE query prefix via ``Embedder.embed_query()``.
2. Performs cosine-similarity search against the ``research_docs`` collection.
3. Optionally filters results to a specific research session.
4. Returns ranked ``RetrievalResult`` objects ready for prompt injection.

Session scoping
---------------
When ``query.session_id`` is non-empty, a Qdrant filter is applied so only
chunks tagged with that session are returned.  This prevents cross-session
contamination when multiple research sessions are running concurrently.

Passing an empty ``session_id`` searches across all sessions — useful for
cross-session exploratory queries (future feature).
"""

import logging

from qdrant_client import models as qdrant_models

from app.config import Settings, get_settings
from app.db.qdrant.client import get_qdrant_client
from app.rag.embedder import get_embedder
from app.rag.schemas import RetrievalQuery, RetrievalResult

logger = logging.getLogger(__name__)


async def retrieve(
    query: RetrievalQuery,
    *,
    settings: Settings | None = None,
) -> list[RetrievalResult]:
    """Search Qdrant for chunks relevant to ``query``.

    Args:
        query: Retrieval parameters including query text, session scope, and k.
        settings: Application settings; defaults to the cached singleton.

    Returns:
        Up to ``query.k`` ``RetrievalResult`` objects sorted by descending
        cosine similarity score.  May be fewer than ``k`` if the collection
        contains fewer matching points.
    """
    if settings is None:
        settings = get_settings()

    embedder = get_embedder()
    query_vector = await embedder.embed_query(query.text)

    search_filter = _build_filter(query.session_id)

    client = get_qdrant_client()
    hits = await client.search(
        collection_name=settings.qdrant_collection_name,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=query.k,
        with_payload=True,
        score_threshold=None,
    )

    results = [_hit_to_result(hit) for hit in hits]

    logger.debug(
        "Retrieval complete.",
        extra={
            "query_length": len(query.text),
            "session_id": query.session_id or "global",
            "k": query.k,
            "returned": len(results),
        },
    )

    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _build_filter(session_id: str) -> qdrant_models.Filter | None:
    """Build a Qdrant filter for session scoping, or return None for global."""
    if not session_id:
        return None

    return qdrant_models.Filter(
        must=[
            qdrant_models.FieldCondition(
                key="session_id",
                match=qdrant_models.MatchValue(value=session_id),
            )
        ]
    )


def _hit_to_result(hit: qdrant_models.ScoredPoint) -> RetrievalResult:
    """Convert a Qdrant ``ScoredPoint`` to a ``RetrievalResult``."""
    payload = hit.payload or {}
    return RetrievalResult(
        text=str(payload.get("text", "")),
        source_url=str(payload.get("source_url", "")),
        score=float(hit.score),
        chunk_index=int(payload.get("chunk_index", 0)),
        session_id=str(payload.get("session_id", "")),
    )
