"""Central, env-driven configuration.

Kept import-light (only pydantic-settings) so it can be imported from the CLI
launcher, the Chainlit app, and the tests without pulling in heavy ML deps.
All filesystem paths use ``pathlib`` so the system runs unchanged on Linux,
macOS, and Windows.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = three levels up from this file: src/agentic_kris/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings, loaded from environment / a project-root .env file."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── LLM backend ──────────────────────────────────────────────────────────
    llm_provider: str = "anthropic"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"

    # ── Orchestration ────────────────────────────────────────────────────────
    max_review_rounds: int = Field(default=3, ge=1, le=10)

    # ── Skills ───────────────────────────────────────────────────────────────
    skills_dir: str = "skills"

    # ── RAG (future integration) ─────────────────────────────────────────────
    rag_enabled: bool = False
    retrieval_top_k: int = 5

    # Postgres + pgvector (only used once the real RAG backend lands)
    pghost: str = "localhost"
    pgport: int = 5432
    pguser: str = "agent_user"
    pgpassword: str = "agent_pass"
    pgdatabase: str = "agent_db"

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def skills_path(self) -> Path:
        """Absolute path to the skills directory (relative resolves to root)."""
        p = Path(self.skills_dir)
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    @property
    def pg_dsn(self) -> str:
        return (
            f"host={self.pghost} port={self.pgport} user={self.pguser} "
            f"password={self.pgpassword} dbname={self.pgdatabase}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (re-read by clearing the lru_cache in tests)."""
    return Settings()


settings = get_settings()
