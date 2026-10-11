"""Tests for the M2.4 capability and health assessment models."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.capability import (
    CapabilityAssessment,
    CapabilityAvailability,
    HealthAssessment,
    HealthStatus,
)
from backend.app.platform.component import Component


def make_component(
    *,
    component_id: str = "component-a",
    capabilities: frozenset[str] = frozenset({"inspect", "repair"}),
) -> Component:
    """Create a component definition for assessment tests."""
    return Component(
        component_id=component_id,
        name="sample",
        contract_version="1.0",
        implementation_version="1.0",
        capabilities=capabilities,
        declared_dependencies=frozenset(),
    )


def make_capability_assessment(
    *,
    availability: CapabilityAvailability = CapabilityAvailability.AVAILABLE,
    capability: str = "inspect",
    assessed_at: datetime | None = None,
    explanation: str | None = None,
    source: str = "unit-test",
) -> CapabilityAssessment:
    """Create a valid capability assessment."""
    return CapabilityAssessment(
        component=make_component(),
        instance_id="instance-a",
        runtime_id="runtime-a",
        capability=capability,
        availability=availability,
        assessed_at=assessed_at or datetime.now(timezone.utc),
        source=source,
        explanation=explanation,
    )


def make_health_assessment(
    *,
    status: HealthStatus = HealthStatus.HEALTHY,
    assessed_at: datetime | None = None,
    explanation: str | None = None,
    source: str = "unit-test",
) -> HealthAssessment:
    """Create a valid health assessment."""
    return HealthAssessment(
        component=make_component(),
        instance_id="instance-a",
        runtime_id="runtime-a",
        status=status,
        assessed_at=assessed_at or datetime.now(timezone.utc),
        source=source,
        explanation=explanation,
    )


def test_capability_assessment_preserves_identity_and_provenance() -> None:
    assessment = make_capability_assessment()

    assert assessment.component_id == "component-a"
    assert assessment.instance_id == "instance-a"
    assert assessment.runtime_id == "runtime-a"
    assert assessment.capability == "inspect"
    assert assessment.availability is CapabilityAvailability.AVAILABLE
    assert assessment.source == "unit-test"
    assert assessment.assessment_id
    assert assessment.assessed_at.tzinfo is not None


def test_capability_assessment_accepts_unknown_availability() -> None:
    assessment = make_capability_assessment(
        availability=CapabilityAvailability.UNKNOWN,
    )

    assert assessment.availability is CapabilityAvailability.UNKNOWN


def test_capability_assessment_accepts_unavailable_state() -> None:
    assessment = make_capability_assessment(
        availability=CapabilityAvailability.UNAVAILABLE,
    )

    assert assessment.availability is CapabilityAvailability.UNAVAILABLE


def test_capability_assessment_requires_declared_capability() -> None:
    with pytest.raises(ValidationError):
        make_capability_assessment(capability="undeclared-capability")


def test_capability_assessment_accepts_each_declared_capability() -> None:
    for capability in ("inspect", "repair"):
        assessment = make_capability_assessment(capability=capability)
        assert assessment.capability == capability


@pytest.mark.parametrize(
    "availability",
    [
        CapabilityAvailability.UNKNOWN,
        CapabilityAvailability.AVAILABLE,
        CapabilityAvailability.UNAVAILABLE,
    ],
)
def test_capability_assessment_accepts_valid_availability_values(
    availability: CapabilityAvailability,
) -> None:
    assessment = make_capability_assessment(availability=availability)

    assert assessment.availability is availability


def test_capability_assessment_rejects_plain_string_availability() -> None:
    with pytest.raises(ValidationError):
        CapabilityAssessment(
            component=make_component(),
            instance_id="instance-a",
            runtime_id="runtime-a",
            capability="inspect",
            availability="available",  # type: ignore[arg-type]
            assessed_at=datetime.now(timezone.utc),
            source="unit-test",
        )


@pytest.mark.parametrize(
    "status",
    [
        HealthStatus.UNKNOWN,
        HealthStatus.HEALTHY,
        HealthStatus.DEGRADED,
        HealthStatus.UNHEALTHY,
    ],
)
def test_health_assessment_accepts_each_valid_status(
    status: HealthStatus,
) -> None:
    assessment = make_health_assessment(status=status)

    assert assessment.status is status


def test_unknown_health_is_not_silently_marked_healthy() -> None:
    assessment = make_health_assessment(status=HealthStatus.UNKNOWN)

    assert assessment.status is HealthStatus.UNKNOWN
    assert assessment.status is not HealthStatus.HEALTHY


def test_health_assessment_preserves_identity_and_provenance() -> None:
    assessment = make_health_assessment()

    assert assessment.component_id == "component-a"
    assert assessment.instance_id == "instance-a"
    assert assessment.runtime_id == "runtime-a"
    assert assessment.status is HealthStatus.HEALTHY
    assert assessment.source == "unit-test"
    assert assessment.assessment_id
    assert assessment.assessed_at.tzinfo is not None


def test_health_assessment_rejects_plain_string_status() -> None:
    with pytest.raises(ValidationError):
        HealthAssessment(
            component=make_component(),
            instance_id="instance-a",
            runtime_id="runtime-a",
            status="healthy",  # type: ignore[arg-type]
            assessed_at=datetime.now(timezone.utc),
            source="unit-test",
        )


def test_default_assessment_ids_are_unique() -> None:
    capability_first = make_capability_assessment()
    capability_second = make_capability_assessment()
    health_first = make_health_assessment()
    health_second = make_health_assessment()

    assert capability_first.assessment_id != capability_second.assessment_id
    assert health_first.assessment_id != health_second.assessment_id


def test_capability_assessment_normalizes_text_fields() -> None:
    assessment = CapabilityAssessment(
        component=make_component(),
        instance_id="  instance-a  ",
        runtime_id="  runtime-a  ",
        capability="  inspect  ",
        availability=CapabilityAvailability.AVAILABLE,
        assessed_at=datetime.now(timezone.utc),
        source="  test-runner  ",
        explanation="  Assessment completed.  ",
        assessment_id="  assessment-a  ",
    )

    assert assessment.instance_id == "instance-a"
    assert assessment.runtime_id == "runtime-a"
    assert assessment.capability == "inspect"
    assert assessment.source == "test-runner"
    assert assessment.explanation == "Assessment completed."
    assert assessment.assessment_id == "assessment-a"


def test_health_assessment_normalizes_text_fields() -> None:
    assessment = HealthAssessment(
        component=make_component(),
        instance_id="  instance-a  ",
        runtime_id="  runtime-a  ",
        status=HealthStatus.DEGRADED,
        assessed_at=datetime.now(timezone.utc),
        source="  monitor  ",
        explanation="  Delayed responses.  ",
        assessment_id="  health-a  ",
    )

    assert assessment.instance_id == "instance-a"
    assert assessment.runtime_id == "runtime-a"
    assert assessment.source == "monitor"
    assert assessment.explanation == "Delayed responses."
    assert assessment.assessment_id == "health-a"


def test_blank_explanation_normalizes_to_none() -> None:
    capability = make_capability_assessment(explanation="   ")
    health = make_health_assessment(explanation="   ")

    assert capability.explanation is None
    assert health.explanation is None


@pytest.mark.parametrize(
    "field_name",
    ["instance_id", "runtime_id", "capability", "source", "assessment_id"],
)
def test_capability_assessment_rejects_empty_required_text(
    field_name: str,
) -> None:
    arguments: dict[str, object] = {
        "component": make_component(),
        "instance_id": "instance-a",
        "runtime_id": "runtime-a",
        "capability": "inspect",
        "availability": CapabilityAvailability.AVAILABLE,
        "assessed_at": datetime.now(timezone.utc),
        "source": "unit-test",
    }
    arguments[field_name] = "   "

    with pytest.raises(ValidationError):
        CapabilityAssessment(**arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    ["instance_id", "runtime_id", "source", "assessment_id"],
)
def test_health_assessment_rejects_empty_required_text(
    field_name: str,
) -> None:
    arguments: dict[str, object] = {
        "component": make_component(),
        "instance_id": "instance-a",
        "runtime_id": "runtime-a",
        "status": HealthStatus.HEALTHY,
        "assessed_at": datetime.now(timezone.utc),
        "source": "unit-test",
    }
    arguments[field_name] = "   "

    with pytest.raises(ValidationError):
        HealthAssessment(**arguments)  # type: ignore[arg-type]


def test_capability_assessment_normalizes_timestamp_to_utc() -> None:
    offset = timezone(timedelta(hours=3))
    timestamp = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=offset,
    )

    assessment = make_capability_assessment(assessed_at=timestamp)

    assert assessment.assessed_at.utcoffset() == timedelta(0)
    assert assessment.assessed_at.hour == 9


def test_health_assessment_normalizes_timestamp_to_utc() -> None:
    offset = timezone(timedelta(hours=-5))
    timestamp = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=offset,
    )

    assessment = make_health_assessment(assessed_at=timestamp)

    assert assessment.assessed_at.utcoffset() == timedelta(0)
    assert assessment.assessed_at.hour == 17


def test_capability_assessment_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        make_capability_assessment(
            assessed_at=datetime(2026, 1, 1),
        )


def test_health_assessment_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        make_health_assessment(
            assessed_at=datetime(2026, 1, 1),
        )


def test_capability_assessment_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(ValidationError):
        CapabilityAssessment(
            component=make_component(),
            instance_id="instance-a",
            runtime_id="runtime-a",
            capability="inspect",
            availability=CapabilityAvailability.AVAILABLE,
            assessed_at="not-a-datetime",  # type: ignore[arg-type]
            source="unit-test",
        )


def test_health_assessment_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(ValidationError):
        HealthAssessment(
            component=make_component(),
            instance_id="instance-a",
            runtime_id="runtime-a",
            status=HealthStatus.HEALTHY,
            assessed_at="not-a-datetime",  # type: ignore[arg-type]
            source="unit-test",
        )


def test_capability_assessment_rejects_non_component_definition() -> None:
    with pytest.raises(ValidationError):
        CapabilityAssessment(
            component="component-a",  # type: ignore[arg-type]
            instance_id="instance-a",
            runtime_id="runtime-a",
            capability="inspect",
            availability=CapabilityAvailability.AVAILABLE,
            assessed_at=datetime.now(timezone.utc),
            source="unit-test",
        )


def test_health_assessment_rejects_non_component_definition() -> None:
    with pytest.raises(ValidationError):
        HealthAssessment(
            component="component-a",  # type: ignore[arg-type]
            instance_id="instance-a",
            runtime_id="runtime-a",
            status=HealthStatus.HEALTHY,
            assessed_at=datetime.now(timezone.utc),
            source="unit-test",
        )


def test_capability_assessment_rejects_non_string_explanation() -> None:
    with pytest.raises(ValidationError):
        CapabilityAssessment(
            component=make_component(),
            instance_id="instance-a",
            runtime_id="runtime-a",
            capability="inspect",
            availability=CapabilityAvailability.AVAILABLE,
            assessed_at=datetime.now(timezone.utc),
            source="unit-test",
            explanation=123,  # type: ignore[arg-type]
        )


def test_health_assessment_rejects_non_string_explanation() -> None:
    with pytest.raises(ValidationError):
        HealthAssessment(
            component=make_component(),
            instance_id="instance-a",
            runtime_id="runtime-a",
            status=HealthStatus.HEALTHY,
            assessed_at=datetime.now(timezone.utc),
            source="unit-test",
            explanation=123,  # type: ignore[arg-type]
        )


def test_capability_assessment_rejects_overlong_source() -> None:
    with pytest.raises(ValidationError):
        make_capability_assessment(source="s" * 257)


def test_health_assessment_rejects_overlong_source() -> None:
    with pytest.raises(ValidationError):
        make_health_assessment(source="s" * 257)


def test_capability_assessment_rejects_overlong_explanation() -> None:
    with pytest.raises(ValidationError):
        make_capability_assessment(explanation="e" * 2049)


def test_health_assessment_rejects_overlong_explanation() -> None:
    with pytest.raises(ValidationError):
        make_health_assessment(explanation="e" * 2049)


def test_capability_assessment_is_immutable() -> None:
    assessment = make_capability_assessment()

    with pytest.raises(FrozenInstanceError):
        assessment.instance_id = "changed"  # type: ignore[misc]


def test_health_assessment_is_immutable() -> None:
    assessment = make_health_assessment()

    with pytest.raises(FrozenInstanceError):
        assessment.status = HealthStatus.UNHEALTHY  # type: ignore[misc]


def test_capability_assessment_keeps_component_identity() -> None:
    component = make_component(component_id="analysis-component")
    assessment = CapabilityAssessment(
        component=component,
        instance_id="instance-a",
        runtime_id="runtime-a",
        capability="inspect",
        availability=CapabilityAvailability.AVAILABLE,
        assessed_at=datetime.now(timezone.utc),
        source="unit-test",
    )

    assert assessment.component is component
    assert assessment.component_id == "analysis-component"


def test_health_assessment_keeps_component_identity() -> None:
    component = make_component(component_id="health-component")
    assessment = HealthAssessment(
        component=component,
        instance_id="instance-a",
        runtime_id="runtime-a",
        status=HealthStatus.DEGRADED,
        assessed_at=datetime.now(timezone.utc),
        source="unit-test",
    )

    assert assessment.component is component
    assert assessment.component_id == "health-component"
