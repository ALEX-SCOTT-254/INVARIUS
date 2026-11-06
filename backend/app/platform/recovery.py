"""Recovery contracts and lifecycle model for INVARIUS M2.10."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.app.core.errors import ValidationError
from backend.app.platform.failures import FailureRecord

if TYPE_CHECKING:
    from backend.app.platform.recovery_authorization import RecoveryAuthorization


RECOVERY_CONTRACT_VERSION = "v1"
_MAX_TEXT_LENGTH = 2_000


class RecoveryScope(StrEnum):
    """Explicit boundary targeted by a recovery attempt."""

    COMPONENT_INSTANCE = "component_instance"
    RUNTIME = "runtime"
    OPERATION = "operation"
    DEPENDENCY = "dependency"
    OTHER = "other"


class RecoveryStatus(StrEnum):
    """Lifecycle states for a single recovery attempt."""

    REQUESTED = "requested"
    AUTHORIZED = "authorized"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    UNRESOLVED = "unresolved"


_TERMINAL_STATUSES = frozenset(
    {
        RecoveryStatus.SUCCEEDED,
        RecoveryStatus.FAILED,
        RecoveryStatus.REJECTED,
        RecoveryStatus.CANCELLED,
        RecoveryStatus.UNRESOLVED,
    }
)

_AUTHORIZED_STATUSES = frozenset(
    {
        RecoveryStatus.AUTHORIZED,
        RecoveryStatus.RUNNING,
        RecoveryStatus.SUCCEEDED,
        RecoveryStatus.FAILED,
        RecoveryStatus.UNRESOLVED,
    }
)

_ALLOWED_TRANSITIONS: dict[RecoveryStatus, frozenset[RecoveryStatus]] = {
    RecoveryStatus.REQUESTED: frozenset(
        {
            RecoveryStatus.AUTHORIZED,
            RecoveryStatus.REJECTED,
            RecoveryStatus.CANCELLED,
        }
    ),
    RecoveryStatus.AUTHORIZED: frozenset(
        {
            RecoveryStatus.RUNNING,
            RecoveryStatus.CANCELLED,
        }
    ),
    RecoveryStatus.RUNNING: frozenset(
        {
            RecoveryStatus.SUCCEEDED,
            RecoveryStatus.FAILED,
            RecoveryStatus.CANCELLED,
            RecoveryStatus.UNRESOLVED,
        }
    ),
    RecoveryStatus.SUCCEEDED: frozenset(),
    RecoveryStatus.FAILED: frozenset(),
    RecoveryStatus.REJECTED: frozenset(),
    RecoveryStatus.CANCELLED: frozenset(),
    RecoveryStatus.UNRESOLVED: frozenset(),
}


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


def _normalize_timestamp(value: datetime, field_name: str) -> datetime:
    """Require an aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError(f"{field_name} must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{field_name} must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _validate_text(
    value: str,
    field_name: str,
    *,
    max_length: int = _MAX_TEXT_LENGTH,
) -> str:
    """Validate bounded, non-empty text."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    if not value.strip():
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(value) > max_length:
        raise ValidationError(f"{field_name} exceeds the maximum length.")

    return value


@dataclass(frozen=True)
class RecoveryAttempt:
    """Immutable description of one recovery attempt.

    This record does not itself authorize, execute, or verify recovery.
    Lifecycle updates create a new immutable record while preserving
    the attempt identity.
    """

    failure: FailureRecord
    scope: RecoveryScope
    target_id: str
    action_id: str
    authorization_context: str

    recovery_id: str = field(default_factory=lambda: uuid4().hex)
    contract_version: str = RECOVERY_CONTRACT_VERSION
    status: RecoveryStatus = RecoveryStatus.REQUESTED
    requested_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    verification_reference: str | None = None
    failure_reason: str | None = None
    max_attempts: int = 1
    attempt_number: int = 1
    max_duration_seconds: int = 300
    authorization_id: str | None = None

    def __post_init__(self) -> None:
        """Validate recovery attempt invariants."""
        if not isinstance(self.failure, FailureRecord):
            raise ValidationError("Recovery must reference a FailureRecord.")

        if not isinstance(self.scope, RecoveryScope):
            raise ValidationError("Recovery scope must be a RecoveryScope.")

        if not isinstance(self.status, RecoveryStatus):
            raise ValidationError("Recovery status must be a RecoveryStatus.")

        _validate_text(self.recovery_id, "Recovery ID", max_length=128)
        _validate_text(self.contract_version, "Contract version", max_length=64)
        _validate_text(self.target_id, "Recovery target ID", max_length=512)
        _validate_text(self.action_id, "Recovery action ID", max_length=512)
        _validate_text(
            self.authorization_context,
            "Authorization context",
            max_length=512,
        )

        if self.authorization_id is not None:
            _validate_text(
                self.authorization_id,
                "Authorization ID",
                max_length=128,
            )

        if self.status in _AUTHORIZED_STATUSES and self.authorization_id is None:
            raise ValidationError("Authorized recovery lifecycle requires an authorization ID.")

        object.__setattr__(
            self,
            "requested_at",
            _normalize_timestamp(self.requested_at, "Requested timestamp"),
        )

        if self.started_at is not None:
            object.__setattr__(
                self,
                "started_at",
                _normalize_timestamp(self.started_at, "Started timestamp"),
            )

        if self.completed_at is not None:
            object.__setattr__(
                self,
                "completed_at",
                _normalize_timestamp(self.completed_at, "Completed timestamp"),
            )

        if self.verification_reference is not None:
            _validate_text(
                self.verification_reference,
                "Verification reference",
                max_length=512,
            )

        if self.failure_reason is not None:
            _validate_text(
                self.failure_reason,
                "Failure reason",
                max_length=_MAX_TEXT_LENGTH,
            )

        if (
            not isinstance(self.max_attempts, int)
            or isinstance(self.max_attempts, bool)
            or self.max_attempts < 1
        ):
            raise ValidationError("max_attempts must be a positive integer.")

        if (
            not isinstance(self.attempt_number, int)
            or isinstance(self.attempt_number, bool)
            or not 1 <= self.attempt_number <= self.max_attempts
        ):
            raise ValidationError("attempt_number must be between 1 and max_attempts.")

        if (
            not isinstance(self.max_duration_seconds, int)
            or isinstance(self.max_duration_seconds, bool)
            or self.max_duration_seconds < 1
        ):
            raise ValidationError("max_duration_seconds must be a positive integer.")

        if self.status is RecoveryStatus.RUNNING and self.started_at is None:
            raise ValidationError("Running recovery requires started_at.")

        if self.status in _TERMINAL_STATUSES and self.completed_at is None:
            raise ValidationError("Terminal recovery requires completed_at.")

        if self.status is RecoveryStatus.SUCCEEDED:
            if self.verification_reference is None:
                raise ValidationError("Successful recovery requires verification evidence.")

        if self.status is RecoveryStatus.FAILED and self.failure_reason is None:
            raise ValidationError("Failed recovery requires a failure reason.")

    @property
    def is_terminal(self) -> bool:
        """Whether the attempt has reached a terminal lifecycle state."""
        return self.status in _TERMINAL_STATUSES

    def transition(
        self,
        new_status: RecoveryStatus,
        *,
        at: datetime | None = None,
        verification_reference: str | None = None,
        failure_reason: str | None = None,
        authorization: RecoveryAuthorization | None = None,
    ) -> RecoveryAttempt:
        """Return a new attempt record after a valid lifecycle transition."""
        if not isinstance(new_status, RecoveryStatus):
            raise ValidationError("New status must be a RecoveryStatus.")

        if new_status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValidationError(
                f"Invalid recovery transition: {self.status.value} -> {new_status.value}."
            )

        authorization_id = self.authorization_id

        if new_status is RecoveryStatus.AUTHORIZED:
            from backend.app.platform.recovery_authorization import (
                RecoveryAuthorization,
            )

            if not isinstance(authorization, RecoveryAuthorization):
                raise ValidationError("RecoveryAuthorization record is required.")

            if not authorization.permits(self):
                raise ValidationError(
                    "Recovery authorization is rejected or does not match this recovery attempt."
                )

            authorization_id = authorization.authorization_id

        timestamp = _normalize_timestamp(
            at if at is not None else _utc_now(),
            "Transition timestamp",
        )

        started_at = self.started_at
        completed_at = self.completed_at

        if new_status is RecoveryStatus.RUNNING:
            started_at = timestamp

        if new_status in _TERMINAL_STATUSES:
            completed_at = timestamp

        if new_status is RecoveryStatus.SUCCEEDED:
            if verification_reference is None:
                raise ValidationError("Successful recovery requires verification evidence.")

            _validate_text(
                verification_reference,
                "Verification reference",
                max_length=512,
            )

        if new_status is RecoveryStatus.FAILED:
            if failure_reason is None:
                raise ValidationError("Failed recovery requires a failure reason.")

            _validate_text(failure_reason, "Failure reason")

        return RecoveryAttempt(
            failure=self.failure,
            scope=self.scope,
            target_id=self.target_id,
            action_id=self.action_id,
            authorization_context=self.authorization_context,
            authorization_id=authorization_id,
            recovery_id=self.recovery_id,
            contract_version=self.contract_version,
            status=new_status,
            requested_at=self.requested_at,
            started_at=started_at,
            completed_at=completed_at,
            verification_reference=(
                verification_reference
                if verification_reference is not None
                else self.verification_reference
            ),
            failure_reason=(failure_reason if failure_reason is not None else self.failure_reason),
            max_attempts=self.max_attempts,
            attempt_number=self.attempt_number,
            max_duration_seconds=self.max_duration_seconds,
        )
