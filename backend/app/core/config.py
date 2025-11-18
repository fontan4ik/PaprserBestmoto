from functools import lru_cache
from typing import List

from fastapi.responses import ORJSONResponse
from pydantic import AnyHttpUrl, BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RateLimitConfig(BaseModel):
    user_limit: int = 100
    admin_limit: int = 0
    user_concurrent_tasks: int = 3
    admin_concurrent_tasks: int = 10


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env", "backend/env.example"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    secret_key: str = "dev-secret"

    telegram_bot_token: str
    telegram_bot_username: str = ""
    initial_admin_telegram_id: str | None = None

    frontend_url: AnyHttpUrl | None = None
    api_base_url: AnyHttpUrl | None = None
    allowed_origins: List[str] = ["*"]

    database_url: str

    redis_url: str
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    google_credentials: str
    google_service_account_email: str

    supabase_project_url: AnyHttpUrl | None = None
    supabase_service_key: str | None = None
    supabase_bucket: str = "commerce-files"

    log_level: str = "INFO"
    sentry_dsn: str | None = None

    rate_limit: RateLimitConfig = RateLimitConfig()
    max_file_size_mb: int = 10
    max_file_size_admin_mb: int = 50

    default_response_class = ORJSONResponse

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def celery_broker(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def celery_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

