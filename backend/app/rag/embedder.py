"""
Sentence embedding wrapper for the RAG pipeline.

Wraps ``sentence-transformers`` (SentenceTransformer) to produce normalised
1024-dimensional vectors using BAAI/bge-large-en-v1.5.

Async interface
---------------
``sentence-transformers`` is a synchronous CPU/GPU library.  All encode calls
are dispatched to the default thread-pool executor via
``loop.run_in_executor()`` so the event loop is never blocked.

BGE asymmetric retrieval
------------------------
BGE models use different encodings for queries vs. documents:
- Queries must be prefixed with the instruction string (see ``_QUERY_PREFIX``).
- Documents are encoded without any prefix.
Using the wrong encoding degrades retrieval quality significantly.

Singleton lifecycle
-------------------
``init_embedder(settings)``  — called once during app startup (lifespan).
``get_embedder()``           — returns the singleton; raises if not initialised.
``close_embedder()``         — releases the model and frees GPU/CPU memory.
"""

import asyncio
import logging
from functools import partial

from sentence_transformers import SentenceTransformer

from app.config import Settings

logger = logging.getLogger(__name__)

# BGE asymmetric retrieval: queries need this prefix; documents do not.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_embedder: "Embedder | None" = None


# ---------------------------------------------------------------------------
# Singleton lifecycle
# ---------------------------------------------------------------------------


_EXPECTED_DIMENSIONS = 1024


async def init_embedder(settings: Settings) -> None:
    """Load the embedding model and initialise the module-level singleton.

    Wraps the blocking ``SentenceTransformer()`` constructor in the default
    thread-pool executor so the event loop is not blocked during startup.
    Validates that the loaded model produces the expected 1024-dimensional
    vectors to catch misconfigured ``embedding_model`` values early.

    Args:
        settings: Application settings; ``settings.embedding_model`` selects
            the SentenceTransformer model to load.

    Raises:
        ValueError: If the loaded model's dimensions do not match the expected
            Qdrant collection vector size.
    """
    global _embedder

    loop = asyncio.get_running_loop()
    model = await loop.run_in_executor(
        None, lambda: SentenceTransformer(settings.embedding_model)
    )
    _embedder = Embedder(model_name=settings.embedding_model, _model=model)

    if _embedder.dimensions != _EXPECTED_DIMENSIONS:
        raise ValueError(
            f"Embedding model '{settings.embedding_model}' produces "
            f"{_embedder.dimensions}-dimensional vectors, but Qdrant collection "
            f"expects {_EXPECTED_DIMENSIONS}. Update the collection schema or "
            f"choose a compatible embedding model."
        )

    logger.info(
        "Embedder initialised.",
        extra={"model": settings.embedding_model, "dimensions": _embedder.dimensions},
    )


def get_embedder() -> "Embedder":
    """Return the module-level ``Embedder`` singleton.

    Raises:
        RuntimeError: If ``init_embedder()`` has not been called.
    """
    if _embedder is None:
        raise RuntimeError(
            "Embedder has not been initialised. "
            "Call init_embedder(settings) during app startup."
        )
    return _embedder


def close_embedder() -> None:
    """Release the embedding model and free associated memory."""
    global _embedder
    _embedder = None
    logger.info("Embedder closed.")


# ---------------------------------------------------------------------------
# Embedder class
# ---------------------------------------------------------------------------


class Embedder:
    """Async wrapper around a ``SentenceTransformer`` model.

    Args:
        model_name: HuggingFace model identifier, e.g. ``"BAAI/bge-large-en-v1.5"``.
        batch_size: Number of texts to encode in a single forward pass.
            Larger batches are faster but require more memory.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-large-en-v1.5",
        batch_size: int = 32,
        *,
        _model: SentenceTransformer | None = None,
    ) -> None:
        self._model_name = model_name
        self._batch_size = batch_size
        # Accept a pre-loaded model (from async init) or load synchronously.
        self._model = _model if _model is not None else SentenceTransformer(model_name)

    # -------------------------------------------------------------------------
    # Public async interface
    # -------------------------------------------------------------------------

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts.

        Documents are encoded WITHOUT any prefix — BGE asymmetric retrieval.
        Normalised L2 embeddings are returned so cosine similarity equals
        dot product.

        Args:
            texts: Plain document texts.  Must be non-empty.

        Returns:
            List of 1024-dimensional float vectors, one per input text.
        """
        if not texts:
            return []

        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(
            None,
            partial(
                self._model.encode,
                texts,
                batch_size=self._batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
        )
        return [v.tolist() for v in vectors]

    async def embed_query(self, query: str) -> list[float]:
        """Embed a single retrieval query.

        The BGE instruction prefix is automatically prepended.  The result is
        compatible with the document vectors for cosine similarity search.

        Args:
            query: Natural-language query string.

        Returns:
            A single 1024-dimensional float vector.
        """
        prefixed = _QUERY_PREFIX + query
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(
            None,
            partial(
                self._model.encode,
                [prefixed],
                batch_size=1,
                normalize_embeddings=True,
                show_progress_bar=False,
            ),
        )
        return vectors[0].tolist()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def dimensions(self) -> int:
        """Return the embedding vector dimensionality (1024 for bge-large)."""
        return int(self._model.get_sentence_embedding_dimension())

    @property
    def model_name(self) -> str:
        """Return the HuggingFace model identifier."""
        return self._model_name

    def __repr__(self) -> str:
        return f"Embedder(model={self._model_name!r}, dimensions={self.dimensions})"
