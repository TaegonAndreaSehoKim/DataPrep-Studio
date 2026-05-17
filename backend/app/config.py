from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="DataPrep Studio", alias="APP_NAME")
    database_url: str = Field(default="sqlite:///./dataprep_studio.db", alias="DATABASE_URL")
    storage_dir: str = Field(default="app/storage", alias="STORAGE_DIR")
    upload_dir: str = Field(default="app/storage/uploads", alias="UPLOAD_DIR")
    export_dir: str = Field(default="app/storage/exports", alias="EXPORT_DIR")
    max_upload_mb: int = Field(default=25, alias="MAX_UPLOAD_MB")
    allowed_extensions: str = Field(default=".csv", alias="ALLOWED_EXTENSIONS")
    max_preview_rows: int = Field(default=20, alias="MAX_PREVIEW_ROWS")
    default_readiness_score: int = Field(default=100, alias="DEFAULT_READINESS_SCORE")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"],
        alias="CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", populate_by_name=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
