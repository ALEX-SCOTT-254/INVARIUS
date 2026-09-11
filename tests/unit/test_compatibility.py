import pytest

from backend.app.core.compatibility import (
    COMPATIBILITY_CONTRACT_VERSION,
    Compatibility,
)
from backend.app.core.errors import ValidationError


def test_compatible_contract() -> None:
    result = Compatibility(
        compatible=True,
        contract_version="v1",
        reason="Contract version v1 is supported.",
    )

    assert result.compatible is True
    assert result.contract_version == "v1"
    assert result.reason == "Contract version v1 is supported."


def test_incompatible_contract() -> None:
    result = Compatibility(
        compatible=False,
        contract_version="v2",
        reason="Contract version v2 is not supported.",
    )

    assert result.compatible is False
    assert result.contract_version == "v2"
    assert result.reason == "Contract version v2 is not supported."


def test_compatibility_contract_version() -> None:
    result = Compatibility(
        compatible=True,
        contract_version="v1",
        reason="Supported.",
    )

    assert result.compatibility_contract_version == COMPATIBILITY_CONTRACT_VERSION


def test_compatibility_is_immutable() -> None:
    result = Compatibility(
        compatible=True,
        contract_version="v1",
        reason="Supported.",
    )

    with pytest.raises(AttributeError):
        result.compatible = False  # type: ignore[misc]


def test_non_boolean_compatibility_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible="yes",  # type: ignore[arg-type]
            contract_version="v1",
            reason="Supported.",
        )


def test_empty_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible=True,
            contract_version="   ",
            reason="Supported.",
        )


def test_non_string_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible=True,
            contract_version=1,  # type: ignore[arg-type]
            reason="Supported.",
        )


def test_empty_reason_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible=True,
            contract_version="v1",
            reason="   ",
        )


def test_non_string_reason_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible=True,
            contract_version="v1",
            reason=123,  # type: ignore[arg-type]
        )


def test_empty_compatibility_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible=True,
            contract_version="v1",
            reason="Supported.",
            compatibility_contract_version="   ",
        )


def test_non_string_compatibility_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Compatibility(
            compatible=True,
            contract_version="v1",
            reason="Supported.",
            compatibility_contract_version=1,  # type: ignore[arg-type]
        )
