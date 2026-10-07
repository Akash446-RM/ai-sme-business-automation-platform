"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, List, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central, validated application settings.

    Every value can be overridden through the environment or a local .env file.
    No secret or environment specific value is ever hardcoded in source.
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Application ------------------------------------------------------
    app_name: str = "AI-Powered SME Business Automation Platform"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = True
    api_v1_prefix: str = "/api/v1"

    # -- Database ---------------------------------------------------------
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "sme_ai_platform"
    database_url_override: str = ""

    # -- Security ---------------------------------------------------------
    secret_key: str = "insecure-development-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    cors_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # -- Business rules ---------------------------------------------------
    gst_rate: float = 18.0
    currency: str = "INR"
    currency_symbol: str = "Rs."
    default_lead_time_days: int = 5
    service_level_z: float = 1.65

    # -- Machine learning -------------------------------------------------
    ml_model_dir: str = "ml_models"
    forecast_default_horizon: int = 7

    # -- AI / LLM ---------------------------------------------------------
    llm_provider: Literal["offline", "openai_compat", "gemini", "ollama"] = "offline"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 45
    llm_max_output_tokens: int = 900

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Allow CORS origins to be supplied as a comma separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def database_url(self) -> str:
        """SQLAlchemy connection URL for the configured MySQL database."""
        if self.database_url_override:
            return self.database_url_override
        from urllib.parse import quote_plus

        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def server_url(self) -> str:
        """Connection URL without a database name (used to create the schema)."""
        from urllib.parse import quote_plus

        password = quote_plus(self.db_password)
        return (
            f"mysql+pymysql://{self.db_user}:{password}"
            f"@{self.db_host}:{self.db_port}/?charset=utf8mb4"
        )

    @property
    def model_dir(self) -> Path:
        """Absolute path to the directory holding persisted ML artifacts."""
        path = Path(self.ml_model_dir)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
