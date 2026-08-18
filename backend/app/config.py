from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ai_api_key: str = ""
    ai_base_url: str = "https://api.deepseek.com"
    ai_model: str = "deepseek-chat"
    admin_password: str = "zhuanglema"
    host: str = "127.0.0.1"
    port: int = 8765
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'zlm.db').as_posix()}"
    version_cache_hours: int = 6


settings = Settings()
