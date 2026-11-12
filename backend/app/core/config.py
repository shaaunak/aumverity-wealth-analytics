from functools import lru_cache
from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "AUMVERITY"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    CALCULATION_VERSION: str = "v1.0.0"
    REPORTING_CURRENCY: str = "USD"
    DATA_CLASSIFICATION: str = "SYNTHETIC"
    LOG_LEVEL: str = "INFO"

    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aumverity"
    POSTGRES_USER: str = "aumverity"
    POSTGRES_PASSWORD: str = "aumverity_dev_password"
    DATABASE_URL: str | None = None

    @computed_field
    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL.strip()
            if url.startswith("postgres://"):
                return "postgresql+psycopg://" + url[len("postgres://") :]
            if url.startswith("postgresql://"):
                return "postgresql+psycopg://" + url[len("postgresql://") :]
            return url
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field
    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
