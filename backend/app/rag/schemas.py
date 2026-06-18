"""
Data contracts for the RAG pipeline.

All types are plain dataclasses — no ORM or Pydantic dependency — so they can
be used in any layer (agents, services, tests) without pulling in extra weight.
"""

from dataclasses import dataclass, field


@dataclass
class DocumentMetadata:
    """Optional metadata attached to a document before ingestion.

    Fields are stored as extra payload keys on every Qdrant point produced
    from the document, making them filterable and returnable at retrieval time.

    Attributes:
        filename: Original file name, e.g. ``"report.pdf"``.
        file_type: Normalised type string: ``"pdf"``, ``"txt"``, or ``"markdown"``.
        file_size_bytes: Size of the source file in bytes.
        page_count: Number of pages (PDF only; ``None`` for other types).
        title: Document title extracted from file metadata, if available.
    """

    filename: str
    file_type: str
    file_size_bytes: int
    page_count: int | None = None
    title: str | None = None

    def to_payload_dict(self) -> dict[str, object]:
        """Return a flat dict suitable for merging into a Qdrant point payload."""
        payload: dict[str, object] = {
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size_bytes": self.file_size_bytes,
        }
        if self.page_count is not None:
            payload["page_count"] = self.page_count
        if self.title is not None:
            payload["title"] = self.title
        return payload


@dataclass
class DocumentInput:
    """A raw document to be chunked, embedded, and stored in Qdrant.

    Attributes:
        text: Full text of the document (web page body, PDF content, etc.).
        source_url: Canonical URL or ``file://`` URI identifying the document.
            Used as a stable key for deduplication across ingestion runs.
        metadata: Optional file metadata included in the Qdrant payload.
            Pass ``None`` for documents sourced from web search.
    """

    text: str
    source_url: str
    metadata: DocumentMetadata | None = None


@dataclass
class DocumentChunk:
    """A single chunk produced by splitting a ``DocumentInput``.

    Attributes:
        text: The chunk text that will be embedded and stored.
        chunk_index: Zero-based index of this chunk within its source document.
        source_url: Inherited from the parent ``DocumentInput``.
        session_id: Research session this document belongs to.  Stored as a
            Qdrant payload field so retrieval can be scoped per session.
    """

    text: str
    chunk_index: int
    source_url: str
    session_id: str


@dataclass
class IngestedDocument:
    """Summary returned after ingesting one document.

    Attributes:
        source_url: URL of the ingested document.
        session_id: Research session the document was associated with.
        chunk_count: Number of chunks written to Qdrant.  Zero when skipped.
        skipped: True if the document was already present in Qdrant and was
            not re-ingested (deduplication shortcut).
    """

    source_url: str
    session_id: str
    chunk_count: int
    skipped: bool = False


@dataclass
class RetrievalQuery:
    """Input to the vector retriever.

    Attributes:
        text: Natural-language query string.
        session_id: When set, restricts results to chunks from this session.
            Pass an empty string to search across all sessions.
        k: Maximum number of results to return.  Defaults to 8.
    """

    text: str
    session_id: str
    k: int = 8


@dataclass
class RetrievalResult:
    """A single chunk returned by the retriever.

    Attributes:
        text: The chunk text, ready for injection into an agent prompt.
        source_url: URL of the document the chunk came from.
        score: Cosine similarity score in [0, 1].  Higher is more relevant.
        chunk_index: Position of this chunk within its source document.
        session_id: Session the chunk belongs to.
    """

    text: str
    source_url: str
    score: float
    chunk_index: int
    session_id: str


@dataclass
class IngestionSummary:
    """Aggregate result of ingesting a batch of documents.

    Attributes:
        total: Total documents submitted for ingestion.
        ingested: Documents that produced at least one new Qdrant point.
        skipped: Documents skipped due to deduplication.
        failed: Documents that encountered an error during ingestion.
        total_chunks: Sum of all chunks written across ingested documents.
        errors: Mapping of source_url → error message for failed documents.
    """

    total: int
    ingested: int
    skipped: int
    failed: int
    total_chunks: int
    errors: dict[str, str] = field(default_factory=dict)
