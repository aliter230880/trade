"""Настройки приложения. Читаются из .env / переменных окружения."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "127.0.0.1"
    app_port: int = 8000

    default_exchange: str = "bybit"
    default_testnet: bool = True

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    encryption_key: str = Field(default="dev-only-change-me")

    db_path: Path = DATA_DIR / "bot.db"


settings = Settings()
