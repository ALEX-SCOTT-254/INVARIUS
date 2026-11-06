"""Failure contracts for the INVARIUS platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from backend.app.core.errors import ValidationError

FAILURE_CONTRACT_VERSION = "v1"

_MAX_TEXT_LENGTH = 2_000
_MAX_REFERENCE_LENGTH = 512


class FailureCategory(StrEnum):
    """Failure categories defined by the M2.10 engineering contract."""

    RUNTIME = "runtime"
    COMPONENT_INSTANCE = "component_instance"
    OPERATION_EXECUTION = "operation_execution"
    COMMUNICATION = "communication"
    STORAGE = "storage"
    CONFIGURATION = "configuration"
    DEPENDENCY_AVAILABILITY = "dependency_availability"
    RECOVERY = "recovery"
    DIAGNOSTIC_REPORTING = "diagnostic_reporting"


class FailureConfidence(StrEnum):
    """Confidence in failure classification, not root-cause certainty."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNRESOLVED = "unresolved"


def _normalize_timestamp(value: datetime) -> datetime:
    """Require an aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Failure timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Failure timestamp must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def _validate_text(
    value: str,
    field_name: str,
    *,
    max_length: int = _MAX_TEXT_LENGTH,
    allow_empty: bool = False,
) -> str:
    """Validate bounded text without silently modifying it."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    if not allow_empty and not value.strip():
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(value) > max_length:
        raise ValidationError(f"{field_name} exceeds the maximum length.")

    return value


def _validate_optional_text(
    value: str | None,
    field_name: str,
    *,
    max_length: int = _MAX_TEXT_LENGTH,
) -> str | None:
    """Validate an optional string."""
    if value is None:
        return None

    return _validate_text(
        value,
        field_name,
        max_length=max_length,
        allow_empty=True,
    )


@dataclass(frozen=True)
class FailureRecord:
    """Immutable, descriptive record of a detected failure.

    This record does not establish root cause, authorize recovery, or
    guarantee persistence.
    """

    category: FailureCategory
    source: str
    originating_boundary: str
    safe_description: str

    failure_id: str = field(default_factory=lambda: uuid4().hex)
    contract_version: str = FAILURE_CONTRACT_VERSION
    detected_at: datetime = field(default_factory=_utc_now)

    error_type: str | None = None
    error_code: str | None = None

    runtime_id: str | None = None
    component_id: str | None = None
    component_instance_id: str | None = None

    operation_id: str | None = None
    operation_type: str | None = None
    correlation_id: str | None = None
    parent_operation_id: str | None = None

    evidence_references: tuple[str, ...] = ()
    provenance: tuple[str, ...] = ()
    related_failure_ids: tuple[str, ...] = ()

    confidence: FailureConfidence = FailureConfidence.UNRESOLVED

    def __post_init__(self) -> None:
        """Validate failure record invariants."""
        if not isinstance(self.category, FailureCategory):
            raise ValidationError("Failure category must be a FailureCategory.")

        if not isinstance(self.confidence, FailureConfidence):
            raise ValidationError("Failure confidence must be a FailureConfidence.")

        _validate_text(self.failure_id, "Failure ID", max_length=128)
        _validate_text(self.contract_version, "Contract version", max_length=64)
        _validate_text(self.source, "Failure source")
        _validate_text(self.originating_boundary, "Originating boundary")
        _validate_text(self.safe_description, "Safe description")

        object.__setattr__(
            self,
            "detected_at",
            _normalize_timestamp(self.detected_at),
        )

        for name in (
            "error_type",
            "error_code",
            "runtime_id",
            "component_id",
            "component_instance_id",
            "operation_id",
            "operation_type",
            "correlation_id",
            "parent_operation_id",
        ):
            _validate_optional_text(getattr(self, name), name)

        for name in (
            "evidence_references",
            "provenance",
            "related_failure_ids",
        ):
            value = getattr(self, name)

            if not isinstance(value, tuple):
                raise ValidationError(f"{name} must be a tuple.")

            for item in value:
                _validate_text(
                    item,
                    name,
                    max_length=_MAX_REFERENCE_LENGTH,
                )

    @classmethod
    def from_exception(
        cls,
        exception: BaseException,
        *,
        category: FailureCategory,
        source: str,
        originating_boundary: str,
        safe_description: str,
        **context: object,
    ) -> FailureRecord:
        """Capture exception type without automatically exposing its message.

        The caller must provide a safe description. Exception messages may
        contain secrets, user data, or other sensitive information.
        """
        if not isinstance(exception, BaseException):
            raise ValidationError("Exception must derive from BaseException.")

        return cls(
            category=category,
            source=source,
            originating_boundary=originating_boundary,
            safe_description=safe_description,
            error_type=type(exception).__name__,
            **context,
        )

    def to_dict(self) -> dict[str, object]:
        """Return a serialization-friendly representation."""
        return {
            "failure_id": self.failure_id,
            "contract_version": self.contract_version,
            "category": self.category.value,
            "detected_at": self.detected_at.isoformat(),
            "source": self.source,
            "originating_boundary": self.originating_boundary,
            "error_type": self.error_type,
            "error_code": self.error_code,
            "safe_description": self.safe_description,
            "runtime_id": self.runtime_id,
            "component_id": self.component_id,
            "component_instance_id": self.component_instance_id,
            "operation_id": self.operation_id,
            "operation_type": self.operation_type,
            "correlation_id": self.correlation_id,
            "parent_operation_id": self.parent_operation_id,
            "evidence_references": list(self.evidence_references),
            "provenance": list(self.provenance),
            "confidence": self.confidence.value,
            "related_failure_ids": list(self.related_failure_ids),
        }
