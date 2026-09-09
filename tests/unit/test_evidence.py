from datetime import datetime, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.evidence import Evidence, EvidenceState


def test_create_evidence() -> None:
    observed_at = datetime(
        2026,
        9,
        6,
        12,
        0,
        tzinfo=timezone.utc,
    )

    evidence = Evidence(
        state=EvidenceState.FACT,
        statement="The configuration file exists.",
        source="filesystem",
        confidence=1.0,
        observed_at=observed_at,
    )

    assert evidence.state == EvidenceState.FACT
    assert evidence.statement == "The configuration file exists."
    assert evidence.source == "filesystem"
    assert evidence.confidence == 1.0
    assert evidence.observed_at == observed_at


def test_now_creates_utc_timestamp() -> None:
    evidence = Evidence.now(
        state=EvidenceState.FACT,
        statement="Application started.",
        source="runtime",
        confidence=1.0,
    )

    assert evidence.observed_at.tzinfo is not None
    assert evidence.observed_at.utcoffset() == timezone.utc.utcoffset(evidence.observed_at)


def test_confidence_range() -> None:
    observed_at = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=-0.1,
            observed_at=observed_at,
        )

    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=1.1,
            observed_at=observed_at,
        )


def test_confidence_must_be_finite() -> None:
    observed_at = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=float("nan"),
            observed_at=observed_at,
        )

    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=float("inf"),
            observed_at=observed_at,
        )


def test_statement_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="   ",
            source="test",
            confidence=1.0,
            observed_at=datetime.now(timezone.utc),
        )


def test_source_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="   ",
            confidence=1.0,
            observed_at=datetime.now(timezone.utc),
        )


def test_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=1.0,
            observed_at=datetime(2026, 9, 6, 12, 0),
        )


def test_state_must_be_valid_evidence_state() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state="fact",  # type: ignore[arg-type]
            statement="Test",
            source="test",
            confidence=1.0,
            observed_at=datetime.now(timezone.utc),
        )


def test_statement_must_be_string() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement=123,  # type: ignore[arg-type]
            source="test",
            confidence=1.0,
            observed_at=datetime.now(timezone.utc),
        )


def test_source_must_be_string() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source=123,  # type: ignore[arg-type]
            confidence=1.0,
            observed_at=datetime.now(timezone.utc),
        )


def test_confidence_must_be_numeric() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence="high",  # type: ignore[arg-type]
            observed_at=datetime.now(timezone.utc),
        )


def test_boolean_confidence_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=True,  # type: ignore[arg-type]
            observed_at=datetime.now(timezone.utc),
        )


def test_timestamp_must_be_datetime() -> None:
    with pytest.raises(ValidationError):
        Evidence(
            state=EvidenceState.FACT,
            statement="Test",
            source="test",
            confidence=1.0,
            observed_at="2026-09-06T12:00:00Z",  # type: ignore[arg-type]
        )


def test_evidence_is_immutable() -> None:
    evidence = Evidence.now(
        state=EvidenceState.FACT,
        statement="Test",
        source="test",
        confidence=1.0,
    )

    with pytest.raises(AttributeError):
        evidence.statement = "Changed"  # type: ignore[misc]


def test_all_evidence_states() -> None:
    for state in EvidenceState:
        evidence = Evidence.now(
            state=state,
            statement=f"Evidence in {state} state.",
            source="test",
            confidence=0.5,
        )

        assert evidence.state == state
