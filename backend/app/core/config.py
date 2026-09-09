"""Application configuration for INVARIUS."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .errors import ConfigurationError


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    environment: str = "development"
    log_level: str = "INFO"
    app_name: str = "INVARIUS"


def load_settings() -> Settings:
    """Load validated settings from the environment."""

    environment = os.getenv("INVARIUS_ENVIRONMENT", "development").strip()
    log_level = os.getenv("INVARIUS_LOG_LEVEL", "INFO").strip().upper()

    if not environment:
        raise ConfigurationError("INVARIUS_ENVIRONMENT cannot be empty.")

    if not log_level:
        raise ConfigurationError("INVARIUS_LOG_LEVEL cannot be empty.")

    return Settings(
        environment=environment,
        log_level=log_level,
    )


settings = load_settings()
