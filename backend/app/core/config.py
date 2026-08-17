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
# Path layout: config.py -> app/core/ -> app/ -> backend/ -> project_root
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]
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
    version: str = Field(default="2.1.1", alias="APP_VERSION")
    env: str = Field(default="dev", alias="ENV")
    debug: bool = Field(default=True, alias="DEBUG")

    # ---- Server ----
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")

    # ---- LLM ----
    # 默认值对应 DeepSeek（OpenAI 兼容接口）；实际以 backend/.env 为准
    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_base_url: str = Field(default="https://api.deepseek.com/v1", alias="OPENAI_BASE_URL")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    model_name: str = Field(default="deepseek-chat", alias="MODEL_NAME")
    llm_timeout: float = Field(default=30.0, alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")
    llm_temperature: float = Field(default=0.7, alias="LLM_TEMPERATURE")
    llm_max_tokens: int = Field(default=4096, alias="LLM_MAX_TOKENS")

    # ---- File System ----
    file_allowed_paths: str = Field(default="", alias="FILE_ALLOWED_PATHS")
    file_watch_paths: str = Field(default="", alias="FILE_WATCH_PATHS")
    file_debounce_ms: int = Field(default=2000, alias="FILE_DEBOUNCE_MS")

    # ---- Hardware Telemetry ----
    hardware_collect_interval: float = Field(
        default=10.0, alias="HARDWARE_COLLECT_INTERVAL"
    )
    hardware_history_retention_minutes: int = Field(
        default=1440, alias="HARDWARE_HISTORY_RETENTION_MINUTES"
    )

    # ---- Logging ----
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # ---- Database ----
    database_url: str = Field(
        default="sqlite+aiosqlite:///./oilchem_agent.db",
        alias="DATABASE_URL",
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")

    # ---- Auth ----
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")
    jwt_secret_key: str = Field(default="dev-only-secret-key-change-me-before-production", alias="JWT_SECRET_KEY")
    jwt_expire_minutes: int = Field(default=10080, alias="JWT_EXPIRE_MINUTES")
    auth_admin_password: str = Field(default="", alias="AUTH_ADMIN_PASSWORD")
    auth_operator_password: str = Field(default="", alias="AUTH_OPERATOR_PASSWORD")
    auth_reviewer_password: str = Field(default="", alias="AUTH_REVIEWER_PASSWORD")

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
