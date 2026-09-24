"""Tests for the INVARIUS investigation contract."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.evidence import Evidence, EvidenceState
from backend.app.core.investigation import (
    INVESTIGATION_CONTRACT_VERSION,
    Investigation,
    InvestigationStatus,
    UnresolvedItem,
)
from backend.app.core.serialization import serialize


def make_evidence() -> Evidence:
    """Create valid evidence for investigation tests."""

    return Evidence(
        state=EvidenceState.FACT,
        statement="The service returned an error response.",
        source="test",
        confidence=1.0,
        observed_at=datetime.now(timezone.utc),
    )


def make_unresolved() -> UnresolvedItem:
    """Create a valid unresolved investigation item."""

    return UnresolvedItem(
        question="Why did the dependency fail?",
        reason="The dependency response was unavailable.",
        next_step="Inspect dependency telemetry.",
    )


def make_investigation(
    **overrides: object,
) -> Investigation:
    """Create a valid investigation with optional field overrides."""

    values: dict[str, object] = {
        "investigation_id": "INV-001",
        "subject": "Service failure",
        "scope": "API request path",
        "status": InvestigationStatus.ACTIVE,
        "summary": "The request path was investigated.",
        "evidence": (make_evidence(),),
        "unresolved": (make_unresolved(),),
        "next_steps": ("Inspect dependency telemetry.",),
    }
    values.update(overrides)

    return Investigation(**values)


def test_valid_investigation_can_be_created() -> None:
    """A valid investigation should be constructible."""

    investigation = make_investigation()

    assert investigation.investigation_id == "INV-001"
    assert investigation.subject == "Service failure"
    assert investigation.scope == "API request path"
    assert investigation.status is InvestigationStatus.ACTIVE
    assert investigation.summary == "The request path was investigated."


def test_investigation_is_immutable() -> None:
    """Investigation fields should not be mutable after creation."""

    investigation = make_investigation()

    with pytest.raises(FrozenInstanceError):
        investigation.subject = "Changed"


def test_default_contract_version_is_v1() -> None:
    """The investigation contract should use the locked v1 contract."""

    investigation = make_investigation()

    assert investigation.investigation_contract_version == (INVESTIGATION_CONTRACT_VERSION)
    assert INVESTIGATION_CONTRACT_VERSION == "v1"


@pytest.mark.parametrize(
    "status",
    InvestigationStatus,
)
def test_all_investigation_statuses_are_valid(
    status: InvestigationStatus,
) -> None:
    """Every defined lifecycle status should be accepted."""

    investigation = make_investigation(status=status)

    assert investigation.status is status


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("investigation_id", "", "Investigation ID cannot be empty."),
        ("subject", "", "Investigation subject cannot be empty."),
        ("scope", "", "Investigation scope cannot be empty."),
        ("summary", "", "Investigation summary cannot be empty."),
    ],
)
def test_required_strings_cannot_be_empty(
    field: str,
    value: str,
    message: str,
) -> None:
    """Required investigation fields should reject empty strings."""

    with pytest.raises(ValidationError, match=message):
        make_investigation(**{field: value})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("investigation_id", 123, "Investigation ID must be a string."),
        ("subject", 123, "Investigation subject must be a string."),
        ("scope", 123, "Investigation scope must be a string."),
        ("summary", 123, "Investigation summary must be a string."),
    ],
)
def test_required_strings_must_be_strings(
    field: str,
    value: object,
    message: str,
) -> None:
    """Required investigation fields should reject non-string values."""

    with pytest.raises(ValidationError, match=message):
        make_investigation(**{field: value})


def test_invalid_status_is_rejected() -> None:
    """Investigation status must use the defined status type."""

    with pytest.raises(
        ValidationError,
        match="Investigation status must be a valid InvestigationStatus.",
    ):
        make_investigation(status="active")


def test_evidence_must_be_a_tuple() -> None:
    """Investigation evidence must use the immutable tuple representation."""

    with pytest.raises(
        ValidationError,
        match="Investigation evidence must be a tuple.",
    ):
        make_investigation(evidence=[make_evidence()])


def test_evidence_must_contain_only_evidence_objects() -> None:
    """Investigation evidence must contain only Evidence objects."""

    with pytest.raises(
        ValidationError,
        match="Investigation evidence must contain only Evidence objects.",
    ):
        make_investigation(evidence=("not evidence",))


def test_unresolved_items_must_be_a_tuple() -> None:
    """Unresolved items must use the immutable tuple representation."""

    with pytest.raises(
        ValidationError,
        match="Investigation unresolved items must be a tuple.",
    ):
        make_investigation(unresolved=[make_unresolved()])


def test_unresolved_items_must_contain_only_valid_items() -> None:
    """Unresolved items must contain only UnresolvedItem objects."""

    with pytest.raises(
        ValidationError,
        match="Investigation unresolved items must contain only UnresolvedItem objects.",
    ):
        make_investigation(unresolved=("not unresolved",))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "question",
            "",
            "Unresolved question cannot be empty.",
        ),
        (
            "reason",
            "",
            "Unresolved reason cannot be empty.",
        ),
        (
            "next_step",
            "",
            "Unresolved next step cannot be empty.",
        ),
    ],
)
def test_unresolved_item_fields_cannot_be_empty(
    field: str,
    value: str,
    message: str,
) -> None:
    """Unresolved-item fields should reject empty strings."""

    with pytest.raises(ValidationError, match=message):
        UnresolvedItem(
            question=value if field == "question" else "Question",
            reason=value if field == "reason" else "Reason",
            next_step=value if field == "next_step" else "Next step",
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "question",
            123,
            "Unresolved question must be a string.",
        ),
        (
            "reason",
            123,
            "Unresolved reason must be a string.",
        ),
        (
            "next_step",
            123,
            "Unresolved next step must be a string.",
        ),
    ],
)
def test_unresolved_item_fields_must_be_strings(
    field: str,
    value: object,
    message: str,
) -> None:
    """Unresolved-item fields should reject non-string values."""

    values: dict[str, object] = {
        "question": "Question",
        "reason": "Reason",
        "next_step": "Next step",
    }
    values[field] = value

    with pytest.raises(ValidationError, match=message):
        UnresolvedItem(**values)


def test_next_steps_must_be_a_tuple() -> None:
    """Next steps must use the immutable tuple representation."""

    with pytest.raises(
        ValidationError,
        match="Investigation next steps must be a tuple.",
    ):
        make_investigation(next_steps=["Inspect telemetry."])


def test_next_steps_must_contain_only_strings() -> None:
    """Next steps must contain only strings."""

    with pytest.raises(
        ValidationError,
        match="Investigation next steps must contain only strings.",
    ):
        make_investigation(next_steps=("Inspect telemetry.", 123))


def test_contract_version_must_be_a_string() -> None:
    """Investigation contract version must be a string."""

    with pytest.raises(
        ValidationError,
        match="Investigation contract version must be a string.",
    ):
        make_investigation(investigation_contract_version=123)


def test_contract_version_cannot_be_empty() -> None:
    """Investigation contract version cannot be empty."""

    with pytest.raises(
        ValidationError,
        match="Investigation contract version cannot be empty.",
    ):
        make_investigation(investigation_contract_version="")


def test_completed_investigation_may_contain_unresolved_items() -> None:
    """Completion does not imply that every question was established."""

    investigation = make_investigation(
        status=InvestigationStatus.COMPLETED,
    )

    assert investigation.status is InvestigationStatus.COMPLETED
    assert investigation.unresolved == (make_unresolved(),)


def test_evidence_is_separate_from_unresolved_conclusions() -> None:
    """Evidence and unresolved conclusions remain distinct contract fields."""

    evidence = make_evidence()
    unresolved = make_unresolved()

    investigation = make_investigation(
        evidence=(evidence,),
        unresolved=(unresolved,),
    )

    assert investigation.evidence == (evidence,)
    assert investigation.unresolved == (unresolved,)
    assert investigation.evidence[0] is not unresolved


def test_investigation_does_not_imply_causality_from_evidence() -> None:
    """The contract stores evidence without declaring it to be causal."""

    investigation = make_investigation(
        summary="The service failure was observed.",
        evidence=(make_evidence(),),
    )

    assert investigation.summary == "The service failure was observed."
    assert investigation.evidence
    assert not hasattr(investigation, "root_cause")
    assert not hasattr(investigation, "causal_graph")


def test_investigation_serializes_with_existing_serializer() -> None:
    """Investigation should be compatible with the existing serializer."""

    investigation = make_investigation()

    serialized = serialize(investigation)

    assert serialized["investigation_id"] == "INV-001"
    assert serialized["subject"] == "Service failure"
    assert serialized["scope"] == "API request path"
    assert serialized["status"] == "active"
    assert serialized["investigation_contract_version"] == "v1"
    assert len(serialized["evidence"]) == 1
    assert len(serialized["unresolved"]) == 1
    assert serialized["next_steps"] == ["Inspect dependency telemetry."]
