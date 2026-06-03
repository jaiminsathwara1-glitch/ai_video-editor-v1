"""
Centralised application settings via pydantic-settings.
All values are read from environment variables / .env file.
"""
from __future__ import annotations

from pathlib import Path
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: str = "development"
    secret_key: str = "insecure-default-change-me"
    debug: bool = True
    log_level: str = "INFO"

    # ── Storage ───────────────────────────────────────────────────────────────
    upload_dir: Path = Path("./storage/uploads")
    thumbnail_dir: Path = Path("./storage/thumbnails")
    export_dir: Path = Path("./storage/exports")
    temp_dir: Path = Path("./storage/temp")
    max_upload_size_gb: float = 20.0

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./storage/db/videoedit.db"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ── FFmpeg ────────────────────────────────────────────────────────────────
    ffmpeg_path: str = r"E:\ai-video_editing\venv\Scripts\ffmpeg.exe"
    ffprobe_path: str = r"E:\ai-video_editing\venv\Scripts\ffprobe.exe"

    # ── AI ────────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_base_url: str = ""   # Leave empty for default OpenAI. Set to Groq/other provider URL.
    openai_model: str = "gpt-4o-mini"
    whisper_model: str = "base"

    # ── Thumbnails ────────────────────────────────────────────────────────────
    thumbnail_width: int = 320
    thumbnail_height: int = 180
    thumbnail_count: int = 5

    # ── Upload chunks ─────────────────────────────────────────────────────────
    chunk_size_mb: int = 10

    # ── Performance ───────────────────────────────────────────────────────────
    celery_concurrency: int = 4
    analysis_timeout_seconds: int = 3600

    @field_validator("upload_dir", "thumbnail_dir", "export_dir", "temp_dir", mode="before")
    @classmethod
    def make_path(cls, v: str | Path) -> Path:
        return Path(v)

    @property
    def max_upload_size_bytes(self) -> int:
        return int(self.max_upload_size_gb * 1024 ** 3)

    def create_dirs(self) -> None:
        """Ensure all storage directories exist."""
        for d in (self.upload_dir, self.thumbnail_dir, self.export_dir, self.temp_dir):
            d.mkdir(parents=True, exist_ok=True)
        # SQLite DB directory
        Path(self.database_url.split("///")[-1]).parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.create_dirs()
    return s
