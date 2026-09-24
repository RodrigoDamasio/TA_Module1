import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_path: str
    base_url: str
    frontend_origins: list[str]


def get_settings() -> Settings:
    return Settings(
        database_path=os.getenv("DATABASE_PATH", "urls.db"),
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        frontend_origins=[
            origin.strip().rstrip("/")
            for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
            if origin.strip()
        ],
    )
