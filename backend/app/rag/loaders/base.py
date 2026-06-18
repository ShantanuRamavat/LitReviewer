"""
Abstract base class for all document loaders.

Each loader handles one file type and exposes a single ``load()`` method that
reads a file from disk and returns a ``DocumentInput`` ready for the ingestion
pipeline.

Loaders are synchronous.  File I/O (especially PDF parsing) is blocking, so
callers must dispatch ``load()`` to a thread-pool executor — this is handled
by ``document_ingestion.py``, not by the loaders themselves.  Keeping loaders
sync makes them trivially unit-testable without an event loop.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from app.rag.schemas import DocumentInput


class BaseLoader(ABC):
    """Abstract file loader.

    Subclasses implement ``load()`` for a specific file type and declare which
    extensions they handle via ``supported_extensions``.
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> frozenset[str]:
        """Return the set of lowercase file extensions this loader handles.

        Extensions must include the leading dot, e.g. ``{".pdf"}``.
        """

    @abstractmethod
    def load(self, path: Path, source_url: str | None = None) -> DocumentInput:
        """Read a file and return a ``DocumentInput``.

        Args:
            path: Absolute path to the file on disk.
            source_url: Override the default ``file://`` source URL.  Pass
                ``None`` to use ``file://<path>`` as the identifier.

        Returns:
            ``DocumentInput`` with extracted text, source URL, and metadata.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            ValueError: If the file cannot be parsed (corrupt, wrong format).
        """

    def _resolve_source_url(self, path: Path, source_url: str | None) -> str:
        """Return the effective source URL for a file."""
        if source_url:
            return source_url
        return path.as_uri()  # file:///absolute/path

    def _read_with_fallback(self, path: Path) -> str:
        """Read a file trying UTF-8 first, then Latin-1 as a catch-all.

        Latin-1 accepts every byte value so it never raises ``UnicodeDecodeError``,
        making it a safe final fallback for files of unknown encoding.
        """
        for encoding in ("utf-8", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode '{path.name}' with any supported encoding.")
