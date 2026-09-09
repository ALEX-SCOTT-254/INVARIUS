import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.ids import (
    CANONICAL_ID_VERSION,
    IdentifierType,
    canonical_id,
    is_valid_canonical_id,
)


def test_canonical_id_is_deterministic() -> None:
    first = canonical_id(
        IdentifierType.PROJECT,
        "C:/Projects/INVARIUS",
    )
    second = canonical_id(
        IdentifierType.PROJECT,
        "C:/Projects/INVARIUS",
    )

    assert first == second


def test_canonical_id_is_typed() -> None:
    project_id = canonical_id(
        IdentifierType.PROJECT,
        "example",
    )
    file_id = canonical_id(
        IdentifierType.FILE,
        "example",
    )

    assert project_id != file_id
    assert project_id.startswith("v1:project:")
    assert file_id.startswith("v1:file:")


def test_canonical_id_is_versioned() -> None:
    value = canonical_id(
        IdentifierType.SYMBOL,
        "backend.app.core.config.Settings",
    )

    assert value.startswith(f"{CANONICAL_ID_VERSION}:")
    assert is_valid_canonical_id(value)


def test_canonical_id_is_valid() -> None:
    value = canonical_id(
        IdentifierType.SYMBOL,
        "backend.app.core.config.Settings",
    )

    assert is_valid_canonical_id(value)


def test_empty_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        canonical_id(
            IdentifierType.PROJECT,
            "   ",
        )


def test_non_string_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError):
        canonical_id(
            IdentifierType.PROJECT,
            123,  # type: ignore[arg-type]
        )


def test_invalid_identifier_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        canonical_id(
            "project",  # type: ignore[arg-type]
            "example",
        )


def test_unicode_normalization_is_deterministic() -> None:
    composed = "café"
    decomposed = "cafe\u0301"

    assert canonical_id(
        IdentifierType.SYMBOL,
        composed,
    ) == canonical_id(
        IdentifierType.SYMBOL,
        decomposed,
    )


def test_case_is_preserved() -> None:
    upper = canonical_id(
        IdentifierType.SYMBOL,
        "Example",
    )
    lower = canonical_id(
        IdentifierType.SYMBOL,
        "example",
    )

    assert upper != lower
