"""
Centralized application settings via pydantic-settings.
All env vars are read here; everything else imports `settings`.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database — sync URL (used for Alembic) and async URL (used by the app).
    # Postgres + pgvector is the supported runtime; sqlite remains only as a
    # test-only fallback (see tests/conftest.py).
    database_url: str = "postgresql+asyncpg://citations:citations@localhost:5432/citations"
    database_url_sync: str = "postgresql+psycopg2://citations:citations@localhost:5432/citations"

    # Storage
    pdf_storage_path: str = "./data/pdfs"

    # API
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # Background jobs
    redis_url: str = "redis://localhost:6379"

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "claude-opus-4-7"
    feature_llm_resolver: bool = True

    # External enrichment
    feature_external_enrichment: bool = False
    courtlistener_api_key: str = ""

    # Graph defaults
    min_confidence_default: float = 0.7

    # Embeddings — local sentence-transformers, CPU.
    feature_embeddings: bool = True
    embedding_model: str = "all-mpnet-base-v2"
    embedding_dim: int = 768
    embedding_top_k: int = 25
    similarity_threshold_default: float = 0.75

    # Cross-encoder re-ranking on /api/search. Bi-encoder retrieves a wider
    # candidate pool (search_candidate_pool) and the cross-encoder re-ranks
    # to the caller-requested limit. Disabled cleanly if the flag is off —
    # /api/search returns bi-encoder results with scored_by="biencoder".
    feature_cross_encoder: bool = True
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    search_candidate_pool: int = 20

    # Logging
    log_level: str = "INFO"


settings = Settings()
