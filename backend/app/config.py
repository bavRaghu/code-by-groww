"""
Application configuration.

Settings are read from environment variables (or a .env file via python-dotenv).
All values have sensible local-development defaults so the app starts without
any additional setup during the skeleton phase.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_name: str = "Smart Market Watchlist"
    app_version: str = "0.1.0"
    debug: bool = False

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = (
        "postgresql+asyncpg://smw_user:smw_password@localhost:5432/smw_db"
    )

    # ------------------------------------------------------------------ #
    # CORS – allow the Vite dev server by default
    # ------------------------------------------------------------------ #
    cors_origins: list[str] = ["http://localhost:5173"]


# Module-level singleton – import this everywhere else.
settings = Settings()
