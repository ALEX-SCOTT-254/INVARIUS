"""Structured diagnostic events for INVARIUS observability."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from backend.app.core.errors import ValidationError
from backend.app.core.serialization import serialize

_MAX_FIELD_LENGTH = 256
_MAX_MESSAGE_LENGTH = 1024


class DiagnosticSeverity(StrEnum):
    """Severity levels supported by structured diagnostic events."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @property
    def logging_level(self) -> int:
        """Return the matching standard-library logging level."""
        return getattr(logging, self.value)


def _normalize_text(
    value: object,
    field_name: str,
    *,
    max_length: int = _MAX_FIELD_LENGTH,
) -> str:
    """Validate and normalize required bounded text."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(normalized) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")

    return normalized


def _normalize_optional_text(
    value: object,
    field_name: str,
) -> str | None:
    """Validate and normalize optional bounded text."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string or None.")

    normalized = value.strip()

    if not normalized:
        return None

    if len(normalized) > _MAX_FIELD_LENGTH:
        raise ValidationError(f"{field_name} cannot exceed {_MAX_FIELD_LENGTH} characters.")

    return normalized


def _normalize_timestamp(value: datetime) -> datetime:
    """Require a timezone-aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Diagnostic timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Diagnostic timestamp must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class DiagnosticEvent:
    """Immutable, structured record of an observable system event.

    The event records what was observed and its available context. It does
    not infer a root cause, establish operation success, or persist itself.
    Callers should not place secrets or sensitive payloads in diagnostic
    messages or identifiers.
    """

    event_type: str
    message: str
    source: str
    severity: DiagnosticSeverity = DiagnosticSeverity.INFO
    correlation_id: str | None = None
    operation_id: str | None = None
    parent_operation_id: str | None = None
    runtime_id: str | None = None
    component_id: str | None = None
    component_instance_id: str | None = None
    implementation_version: str | None = None
    error_code: str | None = None
    event_id: str = field(default_factory=lambda: uuid4().hex)
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Validate fields and normalize the timestamp."""
        for field_name in (
            "event_type",
            "source",
            "event_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_text(
                    getattr(self, field_name),
                    field_name.replace("_", " ").capitalize(),
                ),
            )

        object.__setattr__(
            self,
            "message",
            _normalize_text(
                self.message,
                "Diagnostic message",
                max_length=_MAX_MESSAGE_LENGTH,
            ),
        )

        if not isinstance(self.severity, DiagnosticSeverity):
            raise ValidationError("Diagnostic severity is invalid.")

        for field_name in (
            "correlation_id",
            "operation_id",
            "parent_operation_id",
            "runtime_id",
            "component_id",
            "component_instance_id",
            "implementation_version",
            "error_code",
        ):
            object.__setattr__(
                self,
                field_name,
                _normalize_optional_text(
                    getattr(self, field_name),
                    field_name.replace("_", " ").capitalize(),
                ),
            )

        object.__setattr__(
            self,
            "occurred_at",
            _normalize_timestamp(self.occurred_at),
        )

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible, deterministically ordered record."""
        result = serialize(self)

        if not isinstance(result, dict):
            raise ValidationError("Diagnostic event serialization did not produce an object.")

        return result

    def to_json(self) -> str:
        """Return the event as deterministic JSON suitable for log output."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )


def emit_diagnostic_event(
    event: DiagnosticEvent,
    *,
    logger: logging.Logger | None = None,
) -> None:
    """Emit a diagnostic event through Python's standard logging system.

    This function emits one JSON record as the log message. Application
    logging handlers, destinations, and global log-level configuration
    remain the responsibility of the application entry point.
    """
    if not isinstance(event, DiagnosticEvent):
        raise ValidationError("Diagnostic emission requires a DiagnosticEvent.")

    resolved_logger = logging.getLogger("invarius") if logger is None else logger

    if not isinstance(resolved_logger, logging.Logger):
        raise ValidationError("Diagnostic logger must be a logging.Logger.")

    resolved_logger.log(
        event.severity.logging_level,
        event.to_json(),
    )
