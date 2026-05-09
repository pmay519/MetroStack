"""
app/core/config.py
Central configuration — all settings pulled from environment variables
or .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "MetroStack API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development | staging | production

    # ── Database ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "metrostack"
    POSTGRES_DB: str = "metrostack"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """Used by Alembic migrations (synchronous)."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── File Storage ──────────────────────────────────────────────────────────
    UPLOAD_DIR: Path = Path("/tmp/metrostack/uploads")
    MAX_UPLOAD_SIZE_MB: int = 2048  # 2 GB — large scan files are common

    # ── Redis / Celery ────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Analysis Defaults ─────────────────────────────────────────────────────
    # ICP alignment
    ICP_MAX_CORRESPONDENCE_DIST_MM: float = 5.0
    ICP_MAX_ITERATIONS: int = 200
    ICP_RELATIVE_FITNESS: float = 1e-6
    ICP_RELATIVE_RMSE: float = 1e-6

    # Deviation analysis
    DEVIATION_DOWNSAMPLE_VOXEL_MM: float = 0.2   # voxel size for large clouds
    DEVIATION_MAX_POINTS_REALTIME: int = 500_000  # cap for live UI response
    DEVIATION_BATCH_SIZE: int = 100_000           # chunk size for DB writes

    # Wall thickness
    WALL_THICKNESS_SAMPLE_COUNT: int = 20_000
    WALL_THICKNESS_RAY_OFFSET_MM: float = 0.01

    # ── CORS ──────────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite dev server
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
