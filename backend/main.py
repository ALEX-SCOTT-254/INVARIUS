"""
INVARIUS Main Application

Entry point for the INVARIUS platform.
"""

from __future__ import annotations

from backend.app.core.config import Settings, load_settings


class MainApplication:
    """Main application engine."""

    VERSION = "0.1.0"

    def __init__(self) -> None:
        self.settings: Settings | None = None

    def start(self) -> None:
        """Validate configuration before reporting successful startup."""

        settings = load_settings()
        self.settings = settings

        print("=" * 60)
        print(settings.app_name)
        print(f"Version: {self.VERSION}")
        print(f"Environment: {settings.environment}")
        print(f"Log level: {settings.log_level}")
        print("Status : ONLINE")
        print("=" * 60)
        print("Engine initialized successfully.")
        print("Ready for Phase 1 development.")
        print("=" * 60)


def main() -> None:
    """Application entry point."""

    app = MainApplication()
    app.start()


if __name__ == "__main__":
    main()
