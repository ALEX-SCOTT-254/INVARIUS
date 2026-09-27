"""Tests for the INVARIUS evolution contract."""

from dataclasses import FrozenInstanceError

import pytest

from backend.app.core.compatibility import Compatibility
from backend.app.core.errors import ValidationError
from backend.app.core.evolution import (
    EVOLUTION_CONTRACT_VERSION,
    Evolution,
)
from backend.app.core.migration import Migration
from backend.app.core.serialization import serialize


@pytest.fixture
def compatibility() -> Compatibility:
    """Return a valid compatibility assessment."""
    return Compatibility(
        compatible=True,
        contract_version="v1",
        reason="The contracts remain compatible.",
    )


@pytest.fixture
def migration() -> Migration:
    """Return a valid migration description."""
    return Migration(
        source_version="v1",
        target_version="v2",
        reason="The representation requires the new contract version.",
    )


@pytest.fixture
def evolution(
    compatibility: Compatibility,
    migration: Migration,
) -> Evolution:
    """Return a valid evolution contract."""
    return Evolution(
        evolution_id="evolution-001",
        subject="Canonical Software Representation",
        source_version="v1",
        target_version="v2",
        reason="Evolve the representation while preserving meaning.",
        compatibility=compatibility,
        migration=migration,
    )


def test_valid_evolution_is_created(evolution: Evolution) -> None:
    """A valid evolution contract can be created."""
    assert evolution.evolution_id == "evolution-001"
    assert evolution.subject == "Canonical Software Representation"
    assert evolution.source_version == "v1"
    assert evolution.target_version == "v2"
    assert evolution.reason == ("Evolve the representation while preserving meaning.")


def test_evolution_is_immutable(evolution: Evolution) -> None:
    """Evolution instances cannot be mutated."""
    with pytest.raises(FrozenInstanceError):
        evolution.subject = "Changed"


def test_default_contract_version_is_used(evolution: Evolution) -> None:
    """The default evolution contract version is v1."""
    assert evolution.evolution_contract_version == (EVOLUTION_CONTRACT_VERSION)
    assert evolution.evolution_contract_version == "v1"


@pytest.mark.parametrize(
    "field,value",
    [
        ("evolution_id", ""),
        ("evolution_id", "   "),
        ("subject", ""),
        ("subject", "   "),
        ("source_version", ""),
        ("source_version", "   "),
        ("target_version", ""),
        ("target_version", "   "),
        ("reason", ""),
        ("reason", "   "),
    ],
)
def test_empty_required_strings_are_rejected(
    compatibility: Compatibility,
    migration: Migration,
    field: str,
    value: str,
) -> None:
    """Required string fields cannot be empty."""
    values = {
        "evolution_id": "evolution-001",
        "subject": "CSR",
        "source_version": "v1",
        "target_version": "v2",
        "reason": "Evolve the representation.",
        "compatibility": compatibility,
        "migration": migration,
    }

    values[field] = value

    with pytest.raises(ValidationError):
        Evolution(**values)


@pytest.mark.parametrize(
    "field,value",
    [
        ("evolution_id", None),
        ("subject", None),
        ("source_version", None),
        ("target_version", None),
        ("reason", None),
    ],
)
def test_non_string_required_fields_are_rejected(
    compatibility: Compatibility,
    migration: Migration,
    field: str,
    value: object,
) -> None:
    """Required string fields must actually be strings."""
    values = {
        "evolution_id": "evolution-001",
        "subject": "CSR",
        "source_version": "v1",
        "target_version": "v2",
        "reason": "Evolve the representation.",
        "compatibility": compatibility,
        "migration": migration,
    }

    values[field] = value

    with pytest.raises(ValidationError):
        Evolution(**values)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "invalid",
        object(),
    ],
)
def test_invalid_compatibility_is_rejected(
    migration: Migration,
    value: object,
) -> None:
    """Evolution requires a Compatibility object."""
    with pytest.raises(ValidationError):
        Evolution(
            evolution_id="evolution-001",
            subject="CSR",
            source_version="v1",
            target_version="v2",
            reason="Evolve the representation.",
            compatibility=value,
            migration=migration,
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "invalid",
        object(),
    ],
)
def test_invalid_migration_is_rejected(
    compatibility: Compatibility,
    value: object,
) -> None:
    """Evolution requires a Migration object."""
    with pytest.raises(ValidationError):
        Evolution(
            evolution_id="evolution-001",
            subject="CSR",
            source_version="v1",
            target_version="v2",
            reason="Evolve the representation.",
            compatibility=compatibility,
            migration=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        123,
        object(),
    ],
)
def test_invalid_contract_version_is_rejected(
    compatibility: Compatibility,
    migration: Migration,
    value: object,
) -> None:
    """Evolution contract version must be a non-empty string."""
    with pytest.raises(ValidationError):
        Evolution(
            evolution_id="evolution-001",
            subject="CSR",
            source_version="v1",
            target_version="v2",
            reason="Evolve the representation.",
            compatibility=compatibility,
            migration=migration,
            evolution_contract_version=value,
        )


def test_compatibility_is_preserved(
    evolution: Evolution,
    compatibility: Compatibility,
) -> None:
    """Evolution preserves its Compatibility contract."""
    assert evolution.compatibility == compatibility


def test_migration_is_preserved(
    evolution: Evolution,
    migration: Migration,
) -> None:
    """Evolution preserves its Migration contract."""
    assert evolution.migration == migration


def test_same_source_and_target_version_are_allowed(
    compatibility: Compatibility,
    migration: Migration,
) -> None:
    """An evolution may document a same-version contract change."""
    evolution = Evolution(
        evolution_id="evolution-002",
        subject="CSR",
        source_version="v1",
        target_version="v1",
        reason="Record a non-version-changing contract evolution.",
        compatibility=compatibility,
        migration=migration,
    )

    assert evolution.source_version == evolution.target_version


def test_serialization_preserves_nested_contracts(
    evolution: Evolution,
) -> None:
    """Evolution can be serialized through the existing serializer."""
    serialized = serialize(evolution)

    assert serialized["evolution_id"] == "evolution-001"
    assert serialized["subject"] == "Canonical Software Representation"
    assert serialized["source_version"] == "v1"
    assert serialized["target_version"] == "v2"
    assert serialized["reason"] == ("Evolve the representation while preserving meaning.")
    assert serialized["compatibility"]["compatible"] is True
    assert serialized["compatibility"]["contract_version"] == "v1"
    assert serialized["migration"]["source_version"] == "v1"
    assert serialized["migration"]["target_version"] == "v2"
    assert serialized["evolution_contract_version"] == "v1"


def test_evolution_serialization_is_deterministic(
    evolution: Evolution,
) -> None:
    """Serializing the same evolution produces the same structure."""
    first = serialize(evolution)
    second = serialize(evolution)

    assert first == second


def test_evolution_has_no_runtime_timestamp() -> None:
    """Evolution remains a descriptive contract without runtime timing state."""
    assert not hasattr(Evolution, "created_at")
    assert not hasattr(Evolution, "updated_at")
    assert not hasattr(Evolution, "executed_at")
