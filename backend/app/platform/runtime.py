"""M2.1 runtime lifecycle foundation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock
from uuid import uuid4

from backend.app.core.errors import ValidationError


class RuntimeState(StrEnum):
    """Lifecycle states for one INVARIUS runtime lifetime."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RuntimeTransition:
    """Immutable record of one runtime lifecycle transition."""

    revision: int
    from_state: RuntimeState | None
    to_state: RuntimeState
    occurred_at: datetime
    reason: str | None = None


_ALLOWED_TRANSITIONS: dict[
    RuntimeState,
    frozenset[RuntimeState],
] = {
    RuntimeState.CREATED: frozenset({RuntimeState.STARTING}),
    RuntimeState.STARTING: frozenset(
        {
            RuntimeState.RUNNING,
            RuntimeState.FAILED,
        }
    ),
    RuntimeState.RUNNING: frozenset(
        {
            RuntimeState.STOPPING,
            RuntimeState.FAILED,
        }
    ),
    RuntimeState.STOPPING: frozenset(
        {
            RuntimeState.STOPPED,
            RuntimeState.FAILED,
        }
    ),
    RuntimeState.STOPPED: frozenset(),
    RuntimeState.FAILED: frozenset(),
}


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def _validate_timestamp(value: datetime) -> datetime:
    """Validate a lifecycle timestamp."""

    if not isinstance(value, datetime):
        raise ValidationError("Runtime timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Runtime timestamps must include timezone information.")

    return value


def _validate_reason(reason: str | None) -> str | None:
    """Validate and normalize an optional transition reason."""

    if reason is None:
        return None

    if not isinstance(reason, str):
        raise ValidationError("Runtime transition reason must be a string.")

    normalized = reason.strip()

    if not normalized:
        raise ValidationError("Runtime transition reason cannot be empty when provided.")

    return normalized


class Runtime:
    """Authoritative lifecycle owner for one INVARIUS runtime lifetime."""

    __slots__ = (
        "_created_at",
        "_history",
        "_lock",
        "_revision",
        "_runtime_id",
        "_state",
    )

    def __init__(
        self,
        runtime_id: str | None = None,
        *,
        created_at: datetime | None = None,
    ) -> None:
        resolved_id = uuid4().hex if runtime_id is None else runtime_id

        if not isinstance(resolved_id, str):
            raise ValidationError("Runtime ID must be a string.")

        resolved_id = resolved_id.strip()

        if not resolved_id:
            raise ValidationError("Runtime ID cannot be empty.")

        timestamp = _utc_now() if created_at is None else _validate_timestamp(created_at)

        self._runtime_id = resolved_id
        self._created_at = timestamp
        self._state = RuntimeState.CREATED
        self._revision = 0
        self._history: tuple[RuntimeTransition, ...] = (
            RuntimeTransition(
                revision=0,
                from_state=None,
                to_state=RuntimeState.CREATED,
                occurred_at=timestamp,
            ),
        )
        self._lock = RLock()

    @property
    def runtime_id(self) -> str:
        """Return this runtime lifetime's immutable identity."""

        return self._runtime_id

    @property
    def created_at(self) -> datetime:
        """Return the runtime creation timestamp."""

        return self._created_at

    @property
    def state(self) -> RuntimeState:
        """Return the current authoritative lifecycle state."""

        with self._lock:
            return self._state

    @property
    def revision(self) -> int:
        """Return the current local lifecycle revision."""

        with self._lock:
            return self._revision

    @property
    def history(self) -> tuple[RuntimeTransition, ...]:
        """Return the immutable lifecycle transition history."""

        with self._lock:
            return self._history

    @property
    def is_terminal(self) -> bool:
        """Return whether the runtime is in a terminal lifecycle state."""

        with self._lock:
            return self._state in {
                RuntimeState.STOPPED,
                RuntimeState.FAILED,
            }

    def begin_start(
        self,
        *,
        at: datetime | None = None,
    ) -> RuntimeTransition:
        """Move the runtime from CREATED to STARTING."""

        return self._transition(
            RuntimeState.STARTING,
            at=at,
        )

    def mark_running(
        self,
        *,
        at: datetime | None = None,
    ) -> RuntimeTransition:
        """Move the runtime from STARTING to RUNNING."""

        return self._transition(
            RuntimeState.RUNNING,
            at=at,
        )

    def begin_stop(
        self,
        *,
        at: datetime | None = None,
    ) -> RuntimeTransition:
        """Move the runtime from RUNNING to STOPPING."""

        return self._transition(
            RuntimeState.STOPPING,
            at=at,
        )

    def mark_stopped(
        self,
        *,
        at: datetime | None = None,
    ) -> RuntimeTransition:
        """Move the runtime from STOPPING to STOPPED."""

        return self._transition(
            RuntimeState.STOPPED,
            at=at,
        )

    def mark_failed(
        self,
        *,
        at: datetime | None = None,
        reason: str | None = None,
    ) -> RuntimeTransition:
        """Move the runtime into the terminal FAILED state."""

        return self._transition(
            RuntimeState.FAILED,
            at=at,
            reason=reason,
        )

    def _transition(
        self,
        target: RuntimeState,
        *,
        at: datetime | None,
        reason: str | None = None,
    ) -> RuntimeTransition:
        """Perform one validated authoritative lifecycle transition."""

        timestamp = _utc_now() if at is None else _validate_timestamp(at)
        normalized_reason = _validate_reason(reason)

        with self._lock:
            allowed = _ALLOWED_TRANSITIONS[self._state]

            if target not in allowed:
                raise ValidationError(
                    f"Invalid runtime lifecycle transition: {self._state.value} -> {target.value}."
                )

            transition = RuntimeTransition(
                revision=self._revision + 1,
                from_state=self._state,
                to_state=target,
                occurred_at=timestamp,
                reason=normalized_reason,
            )

            self._state = target
            self._revision = transition.revision
            self._history = (*self._history, transition)

            return transition
