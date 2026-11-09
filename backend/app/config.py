"""Runtime configuration, read from environment variables (or a .env file)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ASKDATA_", extra="ignore")

    # Target database the agent queries. Use a READ-ONLY role (see data/seed.py).
    database_url: str = "postgresql+psycopg://askdata_ro:askdata_ro@localhost:5432/shop"
    # Where AskData keeps its own history and evaluation runs.
    state_db_path: str = "askdata_state.sqlite3"

    # LLM. provider: "anthropic", "gemini", or "" to pick whichever key is set
    # (Anthropic wins if both are). Gemini has a free tier: https://aistudio.google.com/apikey
    llm_provider: str = ""
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-5-5"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_fallback_model: str = "gemini-flash-lite-latest"
    llm_max_tokens: int = 1500

    # Agent behaviour
    max_repairs: int = 2
    retrieval_top_k: int = 4
    row_limit: int = 1000
    statement_timeout_ms: int = 8000

    # CORS origins for the frontend (comma separated)
    cors_origins: str = "http://localhost:3000"

    @property
    def active_provider(self) -> str:
        p = self.llm_provider.strip().lower()
        if p in ("anthropic", "gemini"):
            return p
        if self.anthropic_api_key:
            return "anthropic"
        if self.gemini_api_key:
            return "gemini"
        return "anthropic"

    @property
    def active_model(self) -> str:
        return self.gemini_model if self.active_provider == "gemini" else self.model

    @property
    def llm_configured(self) -> bool:
        return bool(self.gemini_api_key if self.active_provider == "gemini" else self.anthropic_api_key)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
