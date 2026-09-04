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
