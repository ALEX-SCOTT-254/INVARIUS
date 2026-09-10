from datetime import datetime, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.operation import (
    OPERATION_CONTRACT_VERSION,
    Operation,
)


def test_operation_can_be_created() -> None:
    started_at = datetime(
        2026,
        9,
        10,
        12,
        0,
        tzinfo=timezone.utc,
    )

    operation = Operation(
        operation_id="operation-001",
        operation_type="project_discovery",
        started_at=started_at,
    )

    assert operation.operation_id == "operation-001"
    assert operation.operation_type == "project_discovery"
    assert operation.started_at == started_at
    assert operation.contract_version == OPERATION_CONTRACT_VERSION


def test_operation_is_immutable() -> None:
    operation = Operation(
        operation_id="operation-001",
        operation_type="project_discovery",
        started_at=datetime(
            2026,
            9,
            10,
            12,
            0,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(AttributeError):
        operation.operation_id = "operation-002"  # type: ignore[misc]


def test_empty_operation_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="   ",
            operation_type="project_discovery",
            started_at=datetime.now(timezone.utc),
        )


def test_non_string_operation_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id=123,  # type: ignore[arg-type]
            operation_type="project_discovery",
            started_at=datetime.now(timezone.utc),
        )


def test_empty_operation_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="operation-001",
            operation_type="   ",
            started_at=datetime.now(timezone.utc),
        )


def test_non_string_operation_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="operation-001",
            operation_type=123,  # type: ignore[arg-type]
            started_at=datetime.now(timezone.utc),
        )


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="operation-001",
            operation_type="project_discovery",
            started_at=datetime(2026, 9, 10, 12, 0),
        )


def test_non_datetime_start_time_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="operation-001",
            operation_type="project_discovery",
            started_at="2026-09-10T12:00:00+00:00",  # type: ignore[arg-type]
        )


def test_empty_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="operation-001",
            operation_type="project_discovery",
            started_at=datetime.now(timezone.utc),
            contract_version="   ",
        )


def test_non_string_contract_version_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Operation(
            operation_id="operation-001",
            operation_type="project_discovery",
            started_at=datetime.now(timezone.utc),
            contract_version=123,  # type: ignore[arg-type]
        )
