"""
Plain-text document loader.

Reads ``.txt`` files as UTF-8, falling back to Latin-1 if the file contains
bytes that are not valid UTF-8.  This covers the vast majority of plain-text
files encountered in practice without requiring a charset-detection library.
"""

import logging
from pathlib import Path

from app.rag.loaders.base import BaseLoader
from app.rag.schemas import DocumentInput, DocumentMetadata

logger = logging.getLogger(__name__)


class TextLoader(BaseLoader):
    """Load a plain-text file and return its content as a ``DocumentInput``."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".txt"})

    def load(self, path: Path, source_url: str | None = None) -> DocumentInput:
        """Read a ``.txt`` file.

        Args:
            path: Path to the text file.
            source_url: Override the default ``file://`` source URL.

        Returns:
            ``DocumentInput`` with the file's text content and basic metadata.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Text file not found: {path}")

        text = self._read_with_fallback(path)

        metadata = DocumentMetadata(
            filename=path.name,
            file_type="txt",
            file_size_bytes=path.stat().st_size,
        )

        logger.debug(
            "Text file loaded.",
            extra={"file": path.name, "chars": len(text)},
        )

        return DocumentInput(
            text=text,
            source_url=self._resolve_source_url(path, source_url),
            metadata=metadata,
        )


