import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.migration import (
    MIGRATION_CONTRACT_VERSION,
    Migration,
)


def test_valid_migration() -> None:
    migration = Migration(
        source_version="v1",
        target_version="v2",
        reason="Add required provenance metadata.",
    )

    assert migration.source_version == "v1"
    assert migration.target_version == "v2"
    assert migration.reason == ("Add required provenance metadata.")


def test_migration_contract_version() -> None:
    migration = Migration(
        source_version="v1",
        target_version="v2",
        reason="Supported migration.",
    )

    assert migration.migration_contract_version == MIGRATION_CONTRACT_VERSION


def test_migration_is_immutable() -> None:
    migration = Migration(
        source_version="v1",
        target_version="v2",
        reason="Supported migration.",
    )

    with pytest.raises(AttributeError):
        migration.source_version = "v0"  # type: ignore[misc]


def test_empty_source_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="   ",
            target_version="v2",
            reason="Supported migration.",
        )


def test_non_string_source_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version=1,  # type: ignore[arg-type]
            target_version="v2",
            reason="Supported migration.",
        )


def test_empty_target_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="v1",
            target_version="   ",
            reason="Supported migration.",
        )


def test_non_string_target_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="v1",
            target_version=2,  # type: ignore[arg-type]
            reason="Supported migration.",
        )


def test_empty_reason_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="v1",
            target_version="v2",
            reason="   ",
        )


def test_non_string_reason_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="v1",
            target_version="v2",
            reason=123,  # type: ignore[arg-type]
        )


def test_empty_migration_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="v1",
            target_version="v2",
            reason="Supported migration.",
            migration_contract_version="   ",
        )


def test_non_string_migration_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Migration(
            source_version="v1",
            target_version="v2",
            reason="Supported migration.",
            migration_contract_version=1,  # type: ignore[arg-type]
        )
