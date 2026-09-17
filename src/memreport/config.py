"""Configuration settings for MemReport."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_CACHE_DIR = DATA_DIR / "audio_cache"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMREPORT_", extra="ignore")

    app_name: str = "MemReport"
    debug: bool = False
    secret_key: str = os.getenv("MEMREPORT_SECRET_KEY", "memreport-super-secret-key-change-in-production-32bytes")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    db_path: Path = DATA_DIR / "memreport.db"

    # Default admin credentials created on first boot
    default_admin_user: str = os.getenv("MEMREPORT_DEFAULT_USER", "admin")
    default_admin_password: str = os.getenv("MEMREPORT_DEFAULT_PASSWORD", "admin123")

    # Optional explicit Base URL (e.g. http://192.168.2.41:8125/memreport or https://reports.example.com)
    base_url: str | None = os.getenv("MEMREPORT_BASE_URL", None)


settings = Settings()
