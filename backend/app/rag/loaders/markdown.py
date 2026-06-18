"""
Markdown document loader.

Reads ``.md`` / ``.markdown`` files, strips Markdown syntax to produce clean
prose, and returns a ``DocumentInput`` ready for the ingestion pipeline.

Why strip Markdown syntax?
--------------------------
Embedding ``# Heading`` as-is includes the ``#`` character in the vector.
While sentence-transformers handle this, stripping headings/links/code fences
produces cleaner prose that embeds more consistently.  The stripping is done
with regex — no HTML intermediate step — so it has no external dependency.

Stripping rules (applied in order):
1. Fenced code blocks  (``` ... ```) → replaced with their content
2. Inline code         (`code`)      → content only
3. ATX headings        (# text)      → text only
4. Bold/italic         (**x**, *x*)  → text only
5. Links               ([text](url)) → text only
6. Images              (![alt](url)) → alt text only
7. Blockquotes         (> text)      → text only
8. Horizontal rules    (--- / ***)   → removed
9. HTML tags                         → removed
10. Excess blank lines               → collapsed to max two
"""

import logging
import re
from pathlib import Path

from app.rag.loaders.base import BaseLoader
from app.rag.schemas import DocumentInput, DocumentMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled regex patterns (compiled once at import time)
# ---------------------------------------------------------------------------

# Fenced code blocks: ```lang\n...\n``` — capture the inner content
_RE_FENCED_CODE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
# Inline code: `code`
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
# ATX headings: ## Heading
_RE_HEADING = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
# Bold: **text** or __text__
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
# Italic: *text* or _text_
_RE_ITALIC = re.compile(r"\*(.+?)\*|_(.+?)_")
# Links: [text](url) — keep text
_RE_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
# Images: ![alt](url) — keep alt text
_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
# Blockquotes: > text
_RE_BLOCKQUOTE = re.compile(r"^>\s?", re.MULTILINE)
# Horizontal rules
_RE_HR = re.compile(r"^[-*_]{3,}\s*$", re.MULTILINE)
# HTML tags
_RE_HTML_TAG = re.compile(r"<[^>]+>")
# Collapse 3+ blank lines to 2
_RE_EXCESS_BLANK = re.compile(r"\n{3,}")


class MarkdownLoader(BaseLoader):
    """Load a Markdown file, strip syntax, and return clean prose."""

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".md", ".markdown"})

    def load(self, path: Path, source_url: str | None = None) -> DocumentInput:
        """Read a Markdown file and strip its syntax.

        Args:
            path: Path to the Markdown file.
            source_url: Override the default ``file://`` source URL.

        Returns:
            ``DocumentInput`` with cleaned prose text and file metadata.

        Raises:
            FileNotFoundError: If ``path`` does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")

        raw = self._read_with_fallback(path)
        clean = _strip_markdown(raw)

        metadata = DocumentMetadata(
            filename=path.name,
            file_type="markdown",
            file_size_bytes=path.stat().st_size,
        )

        logger.debug(
            "Markdown file loaded.",
            extra={
                "file": path.name,
                "raw_chars": len(raw),
                "clean_chars": len(clean),
            },
        )

        return DocumentInput(
            text=clean,
            source_url=self._resolve_source_url(path, source_url),
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _strip_markdown(text: str) -> str:
    """Remove Markdown syntax and return clean prose."""
    # Fenced code blocks — keep inner text
    text = _RE_FENCED_CODE.sub(lambda m: m.group(1).strip(), text)
    # Inline code — keep content
    text = _RE_INLINE_CODE.sub(r"\1", text)
    # ATX headings — keep heading text
    text = _RE_HEADING.sub(r"\1", text)
    # Images before links (both share [])
    text = _RE_IMAGE.sub(r"\1", text)
    # Links — keep display text
    text = _RE_LINK.sub(r"\1", text)
    # Bold
    text = _RE_BOLD.sub(lambda m: m.group(1) or m.group(2), text)
    # Italic
    text = _RE_ITALIC.sub(lambda m: m.group(1) or m.group(2), text)
    # Blockquotes — remove the leading >
    text = _RE_BLOCKQUOTE.sub("", text)
    # Horizontal rules — remove entirely
    text = _RE_HR.sub("", text)
    # HTML tags
    text = _RE_HTML_TAG.sub("", text)
    # Collapse excess blank lines
    text = _RE_EXCESS_BLANK.sub("\n\n", text)

    return text.strip()


