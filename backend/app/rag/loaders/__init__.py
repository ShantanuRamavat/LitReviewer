"""
Document loader registry.

``LoaderRegistry`` maps file extensions to the appropriate ``BaseLoader``
subclass.  It is the single place that knows which loaders exist, so adding
a new format only requires registering one more loader here.

Usage::

    from app.rag.loaders import LoaderRegistry

    registry = LoaderRegistry()
    loader = registry.get(Path("report.pdf"))   # → PdfLoader instance
    doc = loader.load(Path("report.pdf"))
"""

from pathlib import Path

from app.rag.loaders.base import BaseLoader
from app.rag.loaders.markdown import MarkdownLoader
from app.rag.loaders.pdf import PdfLoader
from app.rag.loaders.text import TextLoader

__all__ = [
    "BaseLoader",
    "LoaderRegistry",
    "PdfLoader",
    "TextLoader",
    "MarkdownLoader",
]


class LoaderRegistry:
    """Maps file extensions to ``BaseLoader`` instances.

    Loaders are instantiated once at registry creation and reused across all
    ``get()`` calls — they are stateless so sharing is safe.
    """

    def __init__(self) -> None:
        self._loaders: dict[str, BaseLoader] = {}
        for loader in (PdfLoader(), TextLoader(), MarkdownLoader()):
            for ext in loader.supported_extensions:
                self._loaders[ext] = loader

    def get(self, path: Path) -> BaseLoader:
        """Return the loader for ``path``'s file extension.

        Args:
            path: File whose extension determines the loader.

        Returns:
            The registered ``BaseLoader`` for this extension.

        Raises:
            ValueError: If no loader is registered for the extension.
        """
        ext = path.suffix.lower()
        loader = self._loaders.get(ext)
        if loader is None:
            supported = sorted(self._loaders.keys())
            raise ValueError(
                f"No loader registered for extension '{ext}'. "
                f"Supported extensions: {supported}"
            )
        return loader

    def supports(self, path: Path) -> bool:
        """Return ``True`` if a loader is registered for ``path``'s extension."""
        return path.suffix.lower() in self._loaders

    @property
    def supported_extensions(self) -> list[str]:
        """Return a sorted list of all registered file extensions."""
        return sorted(self._loaders.keys())


# Module-level default registry — shared across the app.
_default_registry = LoaderRegistry()


def get_loader(path: Path) -> BaseLoader:
    """Return the loader for ``path`` from the default registry."""
    return _default_registry.get(path)


def is_supported(path: Path) -> bool:
    """Return ``True`` if ``path``'s extension is supported by any loader."""
    return _default_registry.supports(path)
