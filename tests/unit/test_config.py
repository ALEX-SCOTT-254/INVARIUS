import pytest

from backend.app.core.config import Settings, load_settings
from backend.app.core.errors import ConfigurationError


def test_default_settings() -> None:
    settings = load_settings()

    assert settings.app_name == "INVARIUS"
    assert settings.environment == "development"
    assert settings.log_level == "INFO"


def test_settings_are_immutable() -> None:
    settings = Settings()

    with pytest.raises(AttributeError):
        settings.environment = "production"


def test_empty_environment_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVARIUS_ENVIRONMENT", "")

    with pytest.raises(ConfigurationError):
        load_settings()


def test_empty_log_level_raises_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INVARIUS_LOG_LEVEL", "")

    with pytest.raises(ConfigurationError):
        load_settings()
