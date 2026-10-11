"""M2.4 capability availability and health assessment models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from backend.app.core.errors import ValidationError
from backend.app.platform.component import Component

_MAX_TEXT_LENGTH = 256
_MAX_EXPLANATION_LENGTH = 2048


class CapabilityAvailability(StrEnum):
    """Assessed availability of a declared component capability."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class HealthStatus(StrEnum):
    """Assessed operational condition of a component instance."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


def _normalize_text(
    value: object,
    field_name: str,
    *,
    max_length: int = _MAX_TEXT_LENGTH,
) -> str:
    """Validate and normalize a required non-empty text field."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError(f"{field_name} must not be empty.")

    if len(normalized) > max_length:
        raise ValidationError(f"{field_name} must not exceed {max_length} characters.")

    return normalized


def _normalize_optional_text(
    value: object,
    field_name: str,
) -> str | None:
    """Validate and normalize an optional explanation."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string or None.")

    normalized = value.strip()

    if not normalized:
        return None

    if len(normalized) > _MAX_EXPLANATION_LENGTH:
        raise ValidationError(f"{field_name} must not exceed {_MAX_EXPLANATION_LENGTH} characters.")

    return normalized


def _normalize_timestamp(value: datetime) -> datetime:
    """Require a timezone-aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Assessment timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Assessment timestamp must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _new_assessment_id() -> str:
    """Generate a unique identifier for one assessment record."""
    return str(uuid4())


def _validate_component(component: Component) -> None:
    """Require an immutable logical component definition."""
    if not isinstance(component, Component):
        raise ValidationError("Assessment component must be a Component definition.")


def _validate_assessment_id(assessment_id: str) -> str:
    """Validate an assessment record identifier."""
    return _normalize_text(assessment_id, "Assessment ID")


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    """Immutable assessment of one declared capability on one instance.

    Availability is an operational assessment, not an authorization
    decision. An available capability does not prove that its execution
    will be correct.
    """

    component: Component
    instance_id: str
    runtime_id: str
    capability: str
    availability: CapabilityAvailability
    assessed_at: datetime
    source: str
    explanation: str | None = None
    assessment_id: str = field(default_factory=_new_assessment_id)

    def __post_init__(self) -> None:
        _validate_component(self.component)

        instance_id = _normalize_text(
            self.instance_id,
            "Instance ID",
        )
        runtime_id = _normalize_text(
            self.runtime_id,
            "Runtime ID",
        )
        capability = _normalize_text(
            self.capability,
            "Capability",
        )
        source = _normalize_text(
            self.source,
            "Assessment source",
        )
        assessment_id = _validate_assessment_id(self.assessment_id)
        assessed_at = _normalize_timestamp(self.assessed_at)
        explanation = _normalize_optional_text(
            self.explanation,
            "Assessment explanation",
        )

        if not isinstance(self.availability, CapabilityAvailability):
            raise ValidationError("Capability availability must be a CapabilityAvailability value.")

        if capability not in self.component.capabilities:
            raise ValidationError(
                f"Capability '{capability}' is not declared by component "
                f"'{self.component.component_id}'."
            )

        object.__setattr__(self, "instance_id", instance_id)
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "assessment_id", assessment_id)
        object.__setattr__(self, "assessed_at", assessed_at)
        object.__setattr__(self, "explanation", explanation)

    @property
    def component_id(self) -> str:
        """Return the logical identity of the assessed component."""
        return self.component.component_id


@dataclass(frozen=True, slots=True)
class HealthAssessment:
    """Immutable assessment of a component instance's health.

    Health describes an assessed operational condition. It is not proof
    of correctness, a root-cause diagnosis, or an authorization decision.

    UNKNOWN means that the assessment does not establish a known health
    state. It must not be silently interpreted as HEALTHY.
    """

    component: Component
    instance_id: str
    runtime_id: str
    status: HealthStatus
    assessed_at: datetime
    source: str
    explanation: str | None = None
    assessment_id: str = field(default_factory=_new_assessment_id)

    def __post_init__(self) -> None:
        _validate_component(self.component)

        instance_id = _normalize_text(
            self.instance_id,
            "Instance ID",
        )
        runtime_id = _normalize_text(
            self.runtime_id,
            "Runtime ID",
        )
        source = _normalize_text(
            self.source,
            "Assessment source",
        )
        assessment_id = _validate_assessment_id(self.assessment_id)
        assessed_at = _normalize_timestamp(self.assessed_at)
        explanation = _normalize_optional_text(
            self.explanation,
            "Assessment explanation",
        )

        if not isinstance(self.status, HealthStatus):
            raise ValidationError("Health status must be a HealthStatus value.")

        object.__setattr__(self, "instance_id", instance_id)
        object.__setattr__(self, "runtime_id", runtime_id)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "assessment_id", assessment_id)
        object.__setattr__(self, "assessed_at", assessed_at)
        object.__setattr__(self, "explanation", explanation)

    @property
    def component_id(self) -> str:
        """Return the logical identity of the assessed component."""
        return self.component.component_id
