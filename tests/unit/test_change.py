import pytest

from backend.app.core.change import (
    CHANGE_CONTRACT_VERSION,
    ChangeContract,
    ChangeType,
)
from backend.app.core.errors import ValidationError


def test_valid_change_contract() -> None:
    change = ChangeContract(
        change_id="change-001",
        change_type=ChangeType.SOURCE,
        source_version="v1",
        target_version="v2",
        reason="Update source representation.",
    )

    assert change.change_id == "change-001"
    assert change.change_type is ChangeType.SOURCE
    assert change.source_version == "v1"
    assert change.target_version == "v2"
    assert change.reason == "Update source representation."


def test_change_contract_version() -> None:
    change = ChangeContract(
        change_id="change-001",
        change_type=ChangeType.SOURCE,
        source_version="v1",
        target_version="v2",
        reason="Update source representation.",
    )

    assert change.change_contract_version == CHANGE_CONTRACT_VERSION
    assert change.change_contract_version == "v1"


def test_change_contract_is_immutable() -> None:
    change = ChangeContract(
        change_id="change-001",
        change_type=ChangeType.SOURCE,
        source_version="v1",
        target_version="v2",
        reason="Update source representation.",
    )

    with pytest.raises(AttributeError):
        change.reason = "Changed reason."  # type: ignore[misc]


@pytest.mark.parametrize(
    "change_id",
    ["", "   "],
)
def test_empty_change_id_is_rejected(change_id: str) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id=change_id,
            change_type=ChangeType.SOURCE,
            source_version="v1",
            target_version="v2",
            reason="Update source representation.",
        )


@pytest.mark.parametrize(
    "change_id",
    [123, None],
)
def test_non_string_change_id_is_rejected(change_id: object) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id=change_id,  # type: ignore[arg-type]
            change_type=ChangeType.SOURCE,
            source_version="v1",
            target_version="v2",
            reason="Update source representation.",
        )


def test_invalid_change_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id="change-001",
            change_type="source",  # type: ignore[arg-type]
            source_version="v1",
            target_version="v2",
            reason="Update source representation.",
        )


@pytest.mark.parametrize(
    "source_version",
    ["", "   "],
)
def test_empty_source_version_is_rejected(
    source_version: str,
) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id="change-001",
            change_type=ChangeType.SOURCE,
            source_version=source_version,
            target_version="v2",
            reason="Update source representation.",
        )


@pytest.mark.parametrize(
    "source_version",
    [123, None],
)
def test_non_string_source_version_is_rejected(
    source_version: object,
) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id="change-001",
            change_type=ChangeType.SOURCE,
            source_version=source_version,  # type: ignore[arg-type]
            target_version="v2",
            reason="Update source representation.",
        )


@pytest.mark.parametrize(
    "target_version",
    ["", "   "],
)
def test_empty_target_version_is_rejected(
    target_version: str,
) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id="change-001",
            change_type=ChangeType.SOURCE,
            source_version="v1",
            target_version=target_version,
            reason="Update source representation.",
        )


@pytest.mark.parametrize(
    "target_version",
    [123, None],
)
def test_non_string_target_version_is_rejected(
    target_version: object,
) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id="change-001",
            change_type=ChangeType.SOURCE,
            source_version="v1",
            target_version=target_version,  # type: ignore[arg-type]
            reason="Update source representation.",
        )


@pytest.mark.parametrize(
    ("reason", "change_contract_version"),
    [
        ("", "v1"),
        ("   ", "v1"),
        ("Valid reason.", ""),
        ("Valid reason.", "   "),
        (123, "v1"),
        ("Valid reason.", 123),
    ],
)
def test_invalid_reason_or_contract_version_is_rejected(
    reason: object,
    change_contract_version: object,
) -> None:
    with pytest.raises(ValidationError):
        ChangeContract(
            change_id="change-001",
            change_type=ChangeType.SOURCE,
            source_version="v1",
            target_version="v2",
            reason=reason,  # type: ignore[arg-type]
            change_contract_version=change_contract_version,  # type: ignore[arg-type]
        )
