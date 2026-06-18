"""
RAG ingestion pipeline — chunk → embed → store in Qdrant.

The entry point is ``ingest_documents()``.  For each document it:
1. Splits the text into overlapping chunks (``Chunker``).
2. Embeds each chunk in batches (``Embedder``).
3. Checks Qdrant for existing points (deduplication).
4. Upserts only new chunks.

Deduplication
-------------
Each Qdrant point gets a deterministic UUID derived from MD5(session_id +
source_url + chunk_index).  Before upserting, a scroll query checks whether
those IDs already exist.  Documents whose every chunk is already present are
marked ``skipped=True`` and their vectors are not re-computed.  This makes
repeated ingestion calls for the same session idempotent.

Batching
--------
Embedding and Qdrant upserts are batched by ``settings.rag_embedding_batch_size``
(default 32).  Processing large documents in batches avoids OOM on the
sentence-transformers side and keeps Qdrant RPC sizes reasonable.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from qdrant_client import models as qdrant_models

from app.config import Settings, get_settings
from app.db.qdrant.client import get_qdrant_client
from app.rag.chunker import Chunker
from app.rag.embedder import Embedder, get_embedder
from app.rag.schemas import (
    DocumentChunk,
    DocumentInput,
    IngestionSummary,
    IngestedDocument,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ingest_documents(
    documents: list[DocumentInput],
    session_id: str,
    *,
    settings: Settings | None = None,
) -> IngestionSummary:
    """Chunk, embed, and store a batch of documents in Qdrant.

    Args:
        documents: Raw documents to ingest.
        session_id: Research session to associate with all chunks.
        settings: Application settings; defaults to the cached singleton.

    Returns:
        ``IngestionSummary`` with counts and any per-document error messages.
    """
    if settings is None:
        settings = get_settings()

    chunker = Chunker(
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
        min_chunk_length=settings.rag_min_chunk_length,
    )

    total = len(documents)
    ingested = 0
    skipped = 0
    failed = 0
    total_chunks = 0
    errors: dict[str, str] = {}

    for doc in documents:
        try:
            result = await _ingest_one(doc, session_id, chunker, settings)
            if result.skipped:
                skipped += 1
            else:
                ingested += 1
                total_chunks += result.chunk_count
        except Exception as exc:
            failed += 1
            errors[doc.source_url] = str(exc)
            logger.warning(
                "Document ingestion failed.",
                extra={"source_url": doc.source_url, "error": str(exc)},
            )

    logger.info(
        "Ingestion batch complete.",
        extra={
            "session_id": session_id,
            "total": total,
            "ingested": ingested,
            "skipped": skipped,
            "failed": failed,
            "total_chunks": total_chunks,
        },
    )

    return IngestionSummary(
        total=total,
        ingested=ingested,
        skipped=skipped,
        failed=failed,
        total_chunks=total_chunks,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _ingest_one(
    document: DocumentInput,
    session_id: str,
    chunker: Chunker,
    settings: Settings,
) -> IngestedDocument:
    """Ingest a single document.  Returns an ``IngestedDocument`` summary."""
    chunks = chunker.split(document, session_id)

    if not chunks:
        logger.debug(
            "Document produced no chunks; skipping.",
            extra={"source_url": document.source_url},
        )
        return IngestedDocument(
            source_url=document.source_url,
            session_id=session_id,
            chunk_count=0,
            skipped=True,
        )

    # Compute deterministic point IDs before hitting Qdrant.
    point_ids = [_make_point_id(chunk) for chunk in chunks]

    # Deduplication: check which IDs already exist.
    new_chunks, new_ids = await _filter_existing(chunks, point_ids)

    if not new_chunks:
        logger.debug(
            "All chunks already present in Qdrant; skipping document.",
            extra={"source_url": document.source_url, "chunks": len(chunks)},
        )
        return IngestedDocument(
            source_url=document.source_url,
            session_id=session_id,
            chunk_count=0,
            skipped=True,
        )

    # Embed in batches.
    embedder = get_embedder()
    vectors = await _embed_in_batches(
        [c.text for c in new_chunks],
        batch_size=settings.rag_embedding_batch_size,
        embedder=embedder,
    )

    # Build Qdrant PointStruct list.
    now = datetime.now(timezone.utc).isoformat()
    # Merge optional document metadata into every point payload so it is
    # filterable and returnable at retrieval time.
    metadata_payload = document.metadata.to_payload_dict() if document.metadata else {}
    points = [
        qdrant_models.PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "text": chunk.text,
                "source_url": chunk.source_url,
                "session_id": chunk.session_id,
                "chunk_index": chunk.chunk_index,
                "ingested_at": now,
                **metadata_payload,
            },
        )
        for point_id, vector, chunk in zip(new_ids, vectors, new_chunks)
    ]

    # Upsert to Qdrant.
    client = get_qdrant_client()
    await client.upsert(
        collection_name=settings.qdrant_collection_name,
        points=points,
        wait=True,
    )

    logger.info(
        "Document ingested.",
        extra={
            "source_url": document.source_url,
            "session_id": session_id,
            "chunks_written": len(new_chunks),
        },
    )

    return IngestedDocument(
        source_url=document.source_url,
        session_id=session_id,
        chunk_count=len(new_chunks),
    )


async def _filter_existing(
    chunks: list[DocumentChunk],
    point_ids: list[str],
) -> tuple[list[DocumentChunk], list[str]]:
    """Return only chunks whose Qdrant point IDs do not yet exist."""
    client = get_qdrant_client()
    collection_name = get_settings().qdrant_collection_name

    # retrieve() returns only the points that exist.
    existing = await client.retrieve(
        collection_name=collection_name,
        ids=point_ids,
        with_payload=False,
        with_vectors=False,
    )
    existing_ids = {str(p.id) for p in existing}

    new_chunks = []
    new_ids = []
    for chunk, pid in zip(chunks, point_ids):
        if pid not in existing_ids:
            new_chunks.append(chunk)
            new_ids.append(pid)

    return new_chunks, new_ids


async def _embed_in_batches(
    texts: list[str],
    *,
    batch_size: int,
    embedder: Embedder,
) -> list[list[float]]:
    """Embed ``texts`` in batches, returning a flat list of vectors."""
    all_vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors = await embedder.embed_documents(batch)
        all_vectors.extend(vectors)
    return all_vectors


def _make_point_id(chunk: DocumentChunk) -> str:
    """Derive a deterministic UUID from a chunk's natural key.

    Using a deterministic ID means re-ingesting the same chunk overwrites the
    existing point rather than creating a duplicate.  The key is:
    ``session_id:source_url:chunk_index``.
    """
    raw = f"{chunk.session_id}:{chunk.source_url}:{chunk.chunk_index}"
    digest = hashlib.md5(raw.encode()).hexdigest()
    return str(uuid.UUID(digest))
