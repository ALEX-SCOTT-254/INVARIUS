"""
INVARIUS Main Application

Entry point for the INVARIUS platform.
"""

from __future__ import annotations


class MainApplication:
    """Main application engine."""

    VERSION = "0.1.0"

    def start(self) -> None:
        """Start the INVARIUS application."""
        print("=" * 60)
        print("INVARIUS")
        print(f"Version: {self.VERSION}")
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
