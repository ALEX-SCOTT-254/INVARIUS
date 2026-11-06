"""Unit tests for the M2.10 failure model."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.failures import (
    FAILURE_CONTRACT_VERSION,
    FailureCategory,
    FailureConfidence,
    FailureRecord,
)


def make_failure(**overrides: object) -> FailureRecord:
    """Create a valid failure record for testing."""
    values: dict[str, object] = {
        "category": FailureCategory.OPERATION_EXECUTION,
        "source": "unit-test",
        "originating_boundary": "operation-execution",
        "safe_description": "Operation execution failed.",
    }
    values.update(overrides)
    return FailureRecord(**values)


def test_failure_record_has_stable_identity_and_contract_version() -> None:
    failure = make_failure()

    assert failure.failure_id
    assert failure.contract_version == FAILURE_CONTRACT_VERSION
    assert failure.failure_id != make_failure().failure_id


def test_failure_record_normalizes_timestamp_to_utc() -> None:
    offset = timezone(timedelta(hours=3))
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=offset)

    failure = make_failure(detected_at=timestamp)

    assert failure.detected_at.tzinfo == timezone.utc
    assert failure.detected_at.hour == 9


def test_failure_record_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        make_failure(detected_at=datetime(2026, 1, 1, 12, 0))


def test_failure_record_is_immutable() -> None:
    failure = make_failure()

    with pytest.raises(FrozenInstanceError):
        failure.safe_description = "Changed"  # type: ignore[misc]


def test_failure_category_must_be_valid_enum() -> None:
    with pytest.raises(ValidationError, match="FailureCategory"):
        make_failure(category="unknown")  # type: ignore[arg-type]


def test_failure_confidence_must_be_valid_enum() -> None:
    with pytest.raises(ValidationError, match="FailureConfidence"):
        make_failure(confidence="certain")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("failure_id", ""),
        ("source", ""),
        ("originating_boundary", ""),
        ("safe_description", ""),
    ],
)
def test_required_text_fields_reject_empty_values(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        make_failure(**{field_name: value})


def test_failure_record_rejects_overlong_description() -> None:
    with pytest.raises(ValidationError, match="maximum length"):
        make_failure(safe_description="x" * 2001)


def test_failure_record_validates_reference_tuples() -> None:
    with pytest.raises(ValidationError, match="must be a tuple"):
        make_failure(evidence_references=["evidence-1"])  # type: ignore[arg-type]


def test_failure_record_validates_reference_values() -> None:
    with pytest.raises(ValidationError):
        make_failure(evidence_references=("",))


def test_failure_record_preserves_context_and_references() -> None:
    failure = make_failure(
        runtime_id="runtime-1",
        component_id="component-1",
        component_instance_id="instance-1",
        operation_id="operation-1",
        operation_type="analysis",
        correlation_id="correlation-1",
        parent_operation_id="parent-1",
        evidence_references=("evidence-1",),
        provenance=("collector-a",),
        related_failure_ids=("failure-parent",),
        confidence=FailureConfidence.MEDIUM,
    )

    assert failure.runtime_id == "runtime-1"
    assert failure.component_id == "component-1"
    assert failure.component_instance_id == "instance-1"
    assert failure.operation_id == "operation-1"
    assert failure.operation_type == "analysis"
    assert failure.correlation_id == "correlation-1"
    assert failure.parent_operation_id == "parent-1"
    assert failure.evidence_references == ("evidence-1",)
    assert failure.provenance == ("collector-a",)
    assert failure.related_failure_ids == ("failure-parent",)
    assert failure.confidence == FailureConfidence.MEDIUM


def test_from_exception_captures_type_without_exposing_message() -> None:
    exception = RuntimeError("sensitive-token-should-not-be-recorded")

    failure = FailureRecord.from_exception(
        exception,
        category=FailureCategory.RUNTIME,
        source="runtime",
        originating_boundary="runtime-startup",
        safe_description="Runtime startup failed.",
    )

    assert failure.error_type == "RuntimeError"
    assert "sensitive-token" not in failure.safe_description
    assert "sensitive-token" not in str(failure.to_dict())


def test_from_exception_rejects_non_exception() -> None:
    with pytest.raises(ValidationError, match="BaseException"):
        FailureRecord.from_exception(
            "not-an-exception",  # type: ignore[arg-type]
            category=FailureCategory.RUNTIME,
            source="runtime",
            originating_boundary="runtime-startup",
            safe_description="Runtime startup failed.",
        )


def test_to_dict_returns_serializable_values() -> None:
    failure = make_failure(
        evidence_references=("evidence-1",),
        provenance=("source-a",),
        related_failure_ids=("failure-previous",),
    )

    result = failure.to_dict()

    assert result["failure_id"] == failure.failure_id
    assert result["category"] == FailureCategory.OPERATION_EXECUTION.value
    assert result["confidence"] == FailureConfidence.UNRESOLVED.value
    assert isinstance(result["detected_at"], str)
    assert result["evidence_references"] == ["evidence-1"]
    assert result["provenance"] == ["source-a"]
    assert result["related_failure_ids"] == ["failure-previous"]


@pytest.mark.parametrize(
    "category",
    list(FailureCategory),
)
def test_all_contract_failure_categories_are_supported(
    category: FailureCategory,
) -> None:
    failure = make_failure(category=category)

    assert failure.category is category
