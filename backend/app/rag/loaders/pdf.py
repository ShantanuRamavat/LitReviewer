"""
PDF document loader using ``pypdf``.

Extracts text page-by-page and joins pages with a separator so the downstream
chunker can split across natural page boundaries.  Document-level metadata
(title, page count) is read from the PDF's XMP metadata or Info dict,
whichever is available.

Limitations
-----------
- Scanned PDFs with no text layer produce empty output.  The ingestion
  pipeline treats zero-chunk documents as skipped.
- Encrypted PDFs that require a password are not supported and raise
  ``ValueError``.
- pypdf's text extraction quality varies by PDF generator; complex layouts
  (multi-column, tables) may produce garbled text.
"""

import logging
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.rag.loaders.base import BaseLoader
from app.rag.schemas import DocumentInput, DocumentMetadata

logger = logging.getLogger(__name__)

# Separator inserted between pages so the chunker treats page breaks as
# natural split points.
_PAGE_SEPARATOR = "\n\n---\n\n"


class PdfLoader(BaseLoader):
    """Load a PDF file and extract its text and metadata."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".pdf"})

    def load(self, path: Path, source_url: str | None = None) -> DocumentInput:
        """Read a PDF and return a ``DocumentInput``.

        Args:
            path: Path to the PDF file.
            source_url: Override the default ``file://`` source URL.

        Returns:
            ``DocumentInput`` with full text and PDF metadata.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
            ValueError: If the PDF is encrypted or corrupt.
        """
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:
            raise ValueError(f"Could not read PDF '{path.name}': {exc}") from exc

        if reader.is_encrypted:
            raise ValueError(f"Encrypted PDF is not supported: '{path.name}'")

        page_texts: list[str] = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    page_texts.append(text.strip())
            except Exception as exc:
                logger.warning(
                    "Failed to extract text from PDF page.",
                    extra={"file": path.name, "page": page_num, "error": str(exc)},
                )

        full_text = _PAGE_SEPARATOR.join(page_texts)

        title = _extract_title(reader)
        metadata = DocumentMetadata(
            filename=path.name,
            file_type="pdf",
            file_size_bytes=path.stat().st_size,
            page_count=len(reader.pages),
            title=title,
        )

        logger.debug(
            "PDF loaded.",
            extra={
                "file": path.name,
                "pages": len(reader.pages),
                "chars": len(full_text),
                "title": title,
            },
        )

        return DocumentInput(
            text=full_text,
            source_url=self._resolve_source_url(path, source_url),
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_title(reader: PdfReader) -> str | None:
    """Try to extract the document title from XMP metadata or the Info dict."""
    # Prefer XMP metadata (more structured).
    try:
        xmp = reader.xmp_metadata
        if xmp and xmp.dc_title:
            title_value = xmp.dc_title
            if isinstance(title_value, dict):
                # dc_title is often {"x-default": "..."} mapping.
                title_value = title_value.get("x-default") or next(iter(title_value.values()), None)
            if title_value and isinstance(title_value, str):
                return title_value.strip() or None
    except Exception:
        pass

    # Fall back to Info dict.
    try:
        info = reader.metadata
        if info and info.title:
            title = info.title.strip()
            return title or None
    except Exception:
        pass

    return None
