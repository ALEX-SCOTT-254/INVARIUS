"""Tests for INVARIUS structured observability foundations."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.observability import (
    DiagnosticEvent,
    DiagnosticSeverity,
    emit_diagnostic_event,
)


def test_event_normalizes_text_and_timestamp() -> None:
    timestamp = datetime(2026, 1, 2, 12, 0, tzinfo=timezone(timedelta(hours=3)))

    event = DiagnosticEvent(
        event_type="  runtime.failure  ",
        message="  Runtime could not start.  ",
        source="  runtime  ",
        correlation_id="  correlation-123  ",
        occurred_at=timestamp,
    )

    assert event.event_type == "runtime.failure"
    assert event.message == "Runtime could not start."
    assert event.source == "runtime"
    assert event.correlation_id == "correlation-123"
    assert event.occurred_at == datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)


def test_event_defaults_to_info_severity_and_utc_timestamp() -> None:
    event = DiagnosticEvent(
        event_type="runtime.started",
        message="Runtime started.",
        source="runtime",
    )

    assert event.severity is DiagnosticSeverity.INFO
    assert event.occurred_at.tzinfo is timezone.utc
    assert event.event_id


def test_event_is_immutable() -> None:
    event = DiagnosticEvent(
        event_type="runtime.started",
        message="Runtime started.",
        source="runtime",
    )

    with pytest.raises(AttributeError):
        event.message = "Changed message"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("event_type", ""),
        ("event_type", "   "),
        ("message", ""),
        ("message", "   "),
        ("source", ""),
        ("event_id", ""),
    ],
)
def test_event_rejects_empty_required_text(
    field_name: str,
    value: str,
) -> None:
    fields = {
        "event_type": "runtime.started",
        "message": "Runtime started.",
        "source": "runtime",
        "event_id": "event-123",
    }
    fields[field_name] = value

    with pytest.raises(ValidationError):
        DiagnosticEvent(**fields)


def test_event_rejects_invalid_severity() -> None:
    with pytest.raises(ValidationError, match="severity"):
        DiagnosticEvent(
            event_type="runtime.failure",
            message="Runtime failed.",
            source="runtime",
            severity="ERROR",  # type: ignore[arg-type]
        )


def test_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        DiagnosticEvent(
            event_type="runtime.started",
            message="Runtime started.",
            source="runtime",
            occurred_at=datetime(2026, 1, 1),
        )


def test_event_rejects_overlong_message() -> None:
    with pytest.raises(ValidationError, match="1024 characters"):
        DiagnosticEvent(
            event_type="runtime.failure",
            message="x" * 1025,
            source="runtime",
        )


def test_event_rejects_overlong_optional_identifier() -> None:
    with pytest.raises(ValidationError, match="256 characters"):
        DiagnosticEvent(
            event_type="operation.failed",
            message="Operation failed.",
            source="execution",
            correlation_id="x" * 257,
        )


def test_event_serialization_is_deterministic() -> None:
    event = DiagnosticEvent(
        event_type="operation.failed",
        message="Operation failed.",
        source="execution",
        severity=DiagnosticSeverity.ERROR,
        correlation_id="corr-1",
        operation_id="op-1",
        runtime_id="runtime-1",
        component_id="component-1",
        component_instance_id="instance-1",
        implementation_version="1.0",
        error_code="VALIDATION_ERROR",
        event_id="event-1",
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    first = event.to_json()
    second = event.to_json()

    assert first == second
    assert json.loads(first) == event.to_dict()
    assert first == json.dumps(
        event.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def test_event_serialization_preserves_execution_context() -> None:
    event = DiagnosticEvent(
        event_type="operation.interrupted",
        message="Execution was interrupted.",
        source="execution",
        severity=DiagnosticSeverity.WARNING,
        correlation_id="corr-1",
        operation_id="op-1",
        parent_operation_id="parent-op-1",
        runtime_id="runtime-1",
        component_id="component-1",
        component_instance_id="instance-1",
        implementation_version="2.3",
    )

    record = event.to_dict()

    assert record["correlation_id"] == "corr-1"
    assert record["operation_id"] == "op-1"
    assert record["parent_operation_id"] == "parent-op-1"
    assert record["runtime_id"] == "runtime-1"
    assert record["component_id"] == "component-1"
    assert record["component_instance_id"] == "instance-1"
    assert record["implementation_version"] == "2.3"
    assert record["severity"] == "WARNING"


def test_event_allows_missing_parent_operation_id() -> None:
    event = DiagnosticEvent(
        event_type="operation.started",
        message="Operation started.",
        source="execution",
    )

    assert event.parent_operation_id is None
    assert event.to_dict()["parent_operation_id"] is None


@pytest.mark.parametrize(
    ("severity", "expected_level"),
    [
        (DiagnosticSeverity.DEBUG, logging.DEBUG),
        (DiagnosticSeverity.INFO, logging.INFO),
        (DiagnosticSeverity.WARNING, logging.WARNING),
        (DiagnosticSeverity.ERROR, logging.ERROR),
        (DiagnosticSeverity.CRITICAL, logging.CRITICAL),
    ],
)
def test_severity_maps_to_standard_logging_levels(
    severity: DiagnosticSeverity,
    expected_level: int,
) -> None:
    assert severity.logging_level == expected_level


def test_emit_writes_one_structured_json_log_record(
    caplog: pytest.LogCaptureFixture,
) -> None:
    logger = logging.getLogger("invarius.tests.observability")
    event = DiagnosticEvent(
        event_type="storage.failure",
        message="Storage operation failed.",
        source="storage",
        severity=DiagnosticSeverity.ERROR,
        correlation_id="corr-storage-1",
        error_code="STORAGE_ERROR",
        event_id="event-storage-1",
    )

    with caplog.at_level(logging.ERROR, logger=logger.name):
        emit_diagnostic_event(event, logger=logger)

    matching = [record for record in caplog.records if record.name == logger.name]

    assert len(matching) == 1
    assert matching[0].levelno == logging.ERROR

    decoded = json.loads(matching[0].getMessage())
    assert decoded["event_id"] == "event-storage-1"
    assert decoded["event_type"] == "storage.failure"
    assert decoded["severity"] == "ERROR"
    assert decoded["correlation_id"] == "corr-storage-1"
    assert decoded["error_code"] == "STORAGE_ERROR"


def test_emit_rejects_non_event_input() -> None:
    with pytest.raises(ValidationError, match="DiagnosticEvent"):
        emit_diagnostic_event("not an event")  # type: ignore[arg-type]


def test_emit_rejects_non_logger_input() -> None:
    event = DiagnosticEvent(
        event_type="runtime.started",
        message="Runtime started.",
        source="runtime",
    )

    with pytest.raises(ValidationError, match="logging.Logger"):
        emit_diagnostic_event(
            event,
            logger="not a logger",  # type: ignore[arg-type]
        )


def test_emit_propagates_serialization_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = DiagnosticEvent(
        event_type="runtime.started",
        message="Runtime started.",
        source="runtime",
    )

    def fail_serialization(self: DiagnosticEvent) -> str:
        raise RuntimeError("serialization failure")

    monkeypatch.setattr(DiagnosticEvent, "to_json", fail_serialization)

    with pytest.raises(RuntimeError, match="serialization failure"):
        emit_diagnostic_event(event, logger=logging.Logger("test.serialization"))


def test_emit_propagates_logging_handler_failure() -> None:
    class FailingHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            raise RuntimeError("logging handler failure")

    event = DiagnosticEvent(
        event_type="runtime.started",
        message="Runtime started.",
        source="runtime",
    )

    logger = logging.Logger("test.failing_handler")
    logger.setLevel(logging.DEBUG)

    handler = FailingHandler()
    logger.addHandler(handler)

    try:
        with pytest.raises(RuntimeError, match="logging handler failure"):
            emit_diagnostic_event(event, logger=logger)
    finally:
        logger.removeHandler(handler)
        handler.close()
