"""Application configuration for the backend.

Minimal config that provides ``get_settings()`` so that
``backend.database`` und ``backend.main`` auf ``database_url`` und
``environment`` zugreifen können. Wir verzichten hier bewusst auf
Pydantic, damit es keine Versionskonflikte gibt.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    # Default: SQLite file in ./data/app.db (relative to project root)
    database_url: str = os.getenv("APP_DATABASE_URL", "sqlite:///./data/app.db")

    # Simple environment flag for /health endpoint
    environment: str = os.getenv("APP_ENVIRONMENT", "development")

    # Frontend-Origin (für CORS), z.B. "http://localhost:5500"
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5500")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
