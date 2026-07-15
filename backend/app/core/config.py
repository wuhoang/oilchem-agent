"""
Application configuration loaded from environment variables.

Uses pydantic-settings v2. The settings object is imported lazily to avoid
side effects during test collection. All values are typed; no dynamic
attribute mounting.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root (one level above backend/) and backend root.
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
BACKEND_ROOT: Path = Path(__file__).resolve().parents[1]
LOGS_DIR: Path = BACKEND_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """Central application settings."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # ---- App ----
    app_name: str = Field(default="OilChem Agent", alias="APP_NAME")
    version: str = Field(default="0.1.0", alias="APP_VERSION")
    env: str = Field(default="dev", alias="ENV")
    debug: bool = Field(default=True, alias="DEBUG")

    # ---- Server ----
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # ---- LLM ----
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    model_name: str = Field(default="", alias="MODEL_NAME")

    # ---- Logging ----
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---- API ----
    api_v1_prefix: str = "/api/v1"

    @property
    def is_production(self) -> bool:
        return self.env.lower() in {"prod", "production"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
