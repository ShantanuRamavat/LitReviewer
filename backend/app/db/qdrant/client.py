"""
Qdrant async client singleton.

The ``AsyncQdrantClient`` is created once during startup (``init_qdrant_client``)
and shared for the lifetime of the process.  The vector collection is
bootstrapped by ``ensure_collection_exists``, which is also called at startup.

Qdrant collection design:
- Collection name : ``research_docs`` (configurable via settings)
- Vector size     : 1 024 dimensions (BAAI/bge-large-en-v1.5)
- Distance metric : Cosine (suitable for normalised embeddings)
- HNSW index      : m=16, ef_construct=100 (Qdrant defaults, good to 1 M vectors)

Payload fields stored alongside each vector point:
- ``session_id``  : UUID of the research session (keyword, filterable)
- ``source_url``  : Origin URL of the source document (keyword, filterable)
- ``chunk_index`` : Position of the chunk within the source document (integer)
- ``text``        : Full chunk text for context injection into agent prompts
- ``ingested_at`` : ISO-8601 timestamp of ingestion (datetime)
"""

import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant_models

from app.config import Settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None

# Embedding dimensions for BAAI/bge-large-en-v1.5
_VECTOR_SIZE = 1024
_DISTANCE = qdrant_models.Distance.COSINE


def init_qdrant_client(settings: Settings) -> None:
    """Create and cache the ``AsyncQdrantClient`` singleton.

    Should be called once during application startup.  Calling it a second
    time raises a ``RuntimeError`` to prevent accidental double-initialisation.

    Args:
        settings: Validated application settings.

    Raises:
        RuntimeError: If the client has already been initialised.
    """
    global _client

    if _client is not None:
        raise RuntimeError("Qdrant client is already initialised.")

    _client = AsyncQdrantClient(url=settings.qdrant_url)
    logger.info("Qdrant async client initialised.", extra={"url": settings.qdrant_url})


def get_qdrant_client() -> AsyncQdrantClient:
    """Return the cached Qdrant client.

    Returns:
        The ``AsyncQdrantClient`` singleton.

    Raises:
        RuntimeError: If ``init_qdrant_client`` has not been called yet.
    """
    if _client is None:
        raise RuntimeError(
            "Qdrant client is not initialised. "
            "Ensure init_qdrant_client() is called during application startup."
        )
    return _client


async def ensure_collection_exists(settings: Settings) -> None:
    """Create the research_docs collection if it does not already exist.

    This function is idempotent — it checks whether the collection exists
    before attempting to create it, so it is safe to call on every startup.

    The HNSW index parameters are tuned for the MVP scale (up to ~500 K
    vectors).  Increase ``m`` and ``ef_construct`` for larger datasets.

    Args:
        settings: Validated application settings providing the collection name.
    """
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection_name

    existing = await client.get_collections()
    existing_names = {c.name for c in existing.collections}

    if collection_name in existing_names:
        logger.info("Qdrant collection already exists.", extra={"collection": collection_name})
        return

    await client.create_collection(
        collection_name=collection_name,
        vectors_config=qdrant_models.VectorParams(
            size=_VECTOR_SIZE,
            distance=_DISTANCE,
            # on_disk=False keeps vectors in RAM for lowest latency (MVP).
            # Set on_disk=True when vector count exceeds available RAM.
            on_disk=False,
        ),
        hnsw_config=qdrant_models.HnswConfigDiff(
            m=16,
            ef_construct=100,
            # full_scan_threshold: below this count, brute-force is used
            # instead of HNSW (faster for small datasets).
            full_scan_threshold=10_000,
        ),
        optimizers_config=qdrant_models.OptimizersConfigDiff(
            # Delay indexing until at least 20 K vectors are accumulated to
            # avoid thrashing the HNSW index during bulk ingestion.
            indexing_threshold=20_000,
        ),
    )

    # Create payload indexes for the fields used in filter queries.
    await client.create_payload_index(
        collection_name=collection_name,
        field_name="session_id",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    await client.create_payload_index(
        collection_name=collection_name,
        field_name="source_url",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )

    logger.info("Qdrant collection created.", extra={"collection": collection_name})


async def close_qdrant_client() -> None:
    """Close the Qdrant client connection.

    Should be called during application shutdown.  Safe to call if the client
    was never initialised (no-op in that case).
    """
    global _client

    if _client is not None:
        await _client.close()
        _client = None
        logger.info("Qdrant async client closed.")
