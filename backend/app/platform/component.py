"""M2.2 component model foundation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock
from uuid import uuid4

from backend.app.core.errors import ValidationError


class ComponentInstanceState(StrEnum):
    """Lifecycle states for one concrete component instance."""

    CREATED = "created"
    STARTING = "starting"
    READY = "ready"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Component:
    """Immutable logical definition of an INVARIUS platform component."""

    component_id: str
    name: str
    contract_version: str
    implementation_version: str
    capabilities: frozenset[str]
    declared_dependencies: frozenset[str]

    def __post_init__(self) -> None:
        component_id = self._normalize_text(self.component_id, "Component ID")
        name = self._normalize_text(self.name, "Component name")
        contract_version = self._normalize_text(
            self.contract_version,
            "Contract version",
        )
        implementation_version = self._normalize_text(
            self.implementation_version,
            "Implementation version",
        )
        capabilities = self._normalize_collection(
            self.capabilities,
            "Capabilities",
        )
        dependencies = self._normalize_collection(
            self.declared_dependencies,
            "Declared dependencies",
        )

        object.__setattr__(self, "component_id", component_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "contract_version", contract_version)
        object.__setattr__(
            self,
            "implementation_version",
            implementation_version,
        )
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(
            self,
            "declared_dependencies",
            dependencies,
        )

    @staticmethod
    def _normalize_text(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise ValidationError(f"{field_name} must be a string.")

        normalized = value.strip()

        if not normalized:
            raise ValidationError(f"{field_name} cannot be empty.")

        return normalized

    @classmethod
    def _normalize_collection(
        cls,
        value: frozenset[str],
        field_name: str,
    ) -> frozenset[str]:
        if not isinstance(value, (set, frozenset)):
            raise ValidationError(f"{field_name} must be a set of strings.")

        normalized = frozenset(
            cls._normalize_text(
                item,
                field_name.removesuffix("s"),
            )
            for item in value
        )

        return normalized


@dataclass(frozen=True, slots=True)
class ComponentInstanceTransition:
    """Immutable record of one component instance transition."""

    revision: int
    from_state: ComponentInstanceState | None
    to_state: ComponentInstanceState
    occurred_at: datetime
    reason: str | None = None


_ALLOWED_TRANSITIONS: dict[
    ComponentInstanceState,
    frozenset[ComponentInstanceState],
] = {
    ComponentInstanceState.CREATED: frozenset({ComponentInstanceState.STARTING}),
    ComponentInstanceState.STARTING: frozenset(
        {
            ComponentInstanceState.READY,
            ComponentInstanceState.FAILED,
        }
    ),
    ComponentInstanceState.READY: frozenset(
        {
            ComponentInstanceState.STOPPING,
            ComponentInstanceState.FAILED,
        }
    ),
    ComponentInstanceState.STOPPING: frozenset(
        {
            ComponentInstanceState.STOPPED,
            ComponentInstanceState.FAILED,
        }
    ),
    ComponentInstanceState.STOPPED: frozenset(),
    ComponentInstanceState.FAILED: frozenset(),
}


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def _validate_timestamp(value: datetime) -> datetime:
    """Validate a lifecycle timestamp."""

    if not isinstance(value, datetime):
        raise ValidationError("Component timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Component timestamps must include timezone information.")

    return value


def _validate_reason(reason: str | None) -> str | None:
    """Validate and normalize an optional transition reason."""

    if reason is None:
        return None

    if not isinstance(reason, str):
        raise ValidationError("Component transition reason must be a string.")

    normalized = reason.strip()

    if not normalized:
        raise ValidationError("Component transition reason cannot be empty when provided.")

    return normalized


class ComponentInstance:
    """Authoritative lifecycle owner for one concrete component instance."""

    __slots__ = (
        "_component_id",
        "_created_at",
        "_history",
        "_implementation_version",
        "_lock",
        "_revision",
        "_instance_id",
        "_runtime_id",
        "_state",
    )

    def __init__(
        self,
        component: Component,
        runtime_id: str,
        *,
        instance_id: str | None = None,
        created_at: datetime | None = None,
    ) -> None:
        if not isinstance(component, Component):
            raise ValidationError("Component instance requires a Component.")

        if not isinstance(runtime_id, str):
            raise ValidationError("Runtime ID must be a string.")

        normalized_runtime_id = runtime_id.strip()

        if not normalized_runtime_id:
            raise ValidationError("Runtime ID cannot be empty.")

        resolved_instance_id = uuid4().hex if instance_id is None else instance_id

        if not isinstance(resolved_instance_id, str):
            raise ValidationError("Component instance ID must be a string.")

        resolved_instance_id = resolved_instance_id.strip()

        if not resolved_instance_id:
            raise ValidationError("Component instance ID cannot be empty.")

        timestamp = _utc_now() if created_at is None else _validate_timestamp(created_at)

        self._component_id = component.component_id
        self._runtime_id = normalized_runtime_id
        self._instance_id = resolved_instance_id
        self._implementation_version = component.implementation_version
        self._created_at = timestamp
        self._state = ComponentInstanceState.CREATED
        self._revision = 0
        self._history: tuple[ComponentInstanceTransition, ...] = (
            ComponentInstanceTransition(
                revision=0,
                from_state=None,
                to_state=ComponentInstanceState.CREATED,
                occurred_at=timestamp,
            ),
        )
        self._lock = RLock()

    @property
    def instance_id(self) -> str:
        """Return the immutable instance identity."""

        return self._instance_id

    @property
    def component_id(self) -> str:
        """Return the logical component identity."""

        return self._component_id

    @property
    def runtime_id(self) -> str:
        """Return the owning runtime identity."""

        return self._runtime_id

    @property
    def implementation_version(self) -> str:
        """Return the implementation version used by this instance."""

        return self._implementation_version

    @property
    def created_at(self) -> datetime:
        """Return the instance creation timestamp."""

        return self._created_at

    @property
    def state(self) -> ComponentInstanceState:
        """Return the current authoritative lifecycle state."""

        with self._lock:
            return self._state

    @property
    def revision(self) -> int:
        """Return the current local lifecycle revision."""

        with self._lock:
            return self._revision

    @property
    def history(self) -> tuple[ComponentInstanceTransition, ...]:
        """Return the immutable lifecycle history."""

        with self._lock:
            return self._history

    @property
    def is_terminal(self) -> bool:
        """Return whether the instance has reached a terminal state."""

        with self._lock:
            return self._state in {
                ComponentInstanceState.STOPPED,
                ComponentInstanceState.FAILED,
            }

    def begin_start(
        self,
        *,
        at: datetime | None = None,
    ) -> ComponentInstanceTransition:
        """Move the instance from CREATED to STARTING."""

        return self._transition(
            ComponentInstanceState.STARTING,
            at=at,
        )

    def mark_ready(
        self,
        *,
        at: datetime | None = None,
    ) -> ComponentInstanceTransition:
        """Move the instance from STARTING to READY."""

        return self._transition(
            ComponentInstanceState.READY,
            at=at,
        )

    def begin_stop(
        self,
        *,
        at: datetime | None = None,
    ) -> ComponentInstanceTransition:
        """Move the instance from READY to STOPPING."""

        return self._transition(
            ComponentInstanceState.STOPPING,
            at=at,
        )

    def mark_stopped(
        self,
        *,
        at: datetime | None = None,
    ) -> ComponentInstanceTransition:
        """Move the instance from STOPPING to STOPPED."""

        return self._transition(
            ComponentInstanceState.STOPPED,
            at=at,
        )

    def mark_failed(
        self,
        *,
        at: datetime | None = None,
        reason: str | None = None,
    ) -> ComponentInstanceTransition:
        """Move the instance into the terminal FAILED state."""

        return self._transition(
            ComponentInstanceState.FAILED,
            at=at,
            reason=reason,
        )

    def _transition(
        self,
        target: ComponentInstanceState,
        *,
        at: datetime | None,
        reason: str | None = None,
    ) -> ComponentInstanceTransition:
        """Perform one validated lifecycle transition."""

        timestamp = _utc_now() if at is None else _validate_timestamp(at)
        normalized_reason = _validate_reason(reason)

        with self._lock:
            allowed = _ALLOWED_TRANSITIONS[self._state]

            if target not in allowed:
                raise ValidationError(
                    "Invalid component instance lifecycle transition: "
                    f"{self._state.value} -> {target.value}."
                )

            transition = ComponentInstanceTransition(
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
