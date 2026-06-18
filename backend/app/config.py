"""
Application configuration.

All settings are read from environment variables (or a .env file) and
validated at startup via pydantic-settings.  Import `get_settings()` anywhere
in the codebase — the result is cached so the environment is only parsed once.
"""

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated application settings loaded from environment variables.

    Pydantic will raise a ``ValidationError`` at process start if any required
    variable is missing or has the wrong type, giving a clear error before any
    request is served.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # silently discard unknown env vars
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_name: str = Field(default="LitReviewer API", description="Human-readable app name.")
    environment: str = Field(
        default="development",
        description="Runtime environment: development | staging | production.",
    )
    log_level: str = Field(default="INFO", description="Logging level (DEBUG/INFO/WARNING/ERROR).")
    api_version: str = Field(default="v1", description="API version prefix, e.g. 'v1'.")
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="List of allowed CORS origins for the frontend.",
    )

    # -------------------------------------------------------------------------
    # LLM — Provider selection
    # -------------------------------------------------------------------------
    llm_provider: str = Field(
        default="groq",
        description=(
            "Active LLM provider. Supported values: 'groq', 'anthropic'. "
            "Changing this value requires the corresponding API key to be set."
        ),
    )

    # Per-agent provider overrides.  Empty string means "inherit llm_provider".
    research_llm_provider: str = Field(default="", description="LLM provider for ResearchAgent. Empty = use llm_provider.")
    writer_llm_provider: str = Field(default="", description="LLM provider for WriterAgent. Empty = use llm_provider.")
    critic_llm_provider: str = Field(default="", description="LLM provider for CriticAgent. Empty = use llm_provider.")
    factchecker_llm_provider: str = Field(default="", description="LLM provider for FactCheckerAgent. Empty = use llm_provider.")

    # -------------------------------------------------------------------------
    # LLM — Groq (primary)
    # -------------------------------------------------------------------------
    groq_api_key: SecretStr = Field(default="", description="Groq API key (console.groq.com).")
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model identifier.",
    )
    groq_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="LLM sampling temperature (lower = more deterministic).",
    )

    # -------------------------------------------------------------------------
    # LLM — Anthropic Claude (alternative)
    # -------------------------------------------------------------------------
    anthropic_api_key: SecretStr = Field(default="", description="Anthropic API key.")
    anthropic_model: str = Field(
        default="claude-sonnet-4-6",
        description="Anthropic Claude model identifier.",
    )
    anthropic_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description="LLM sampling temperature (lower = more deterministic).",
    )

    # -------------------------------------------------------------------------
    # Web Search — Tavily
    # -------------------------------------------------------------------------
    tavily_api_key: SecretStr = Field(default="", description="Tavily Search API key.")
    tavily_max_results: int = Field(
        default=20,
        ge=1,
        le=20,
        description="Maximum number of search results per Tavily query.",
    )

    # -------------------------------------------------------------------------
    # Database — PostgreSQL
    # -------------------------------------------------------------------------
    postgres_url: SecretStr = Field(
        default="postgresql+asyncpg://research_user:research_pass@localhost:5432/research",
        description="Async SQLAlchemy connection URL (must use asyncpg driver).",
    )
    postgres_pool_size: int = Field(default=10, ge=1, description="SQLAlchemy connection pool size.")
    postgres_max_overflow: int = Field(
        default=20,
        ge=0,
        description="Maximum connections above pool_size allowed during peak load.",
    )
    postgres_pool_recycle: int = Field(
        default=1800,
        ge=60,
        description="Seconds before idle connections are recycled (prevents stale connections).",
    )

    # -------------------------------------------------------------------------
    # Database — Qdrant
    # -------------------------------------------------------------------------
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant REST API base URL.",
    )
    qdrant_collection_name: str = Field(
        default="research_docs",
        description="Name of the Qdrant collection used for research document embeddings.",
    )

    # -------------------------------------------------------------------------
    # Database — Redis
    # -------------------------------------------------------------------------
    redis_url: str = Field(
        default="redis://localhost:6379",
        description="Redis connection URL.",
    )

    # -------------------------------------------------------------------------
    # Research tuning
    # -------------------------------------------------------------------------
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum number of research→fact-check→critique loop iterations.",
    )
    min_quality_score: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum CriticAgent quality score before proceeding to WriterAgent.",
    )
    rag_top_k: int = Field(
        default=8,
        ge=1,
        le=20,
        description="Number of chunks to retrieve from Qdrant per query.",
    )

    # -------------------------------------------------------------------------
    # RAG — Embedding model
    # -------------------------------------------------------------------------
    embedding_model: str = Field(
        default="BAAI/bge-large-en-v1.5",
        description=(
            "HuggingFace sentence-transformers model for document and query embedding. "
            "Must produce 1024-dimensional vectors to match the Qdrant collection schema. "
            "Model is downloaded to the HuggingFace cache on first use."
        ),
    )
    rag_chunk_size: int = Field(
        default=1200,
        ge=100,
        le=4000,
        description=(
            "Maximum chunk length in characters. 1200 chars ≈ 300 tokens, safely under "
            "the bge-large-en-v1.5 512-token context limit."
        ),
    )
    rag_chunk_overlap: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Character overlap between consecutive chunks for cross-boundary context.",
    )
    rag_min_chunk_length: int = Field(
        default=50,
        ge=1,
        description="Chunks shorter than this are discarded after splitting.",
    )
    rag_embedding_batch_size: int = Field(
        default=32,
        ge=1,
        le=256,
        description=(
            "Number of text chunks embedded in a single sentence-transformers forward pass. "
            "Larger values are faster but require more RAM/VRAM."
        ),
    )
    rag_max_document_size_mb: float = Field(
        default=50.0,
        gt=0.0,
        description=(
            "Maximum file size in megabytes accepted by the document ingestion pipeline. "
            "Files larger than this are rejected before loading to prevent OOM errors."
        ),
    )

    # -------------------------------------------------------------------------
    # Rate limiting
    # -------------------------------------------------------------------------
    rate_limit_per_minute: int = Field(
        default=10,
        ge=1,
        description="Maximum research-start requests per minute per IP address.",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        """Ensure environment is one of the known values."""
        allowed = {"development", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"environment must be one of {allowed}, got '{value}'")
        return value

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        """Normalise provider name to lowercase and validate against known values."""
        lower = value.lower()
        allowed = {"groq", "anthropic"}
        if lower not in allowed:
            raise ValueError(
                f"llm_provider must be one of {allowed}, got '{value}'."
            )
        return lower

    @field_validator("research_llm_provider", "writer_llm_provider", "critic_llm_provider", "factchecker_llm_provider")
    @classmethod
    def validate_agent_llm_provider(cls, value: str) -> str:
        """Allow empty string (inherit global) or a valid provider name."""
        if not value:
            return value
        lower = value.lower()
        allowed = {"groq", "anthropic"}
        if lower not in allowed:
            raise ValueError(f"agent LLM provider must be one of {allowed} or empty, got {value!r}")
        return lower

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalise log level to uppercase and validate."""
        upper = value.upper()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}, got '{value}'")
        return upper

    # -------------------------------------------------------------------------
    # Computed helpers
    # -------------------------------------------------------------------------
    @property
    def is_development(self) -> bool:
        """Return True when running in the development environment."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.environment == "production"

    @property
    def docs_enabled(self) -> bool:
        """Swagger UI and ReDoc are only exposed outside production."""
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Uses ``@lru_cache`` so the environment is parsed and validated exactly once
    per process.  In tests, call ``get_settings.cache_clear()`` between cases
    that need different settings, or use ``app.dependency_overrides``.
    """
    return Settings()
