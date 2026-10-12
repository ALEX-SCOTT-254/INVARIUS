"""M2.5 lightweight execution and operation-context integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock

from backend.app.core.errors import ValidationError
from backend.app.core.operation import Operation
from backend.app.core.result import Result
from backend.app.platform.component import (
    ComponentInstance,
    ComponentInstanceState,
)
from backend.app.platform.runtime import Runtime, RuntimeState

_MAX_TEXT_LENGTH = 256


class OperationExecutionState(StrEnum):
    """Lifecycle states for one platform execution attempt."""

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


_ALLOWED_TRANSITIONS: dict[
    OperationExecutionState,
    frozenset[OperationExecutionState],
] = {
    OperationExecutionState.CREATED: frozenset(
        {
            OperationExecutionState.STARTING,
            OperationExecutionState.CANCEL_REQUESTED,
            OperationExecutionState.COMPLETED,
            OperationExecutionState.INTERRUPTED,
        }
    ),
    OperationExecutionState.STARTING: frozenset(
        {
            OperationExecutionState.RUNNING,
            OperationExecutionState.CANCEL_REQUESTED,
            OperationExecutionState.COMPLETED,
            OperationExecutionState.INTERRUPTED,
        }
    ),
    OperationExecutionState.RUNNING: frozenset(
        {
            OperationExecutionState.CANCEL_REQUESTED,
            OperationExecutionState.COMPLETED,
            OperationExecutionState.INTERRUPTED,
        }
    ),
    OperationExecutionState.CANCEL_REQUESTED: frozenset(
        {
            OperationExecutionState.COMPLETED,
            OperationExecutionState.CANCELLED,
            OperationExecutionState.INTERRUPTED,
        }
    ),
    OperationExecutionState.COMPLETED: frozenset(),
    OperationExecutionState.CANCELLED: frozenset(),
    OperationExecutionState.INTERRUPTED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class OperationExecutionContext:
    """Bounded context for tracing an existing M1.5 operation."""

    correlation_id: str
    source: str
    parent_operation_id: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize context fields."""
        object.__setattr__(
            self,
            "correlation_id",
            _normalize_text(self.correlation_id, "Correlation ID"),
        )
        object.__setattr__(
            self,
            "source",
            _normalize_text(self.source, "Context source"),
        )

        if self.parent_operation_id is not None:
            object.__setattr__(
                self,
                "parent_operation_id",
                _normalize_text(
                    self.parent_operation_id,
                    "Parent operation ID",
                ),
            )


@dataclass(frozen=True, slots=True)
class ExecutionTransition:
    """Immutable record of one valid execution lifecycle transition."""

    operation_id: str
    revision: int
    from_state: OperationExecutionState
    to_state: OperationExecutionState
    occurred_at: datetime
    reason: str | None = None

    def __post_init__(self) -> None:
        """Validate transition identity, legality, ordering, and timestamp."""
        object.__setattr__(
            self,
            "operation_id",
            _normalize_text(self.operation_id, "Operation ID"),
        )

        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ValidationError("Execution revision must be a positive integer.")

        if not isinstance(self.from_state, OperationExecutionState):
            raise ValidationError("Execution source state is invalid.")

        if not isinstance(self.to_state, OperationExecutionState):
            raise ValidationError("Execution target state is invalid.")

        if self.from_state == self.to_state:
            raise ValidationError("Execution transition states must differ.")

        if self.to_state not in _ALLOWED_TRANSITIONS[self.from_state]:
            raise ValidationError(
                f"Invalid execution transition: {self.from_state.value} -> {self.to_state.value}."
            )

        object.__setattr__(
            self,
            "occurred_at",
            _normalize_timestamp(self.occurred_at),
        )
        object.__setattr__(
            self,
            "reason",
            _normalize_optional_text(self.reason, "Transition reason"),
        )


def _normalize_text(value: object, field_name: str) -> str:
    """Require bounded, non-empty text."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(normalized) > _MAX_TEXT_LENGTH:
        raise ValidationError(f"{field_name} cannot exceed {_MAX_TEXT_LENGTH} characters.")

    return normalized


def _normalize_optional_text(
    value: object,
    field_name: str,
) -> str | None:
    """Normalize optional descriptive text."""
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string or None.")

    normalized = value.strip()

    if not normalized:
        return None

    if len(normalized) > _MAX_TEXT_LENGTH:
        raise ValidationError(f"{field_name} cannot exceed {_MAX_TEXT_LENGTH} characters.")

    return normalized


def _normalize_timestamp(value: datetime) -> datetime:
    """Require a timezone-aware datetime and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Timestamp must be timezone-aware.")

    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc)


class OperationExecution:
    """Connect one existing M1.5 operation to platform execution context.

    M1.5 Operation remains the authoritative operation contract.
    M1.5 Result remains the authoritative outcome contract.

    This class records execution identity and lifecycle. It does not run
    component code, schedule work, retry operations, persist records,
    perform recovery, or diagnose causes.

    Execution state and result status are separate. COMPLETED does not
    imply a SUCCESS result. An interrupted execution does not automatically
    receive an invented result. A retry requires a separate Operation ID.
    """

    def __init__(
        self,
        *,
        operation: Operation,
        runtime: Runtime,
        component_instance: ComponentInstance,
        context: OperationExecutionContext,
    ) -> None:
        """Bind an existing operation to its platform execution context."""
        if not isinstance(operation, Operation):
            raise ValidationError("Execution requires an existing M1.5 Operation.")

        if not isinstance(runtime, Runtime):
            raise ValidationError("Execution requires a platform Runtime.")

        if not isinstance(component_instance, ComponentInstance):
            raise ValidationError("Execution requires a ComponentInstance.")

        if not isinstance(context, OperationExecutionContext):
            raise ValidationError("Execution context has an invalid type.")

        if component_instance.runtime_id != runtime.runtime_id:
            raise ValidationError("Component instance belongs to a different runtime.")

        # Reuse the original operation contract and identity.
        self._operation = operation
        self._runtime = runtime
        self._component_instance = component_instance
        self._context = context

        # Capture the identities associated with this execution attempt.
        self._runtime_id = runtime.runtime_id
        self._component_id = component_instance.component_id
        self._component_instance_id = component_instance.instance_id
        self._implementation_version = component_instance.implementation_version

        self._state = OperationExecutionState.CREATED
        self._revision = 0
        self._history: list[ExecutionTransition] = []
        self._result: Result | None = None
        self._lock = RLock()

    @property
    def operation(self) -> Operation:
        """Return the original M1.5 operation contract."""
        return self._operation

    @property
    def operation_id(self) -> str:
        """Return the operation ID defined by M1.5."""
        return self._operation.operation_id

    @property
    def runtime_id(self) -> str:
        """Return the runtime identity captured for this execution."""
        return self._runtime_id

    @property
    def component_id(self) -> str:
        """Return the logical component identity."""
        return self._component_id

    @property
    def component_instance_id(self) -> str:
        """Return the concrete component-instance identity."""
        return self._component_instance_id

    @property
    def implementation_version(self) -> str:
        """Return the implementation version captured for this attempt."""
        return self._implementation_version

    @property
    def context(self) -> OperationExecutionContext:
        """Return the immutable execution context."""
        return self._context

    @property
    def state(self) -> OperationExecutionState:
        """Return the current execution lifecycle state."""
        with self._lock:
            return self._state

    @property
    def revision(self) -> int:
        """Return the execution lifecycle revision."""
        with self._lock:
            return self._revision

    @property
    def history(self) -> tuple[ExecutionTransition, ...]:
        """Return an immutable snapshot of lifecycle transitions."""
        with self._lock:
            return tuple(self._history)

    @property
    def result(self) -> Result | None:
        """Return the existing M1.5 Result, if one was recorded."""
        with self._lock:
            return self._result

    def begin_start(
        self,
        reason: str | None = None,
    ) -> ExecutionTransition:
        """Record startup when the runtime and component are ready."""
        with self._lock:
            self._require_runtime_running()
            self._require_component_ready()
            return self._transition(
                OperationExecutionState.STARTING,
                reason,
            )

    def mark_running(
        self,
        reason: str | None = None,
    ) -> ExecutionTransition:
        """Record the operation's transition into its running state."""
        with self._lock:
            self._require_runtime_running()
            self._require_component_ready()
            return self._transition(
                OperationExecutionState.RUNNING,
                reason,
            )

    def request_cancel(
        self,
        reason: str | None = None,
    ) -> ExecutionTransition:
        """Record a cancellation request, not confirmed cancellation."""
        with self._lock:
            return self._transition(
                OperationExecutionState.CANCEL_REQUESTED,
                reason,
            )

    def mark_completed(
        self,
        result: Result,
        reason: str | None = None,
    ) -> ExecutionTransition:
        """Record completion and attach the authoritative M1.5 Result."""
        if not isinstance(result, Result):
            raise ValidationError("Completion requires an existing M1.5 Result.")

        with self._lock:
            transition = self._transition(
                OperationExecutionState.COMPLETED,
                reason,
            )
            self._result = result
            return transition

    def mark_cancelled(
        self,
        reason: str | None = None,
    ) -> ExecutionTransition:
        """Record confirmed cancellation after a cancellation request."""
        with self._lock:
            return self._transition(
                OperationExecutionState.CANCELLED,
                reason,
            )

    def mark_interrupted(
        self,
        reason: str | None = None,
    ) -> ExecutionTransition:
        """Record interruption without inventing an operation result."""
        with self._lock:
            return self._transition(
                OperationExecutionState.INTERRUPTED,
                reason,
            )

    def _require_runtime_running(self) -> None:
        """Require the associated runtime to be running."""
        if self._runtime.state is not RuntimeState.RUNNING:
            raise ValidationError("Execution requires a running runtime.")

    def _require_component_ready(self) -> None:
        """Require the associated component instance to be ready."""
        if self._component_instance.state is not ComponentInstanceState.READY:
            raise ValidationError("Execution requires a ready component instance.")

    def _transition(
        self,
        target: OperationExecutionState,
        reason: str | None,
    ) -> ExecutionTransition:
        """Validate and record one transition under the owner lock."""
        if not isinstance(target, OperationExecutionState):
            raise ValidationError("Target execution state is invalid.")

        normalized_reason = _normalize_optional_text(
            reason,
            "Transition reason",
        )

        if target not in _ALLOWED_TRANSITIONS[self._state]:
            raise ValidationError(
                f"Invalid execution transition: {self._state.value} -> {target.value}."
            )

        transition = ExecutionTransition(
            operation_id=self.operation_id,
            revision=self._revision + 1,
            from_state=self._state,
            to_state=target,
            occurred_at=_utc_now(),
            reason=normalized_reason,
        )

        self._history.append(transition)
        self._state = target
        self._revision = transition.revision
        return transition
