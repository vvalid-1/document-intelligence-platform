from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── Ollama ────────────────────────────────────────────────────────────────
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_CHAT_MODEL: str = "qwen3:8b"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    OLLAMA_TRANSLATION_MODEL: str = "qwen2.5:3b"
    OLLAMA_NUM_CTX: int = 4096
    OLLAMA_NUM_THREAD: int = 4
    OLLAMA_NUM_PREDICT: int = 1024

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    CHROMADB_HOST: str = "chromadb"
    CHROMADB_PORT: int = 8000

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── File storage ──────────────────────────────────────────────────────────
    UPLOAD_DIR: str = "/app/uploads"
    MAX_FILE_SIZE_MB: int = 50

    # ── Agent ─────────────────────────────────────────────────────────────────
    AGENT_TIMEOUT_SECONDS: int = 300
    MAX_CHAT_MESSAGE_CHARS: int = 8000
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100

    # ── Security ──────────────────────────────────────────────────────────────
    # Stored as comma-separated string; use cors_origins property for a list
    CORS_ALLOWED_ORIGINS: str = "http://localhost,http://localhost:80"

    # ── Observability ─────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _jwt_secret_strength(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()  # type: ignore[call-arg]
