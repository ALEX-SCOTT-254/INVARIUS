import pytest

from backend.app.core.errors import (
    ConfigurationError,
    InvariusError,
    SecurityError,
    ValidationError,
)
from backend.app.core.identity import APPLICATION_IDENTITY
from backend.app.core.version import __phase__, __release__, __version__


def test_application_identity() -> None:
    assert APPLICATION_IDENTITY.name == "INVARIUS"
    assert APPLICATION_IDENTITY.version == __version__
    assert APPLICATION_IDENTITY.phase == __phase__
    assert APPLICATION_IDENTITY.release == __release__


def test_error_hierarchy() -> None:
    assert issubclass(ConfigurationError, InvariusError)
    assert issubclass(ValidationError, InvariusError)
    assert issubclass(SecurityError, InvariusError)


def test_error_code() -> None:
    assert ConfigurationError("invalid config").code == "CONFIGURATION_ERROR"
    assert ValidationError("invalid data").code == "VALIDATION_ERROR"
    assert SecurityError("denied").code == "SECURITY_ERROR"


def test_error_message_is_preserved() -> None:
    error = ValidationError("Invalid project data.")

    assert error.message == "Invalid project data."
    assert str(error) == "Invalid project data."


def test_error_code_is_preserved() -> None:
    error = SecurityError("Access denied.")

    assert error.code == "SECURITY_ERROR"


def test_empty_error_message_is_rejected() -> None:
    with pytest.raises(ValueError):
        InvariusError("   ")


def test_non_string_error_message_is_rejected() -> None:
    with pytest.raises(TypeError):
        InvariusError(123)  # type: ignore[arg-type]


def test_empty_error_code_is_rejected() -> None:
    with pytest.raises(ValueError):
        InvariusError(
            "Something went wrong.",
            code="   ",
        )


def test_non_string_error_code_is_rejected() -> None:
    with pytest.raises(TypeError):
        InvariusError(
            "Something went wrong.",
            code=123,  # type: ignore[arg-type]
        )
