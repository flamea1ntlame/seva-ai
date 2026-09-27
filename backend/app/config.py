import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "SEVA AI API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"

    DATABASE_URL: str = "postgresql+asyncpg://anseljustin@localhost:5432/seva_db"
    SYNC_DATABASE_URL: str = "postgresql://anseljustin@localhost:5432/seva_db"

    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "super-secret-key-change-in-production-seva-ai"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        env = (self.ENVIRONMENT or os.getenv("ENVIRONMENT", "")).strip().lower()
        is_production = env in ("production", "prod") or bool(os.getenv("RENDER"))
        known_defaults = {
            "super-secret-key-change-in-production-seva-ai",
            "secret",
            "changeme",
            "secret_key",
            "default_secret",
            "your-secret-key",
        }
        secret = (self.SECRET_KEY or "").strip()
        if is_production:
            if not secret or secret in known_defaults:
                raise ValueError(
                    "Production configuration error: SECRET_KEY environment variable must be set to a secure, non-default key."
                )
        return self

    BACKEND_CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://seva-ai.onrender.com",
    ]
    FRONTEND_URL: str = ""

    @field_validator("BACKEND_CORS_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        origins: List[str] = []
        if isinstance(v, str):
            if v.startswith("["):
                try:
                    import json
                    parsed = json.loads(v)
                    origins = [str(i).strip().rstrip("/") for i in parsed if str(i).strip()]
                except Exception:
                    origins = [i.strip().rstrip("/") for i in v.split(",") if i.strip()]
            else:
                origins = [i.strip().rstrip("/") for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple, set)):
            origins = [str(i).strip().rstrip("/") for i in v if str(i).strip()]

        frontend_url = os.getenv("FRONTEND_URL") or os.getenv("NEXT_PUBLIC_FRONTEND_URL")
        if frontend_url and frontend_url.strip().rstrip("/") not in origins:
            origins.append(frontend_url.strip().rstrip("/"))

        return origins

    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_STORAGE_BUCKET: str = "seva-documents"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
