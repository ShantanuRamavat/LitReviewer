"""
RAG (Retrieval-Augmented Generation) pipeline.

Public API — import everything agents and services need from here::

    from app.rag import (
        # File-based ingestion (PDF / TXT / Markdown)
        ingest_file,
        ingest_files,
        # Low-level ingestion (plain text from web search etc.)
        ingest_documents,
        # Retrieval
        retrieve,
        # Embedder lifecycle
        init_embedder,
        get_embedder,
        close_embedder,
        # Data types
        DocumentInput,
        DocumentMetadata,
        RetrievalQuery,
        RetrievalResult,
        IngestionSummary,
    )

Submodules (internal implementation details — do not import directly):
- ``app.rag.schemas``             — Data contracts
- ``app.rag.chunker``             — RecursiveCharacterTextSplitter wrapper
- ``app.rag.embedder``            — sentence-transformers async wrapper + singleton
- ``app.rag.ingestion``           — Low-level chunk → embed → Qdrant upsert
- ``app.rag.retriever``           — Qdrant similarity search
- ``app.rag.document_ingestion``  — File-based ingestion (reads PDF/TXT/MD)
- ``app.rag.loaders``             — Loader registry and per-format loaders
"""

from app.rag.document_ingestion import ingest_file, ingest_files
from app.rag.embedder import close_embedder, get_embedder, init_embedder
from app.rag.ingestion import ingest_documents
from app.rag.retriever import retrieve
from app.rag.schemas import (
    DocumentChunk,
    DocumentInput,
    DocumentMetadata,
    IngestionSummary,
    IngestedDocument,
    RetrievalQuery,
    RetrievalResult,
)

__all__ = [
    # Embedder lifecycle
    "init_embedder",
    "get_embedder",
    "close_embedder",
    # File-based ingestion entry points
    "ingest_file",
    "ingest_files",
    # Low-level ingestion (text from web search etc.)
    "ingest_documents",
    # Retrieval
    "retrieve",
    # Data types
    "DocumentInput",
    "DocumentMetadata",
    "DocumentChunk",
    "IngestedDocument",
    "IngestionSummary",
    "RetrievalQuery",
    "RetrievalResult",
]
