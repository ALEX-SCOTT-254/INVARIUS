"""Tests for the INVARIUS application entry point."""

import pytest

from backend.app.core.config import Settings
from backend.app.core.errors import ConfigurationError
from backend.main import MainApplication


def test_start_loads_settings_before_reporting_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = Settings(
        environment="test",
        log_level="DEBUG",
    )
    monkeypatch.setenv("INVARIUS_ENVIRONMENT", "test")
    monkeypatch.setenv("INVARIUS_LOG_LEVEL", "DEBUG")

    app = MainApplication()
    app.start()

    output = capsys.readouterr().out

    assert app.settings == expected
    assert "Environment: test" in output
    assert "Log level: DEBUG" in output
    assert "Status : ONLINE" in output
    assert "Engine initialized successfully." in output


def test_start_does_not_report_success_for_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("INVARIUS_ENVIRONMENT", "")

    app = MainApplication()

    with pytest.raises(ConfigurationError):
        app.start()

    output = capsys.readouterr().out

    assert app.settings is None
    assert "ONLINE" not in output
    assert "initialized successfully" not in output
