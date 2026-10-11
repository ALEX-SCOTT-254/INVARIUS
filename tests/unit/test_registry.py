"""Tests for the M2.3 component registry foundation."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.component import Component
from backend.app.platform.registry import (
    ComponentRegistry,
    RegistryEvent,
    RegistryEventKind,
)


def make_component(
    component_id: str = "component-a",
    *,
    name: str = "sample",
    contract_version: str = "1.0",
    implementation_version: str = "1.0",
    capabilities: frozenset[str] = frozenset(),
    declared_dependencies: frozenset[str] = frozenset(),
) -> Component:
    """Build a component definition for registry tests."""
    return Component(
        component_id=component_id,
        name=name,
        contract_version=contract_version,
        implementation_version=implementation_version,
        capabilities=capabilities,
        declared_dependencies=declared_dependencies,
    )


def test_registry_starts_empty() -> None:
    registry = ComponentRegistry()

    assert registry.revision == 0
    assert registry.components == ()
    assert registry.history == ()


def test_register_adds_component_and_history_event() -> None:
    registry = ComponentRegistry()
    component = make_component()

    assert registry.register(component) is True
    assert registry.revision == 1
    assert registry.components == (component,)
    assert len(registry.history) == 1

    event = registry.history[0]
    assert event.revision == 1
    assert event.kind is RegistryEventKind.REGISTERED
    assert event.component == component
    assert event.component_id == component.component_id


def test_get_returns_registered_component() -> None:
    registry = ComponentRegistry()
    component = make_component()
    registry.register(component)

    assert registry.get(component.component_id) == component


def test_get_returns_none_for_missing_component() -> None:
    registry = ComponentRegistry()

    assert registry.get("missing-component") is None


def test_registering_identical_definition_is_idempotent() -> None:
    registry = ComponentRegistry()
    component = make_component()

    assert registry.register(component) is True
    assert registry.register(make_component()) is False
    assert registry.revision == 1
    assert len(registry.history) == 1


def test_conflicting_active_definition_is_rejected_without_mutation() -> None:
    registry = ComponentRegistry()
    original = make_component()
    conflicting = make_component(
        capabilities=frozenset({"inspection"}),
        implementation_version="2.0",
    )
    registry.register(original)

    with pytest.raises(ValidationError):
        registry.register(conflicting)

    assert registry.get(original.component_id) == original
    assert registry.revision == 1
    assert len(registry.history) == 1


def test_distinct_ids_can_share_a_name() -> None:
    registry = ComponentRegistry()
    first = make_component("component-a", name="shared-name")
    second = make_component("component-b", name="shared-name")

    assert registry.register(first) is True
    assert registry.register(second) is True
    assert registry.components == (first, second)
    assert registry.revision == 2


def test_unregister_removes_membership_and_preserves_history() -> None:
    registry = ComponentRegistry()
    component = make_component()
    registry.register(component)

    assert registry.unregister(component.component_id) is True

    assert registry.get(component.component_id) is None
    assert registry.components == ()
    assert registry.revision == 2
    assert len(registry.history) == 2

    registration, removal = registry.history
    assert registration.kind is RegistryEventKind.REGISTERED
    assert removal.kind is RegistryEventKind.UNREGISTERED
    assert registration.component == component
    assert removal.component == component


def test_unregistering_absent_component_is_idempotent() -> None:
    registry = ComponentRegistry()

    assert registry.unregister("missing-component") is False
    assert registry.revision == 0
    assert registry.history == ()


def test_same_definition_can_be_registered_after_deregistration() -> None:
    registry = ComponentRegistry()
    component = make_component()

    assert registry.register(component) is True
    assert registry.unregister(component.component_id) is True
    assert registry.register(component) is True

    assert registry.revision == 3
    assert registry.get(component.component_id) == component
    assert [event.revision for event in registry.history] == [1, 2, 3]
    assert [event.kind for event in registry.history] == [
        RegistryEventKind.REGISTERED,
        RegistryEventKind.UNREGISTERED,
        RegistryEventKind.REGISTERED,
    ]


def test_changed_definition_can_be_registered_with_new_version() -> None:
    registry = ComponentRegistry()
    original = make_component()
    updated = make_component(
        contract_version="2.0",
        capabilities=frozenset({"inspection"}),
    )

    registry.register(original)
    registry.unregister(original.component_id)

    assert registry.register(updated) is True
    assert registry.get(original.component_id) == updated
    assert registry.history[-1].component == updated


def test_changed_historical_definition_requires_version_change() -> None:
    registry = ComponentRegistry()
    original = make_component()
    changed = make_component(
        capabilities=frozenset({"inspection"}),
    )

    registry.register(original)
    registry.unregister(original.component_id)

    with pytest.raises(ValidationError):
        registry.register(changed)

    assert registry.get(original.component_id) is None
    assert registry.revision == 2
    assert len(registry.history) == 2


def test_active_definition_cannot_be_replaced_even_with_new_version() -> None:
    registry = ComponentRegistry()
    original = make_component()
    updated = make_component(implementation_version="2.0")
    registry.register(original)

    with pytest.raises(ValidationError):
        registry.register(updated)

    assert registry.get(original.component_id) == original
    assert registry.revision == 1


def test_contains_reflects_current_membership() -> None:
    registry = ComponentRegistry()
    component = make_component()

    assert registry.contains(component.component_id) is False

    registry.register(component)
    assert registry.contains(component.component_id) is True

    registry.unregister(component.component_id)
    assert registry.contains(component.component_id) is False


@pytest.mark.parametrize("value", [None, "not-a-component", object()])
def test_register_rejects_non_component_values(value: object) -> None:
    registry = ComponentRegistry()

    with pytest.raises(ValidationError):
        registry.register(value)  # type: ignore[arg-type]

    assert registry.revision == 0
    assert registry.history == ()


@pytest.mark.parametrize("component_id", ["", "   "])
def test_lookup_and_removal_reject_empty_ids(component_id: str) -> None:
    registry = ComponentRegistry()

    with pytest.raises(ValidationError):
        registry.get(component_id)

    with pytest.raises(ValidationError):
        registry.contains(component_id)

    with pytest.raises(ValidationError):
        registry.unregister(component_id)


def test_component_snapshots_are_sorted_by_logical_id() -> None:
    registry = ComponentRegistry()
    component_c = make_component("component-c")
    component_a = make_component("component-a")
    component_b = make_component("component-b")

    registry.register(component_c)
    registry.register(component_a)
    registry.register(component_b)

    assert registry.components == (
        component_a,
        component_b,
        component_c,
    )


def test_history_property_returns_an_immutable_snapshot() -> None:
    registry = ComponentRegistry()
    first = make_component("component-a")
    second = make_component("component-b")

    registry.register(first)
    earlier_snapshot = registry.history

    registry.register(second)

    assert len(earlier_snapshot) == 1
    assert len(registry.history) == 2


def test_component_snapshot_is_immutable() -> None:
    registry = ComponentRegistry()
    component = make_component()
    registry.register(component)

    with pytest.raises(AttributeError):
        registry.components[0].name = "changed"  # type: ignore[misc]


def test_registry_event_is_immutable() -> None:
    event = RegistryEvent(
        revision=1,
        kind=RegistryEventKind.REGISTERED,
        component=make_component(),
        occurred_at=datetime.now(timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        event.revision = 2  # type: ignore[misc]


def test_registry_event_timestamp_is_normalized_to_utc() -> None:
    offset = timezone(timedelta(hours=3))
    timestamp = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=offset,
    )
    event = RegistryEvent(
        revision=1,
        kind=RegistryEventKind.REGISTERED,
        component=make_component(),
        occurred_at=timestamp,
    )

    assert event.occurred_at.utcoffset() == timedelta(0)
    assert event.occurred_at.hour == 9


@pytest.mark.parametrize("revision", [0, -1, True, 1.5])
def test_registry_event_rejects_invalid_revisions(
    revision: object,
) -> None:
    with pytest.raises(ValidationError):
        RegistryEvent(
            revision=revision,  # type: ignore[arg-type]
            kind=RegistryEventKind.REGISTERED,
            component=make_component(),
            occurred_at=datetime.now(timezone.utc),
        )


def test_registry_event_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        RegistryEvent(
            revision=1,
            kind="registered",  # type: ignore[arg-type]
            component=make_component(),
            occurred_at=datetime.now(timezone.utc),
        )


def test_registry_event_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        RegistryEvent(
            revision=1,
            kind=RegistryEventKind.REGISTERED,
            component=make_component(),
            occurred_at=datetime(2026, 1, 1),
        )


def test_concurrent_identical_registration_has_one_membership_change() -> None:
    registry = ComponentRegistry()
    component = make_component()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(registry.register, [component] * 64))

    assert sum(results) == 1
    assert registry.revision == 1
    assert registry.components == (component,)
    assert len(registry.history) == 1
