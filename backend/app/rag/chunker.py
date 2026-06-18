"""
Text chunking for the RAG ingestion pipeline.

Splits raw document text into overlapping chunks small enough to fit inside
the BGE embedding model's 512-token context window.  Character-based splitting
is used as a conservative proxy for tokens (1 token ≈ 4 characters).

Default parameters (overridden by ``Settings``):
- chunk_size: 1200 characters ≈ 300 tokens — well inside the 512-token limit
- chunk_overlap: 200 characters — preserves cross-boundary context
- min_chunk_length: 50 characters — discards near-empty trailing fragments

Uses LangChain's ``RecursiveCharacterTextSplitter`` which prefers natural
boundaries (paragraphs → sentences → words) before hard-cutting at the limit.
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.rag.schemas import DocumentChunk, DocumentInput

# Separator hierarchy used by RecursiveCharacterTextSplitter.
# The splitter works down this list until chunks fit within the size limit.
_SEPARATORS = ["\n\n", "\n", ". ", "! ", "? ", ", ", " ", ""]


class Chunker:
    """Splits document text into overlapping chunks for embedding.

    Args:
        chunk_size: Maximum chunk length in characters.
        chunk_overlap: Character overlap between consecutive chunks.
        min_chunk_length: Chunks shorter than this are discarded.
    """

    def __init__(
        self,
        chunk_size: int = 1200,
        chunk_overlap: int = 200,
        min_chunk_length: int = 50,
    ) -> None:
        self._min_length = min_chunk_length
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=_SEPARATORS,
            length_function=len,
            is_separator_regex=False,
            strip_whitespace=True,
        )

    def split(self, document: DocumentInput, session_id: str) -> list[DocumentChunk]:
        """Split a document into chunks ready for embedding.

        Empty documents and documents whose text is shorter than
        ``min_chunk_length`` produce an empty list rather than a single tiny
        chunk — the ingestion layer treats those as no-ops.

        Args:
            document: The raw document to split.
            session_id: Research session to associate with each chunk.

        Returns:
            Ordered list of ``DocumentChunk`` objects.  May be empty.
        """
        raw_text = document.text.strip()
        if not raw_text:
            return []

        raw_chunks = self._splitter.split_text(raw_text)

        chunks: list[DocumentChunk] = []
        chunk_index = 0
        for raw in raw_chunks:
            cleaned = raw.strip()
            if len(cleaned) < self._min_length:
                continue
            chunks.append(
                DocumentChunk(
                    text=cleaned,
                    chunk_index=chunk_index,
                    source_url=document.source_url,
                    session_id=session_id,
                )
            )
            chunk_index += 1

        return chunks
