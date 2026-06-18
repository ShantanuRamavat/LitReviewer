"""
File-based document ingestion entry points.

Sits above the core ingestion pipeline (``app.rag.ingestion``) and adds:
- File reading via the ``LoaderRegistry``
- Async dispatch of blocking loader calls to a thread-pool executor
- File size validation before loading
- Per-file error isolation so one bad file does not abort the batch

Entry points
------------
``ingest_file(path, session_id)``
    Ingest a single file.  Returns an ``IngestedDocument`` summary.

``ingest_files(paths, session_id)``
    Ingest a batch of files.  Returns an ``IngestionSummary``.

Async / blocking boundary
--------------------------
All ``BaseLoader.load()`` implementations are synchronous (file I/O + PDF
parsing).  Each call is dispatched to the default thread-pool executor via
``asyncio.get_event_loop().run_in_executor(None, ...)`` so the event loop
is never blocked.
"""

import asyncio
import logging
from functools import partial
from pathlib import Path

from app.config import Settings, get_settings
from app.rag.ingestion import ingest_documents
from app.rag.loaders import get_loader, is_supported
from app.rag.schemas import IngestionSummary, IngestedDocument

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def ingest_file(
    path: Path,
    session_id: str,
    *,
    source_url: str | None = None,
    settings: Settings | None = None,
) -> IngestedDocument:
    """Load and ingest a single file into Qdrant.

    Args:
        path: Absolute path to the file.  Extension must be one of:
            ``.pdf``, ``.txt``, ``.md``, ``.markdown``.
        session_id: Research session to associate the document with.
        source_url: Override the ``file://`` source URL used for deduplication.
            Useful when the same physical file represents a specific resource.
        settings: Application settings; defaults to the cached singleton.

    Returns:
        ``IngestedDocument`` with chunk count and skip/ingest status.

    Raises:
        ValueError: If the file extension is unsupported or the file exceeds
            ``settings.rag_max_document_size_mb``.
        FileNotFoundError: If ``path`` does not exist.
    """
    if settings is None:
        settings = get_settings()

    _validate_file(path, settings)

    loader = get_loader(path)

    loop = asyncio.get_event_loop()
    document = await loop.run_in_executor(
        None,
        partial(loader.load, path, source_url),
    )

    summary = await ingest_documents([document], session_id, settings=settings)

    # ingest_documents processes one doc — unwrap from summary.
    if summary.failed:
        error_msg = next(iter(summary.errors.values()), "unknown error")
        raise ValueError(f"Ingestion failed for '{path.name}': {error_msg}")

    if summary.skipped:
        return IngestedDocument(
            source_url=document.source_url,
            session_id=session_id,
            chunk_count=0,
            skipped=True,
        )

    return IngestedDocument(
        source_url=document.source_url,
        session_id=session_id,
        chunk_count=summary.total_chunks,
    )


async def ingest_files(
    paths: list[Path],
    session_id: str,
    *,
    settings: Settings | None = None,
) -> IngestionSummary:
    """Load and ingest a batch of files into Qdrant.

    Each file is loaded and ingested independently.  Failures in one file do
    not prevent the remaining files from being processed.

    Args:
        paths: List of file paths to ingest.  Unsupported extensions are
            counted as failures rather than raising.
        session_id: Research session to associate all documents with.
        settings: Application settings; defaults to the cached singleton.

    Returns:
        ``IngestionSummary`` with per-batch counts and per-file error messages.
    """
    if settings is None:
        settings = get_settings()

    total = len(paths)
    ingested = 0
    skipped = 0
    failed = 0
    total_chunks = 0
    errors: dict[str, str] = {}

    for path in paths:
        try:
            result = await ingest_file(path, session_id, settings=settings)
            if result.skipped:
                skipped += 1
            else:
                ingested += 1
                total_chunks += result.chunk_count
        except Exception as exc:
            failed += 1
            errors[str(path)] = str(exc)
            logger.warning(
                "File ingestion failed.",
                extra={"file": str(path), "error": str(exc)},
            )

    logger.info(
        "File batch ingestion complete.",
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


def _validate_file(path: Path, settings: Settings) -> None:
    """Raise if the file is unsupported or too large."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not is_supported(path):
        raise ValueError(
            f"Unsupported file type '{path.suffix}'. "
            f"Supported: .pdf, .txt, .md, .markdown"
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > settings.rag_max_document_size_mb:
        raise ValueError(
            f"File '{path.name}' is {size_mb:.1f} MB, which exceeds the "
            f"{settings.rag_max_document_size_mb} MB limit."
        )
