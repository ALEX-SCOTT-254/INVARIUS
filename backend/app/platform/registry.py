"""M2.3 component registry foundation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock

from backend.app.core.errors import ValidationError
from backend.app.platform.component import Component


class RegistryEventKind(StrEnum):
    """Membership changes recorded by the registry."""

    REGISTERED = "registered"
    UNREGISTERED = "unregistered"


@dataclass(frozen=True, slots=True)
class RegistryEvent:
    """Immutable record of a component registry membership change."""

    revision: int
    kind: RegistryEventKind
    component: Component
    occurred_at: datetime

    def __post_init__(self) -> None:
        if (
            isinstance(self.revision, bool)
            or not isinstance(self.revision, int)
            or self.revision < 1
        ):
            raise ValidationError("Registry event revision must be a positive integer.")

        if not isinstance(self.kind, RegistryEventKind):
            raise ValidationError("Registry event kind is invalid.")

        if not isinstance(self.component, Component):
            raise ValidationError("Registry event component must be a Component.")

        occurred_at = self.occurred_at
        if (
            not isinstance(occurred_at, datetime)
            or occurred_at.tzinfo is None
            or occurred_at.utcoffset() is None
        ):
            raise ValidationError("Registry event timestamp must be timezone-aware.")

        object.__setattr__(
            self,
            "occurred_at",
            occurred_at.astimezone(timezone.utc),
        )

    @property
    def component_id(self) -> str:
        """Return the logical identity of the affected component."""
        return self.component.component_id


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _normalize_component_id(component_id: str) -> str:
    """Validate and normalize a component identifier."""
    if not isinstance(component_id, str):
        raise ValidationError("Component ID must be a string.")

    normalized = component_id.strip()
    if not normalized:
        raise ValidationError("Component ID must not be empty.")

    return normalized


class ComponentRegistry:
    """Thread-safe registry of logical component definitions.

    The registry owns current membership and its in-memory membership
    history. It does not own component-instance lifecycles, runtime health,
    dependency resolution, execution, or durable persistence.

    Registering an identical active definition is idempotent and returns
    False. Registering a different definition under an active ID raises
    ValidationError.

    Deregistration preserves historical events and the last registered
    definition. Re-registering a changed historical definition requires
    a changed contract version or implementation version.
    """

    __slots__ = (
        "_components",
        "_history",
        "_latest_by_id",
        "_lock",
        "_revision",
    )

    def __init__(self) -> None:
        self._components: dict[str, Component] = {}
        self._latest_by_id: dict[str, Component] = {}
        self._history: list[RegistryEvent] = []
        self._revision = 0
        self._lock = RLock()

    @property
    def revision(self) -> int:
        """Return the current membership revision."""
        with self._lock:
            return self._revision

    @property
    def history(self) -> tuple[RegistryEvent, ...]:
        """Return an immutable snapshot of membership history."""
        with self._lock:
            return tuple(self._history)

    @property
    def components(self) -> tuple[Component, ...]:
        """Return active definitions sorted by their logical IDs."""
        with self._lock:
            return tuple(
                sorted(
                    self._components.values(),
                    key=lambda component: component.component_id,
                )
            )

    def register(self, component: Component) -> bool:
        """Register a definition.

        Returns True when membership changes and False when the identical
        definition is already registered. Conflicting definitions are
        rejected without changing registry state.
        """
        if not isinstance(component, Component):
            raise ValidationError("Only Component definitions can be registered.")

        component_id = _normalize_component_id(component.component_id)

        with self._lock:
            current = self._components.get(component_id)

            if current is not None:
                if current == component:
                    return False

                raise ValidationError(
                    "A different definition is already registered "
                    f"for component ID '{component_id}'."
                )

            previous = self._latest_by_id.get(component_id)
            if previous is not None and previous != component:
                versions_unchanged = (
                    previous.contract_version == component.contract_version
                    and previous.implementation_version == component.implementation_version
                )
                if versions_unchanged:
                    raise ValidationError(
                        "A changed historical component definition must "
                        "change its contract version or implementation "
                        "version."
                    )

            event = RegistryEvent(
                revision=self._revision + 1,
                kind=RegistryEventKind.REGISTERED,
                component=component,
                occurred_at=_utc_now(),
            )

            self._components[component_id] = component
            self._latest_by_id[component_id] = component
            self._history.append(event)
            self._revision = event.revision
            return True

    def get(self, component_id: str) -> Component | None:
        """Return an active definition, or None if it is not registered."""
        normalized = _normalize_component_id(component_id)

        with self._lock:
            return self._components.get(normalized)

    def contains(self, component_id: str) -> bool:
        """Return whether a logical component ID is currently registered."""
        return self.get(component_id) is not None

    def unregister(self, component_id: str) -> bool:
        """Remove active membership while preserving its history.

        Returns True when a definition is removed and False when the ID
        is already absent. An absent ID does not advance the revision.
        """
        normalized = _normalize_component_id(component_id)

        with self._lock:
            component = self._components.get(normalized)
            if component is None:
                return False

            event = RegistryEvent(
                revision=self._revision + 1,
                kind=RegistryEventKind.UNREGISTERED,
                component=component,
                occurred_at=_utc_now(),
            )

            del self._components[normalized]
            self._history.append(event)
            self._revision = event.revision
            return True
