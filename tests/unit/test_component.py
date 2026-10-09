"""Tests for M2.2 component model."""

from datetime import datetime, timezone
from threading import Barrier, Thread

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.component import (
    Component,
    ComponentInstance,
    ComponentInstanceState,
)


def make_component() -> Component:
    return Component(
        component_id="component-1",
        name="Parser",
        contract_version="1",
        implementation_version="1.2.0",
        capabilities=frozenset({"parse"}),
        declared_dependencies=frozenset({"storage"}),
    )


def test_component_definition_is_immutable() -> None:
    component = make_component()

    assert component.component_id == "component-1"
    assert component.name == "Parser"
    assert component.contract_version == "1"
    assert component.implementation_version == "1.2.0"
    assert component.capabilities == frozenset({"parse"})
    assert component.declared_dependencies == frozenset({"storage"})

    with pytest.raises(AttributeError):
        component.name = "Changed"  # type: ignore[misc]


def test_component_collections_are_immutable() -> None:
    component = make_component()

    assert isinstance(component.capabilities, frozenset)
    assert isinstance(component.declared_dependencies, frozenset)


def test_component_normalizes_mutable_collections() -> None:
    capabilities = {"parse", "inspect"}
    dependencies = {"storage", "configuration"}

    component = Component(
        component_id=" component-1 ",
        name=" Parser ",
        contract_version=" 1 ",
        implementation_version=" 1.2.0 ",
        capabilities=capabilities,
        declared_dependencies=dependencies,
    )

    capabilities.add("new-capability")
    dependencies.add("new-dependency")

    assert component.component_id == "component-1"
    assert component.name == "Parser"
    assert component.contract_version == "1"
    assert component.implementation_version == "1.2.0"
    assert component.capabilities == frozenset({"parse", "inspect"})
    assert component.declared_dependencies == frozenset({"storage", "configuration"})


@pytest.mark.parametrize(
    "capabilities",
    [
        [],
        ("parse",),
        {"parse": True},
    ],
)
def test_component_rejects_invalid_capability_collection(
    capabilities: object,
) -> None:
    with pytest.raises(ValidationError):
        Component(
            component_id="component-1",
            name="Parser",
            contract_version="1",
            implementation_version="1.0.0",
            capabilities=capabilities,  # type: ignore[arg-type]
            declared_dependencies=frozenset(),
        )


def test_component_rejects_empty_definition_fields() -> None:
    with pytest.raises(ValidationError):
        Component(
            component_id=" ",
            name="Parser",
            contract_version="1",
            implementation_version="1.0.0",
            capabilities=frozenset(),
            declared_dependencies=frozenset(),
        )


def test_instance_starts_in_created_state() -> None:
    created_at = datetime(2026, 10, 8, 10, 0, tzinfo=timezone.utc)

    instance = ComponentInstance(
        make_component(),
        "runtime-1",
        instance_id="instance-1",
        created_at=created_at,
    )

    assert instance.instance_id == "instance-1"
    assert instance.component_id == "component-1"
    assert instance.runtime_id == "runtime-1"
    assert instance.implementation_version == "1.2.0"
    assert instance.created_at == created_at
    assert instance.state == ComponentInstanceState.CREATED
    assert instance.revision == 0
    assert instance.is_terminal is False


def test_instance_captures_implementation_version() -> None:
    component = make_component()

    instance = ComponentInstance(component, "runtime-1")

    assert instance.implementation_version == component.implementation_version


def test_instance_startup_path_is_revisioned() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")

    starting = instance.begin_start(at=datetime(2026, 10, 8, 10, 1, tzinfo=timezone.utc))
    ready = instance.mark_ready(at=datetime(2026, 10, 8, 10, 2, tzinfo=timezone.utc))

    assert starting.revision == 1
    assert starting.from_state == ComponentInstanceState.CREATED
    assert starting.to_state == ComponentInstanceState.STARTING

    assert ready.revision == 2
    assert ready.from_state == ComponentInstanceState.STARTING
    assert ready.to_state == ComponentInstanceState.READY

    assert instance.state == ComponentInstanceState.READY
    assert instance.revision == 2


def test_instance_shutdown_path_reaches_terminal_state() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()
    instance.mark_ready()

    instance.begin_stop()
    stopped = instance.mark_stopped()

    assert stopped.to_state == ComponentInstanceState.STOPPED
    assert instance.state == ComponentInstanceState.STOPPED
    assert instance.is_terminal is True


@pytest.mark.parametrize(
    "starting_state",
    [
        ComponentInstanceState.STARTING,
        ComponentInstanceState.READY,
        ComponentInstanceState.STOPPING,
    ],
)
def test_instance_can_fail_from_active_states(
    starting_state: ComponentInstanceState,
) -> None:
    instance = ComponentInstance(make_component(), "runtime-1")

    if starting_state == ComponentInstanceState.STARTING:
        instance.begin_start()
    elif starting_state == ComponentInstanceState.READY:
        instance.begin_start()
        instance.mark_ready()
    else:
        instance.begin_start()
        instance.mark_ready()
        instance.begin_stop()

    transition = instance.mark_failed(reason="component failure")

    assert transition.to_state == ComponentInstanceState.FAILED
    assert transition.reason == "component failure"
    assert instance.state == ComponentInstanceState.FAILED
    assert instance.is_terminal is True


@pytest.mark.parametrize(
    "action",
    [
        "mark_ready",
        "begin_stop",
        "mark_stopped",
        "mark_failed",
    ],
)
def test_invalid_transition_does_not_mutate_instance(action: str) -> None:
    instance = ComponentInstance(make_component(), "runtime-1")

    with pytest.raises(ValidationError):
        getattr(instance, action)()

    assert instance.state == ComponentInstanceState.CREATED
    assert instance.revision == 0
    assert len(instance.history) == 1


def test_terminal_instance_cannot_transition() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()
    instance.mark_ready()
    instance.begin_stop()
    instance.mark_stopped()

    with pytest.raises(ValidationError):
        instance.begin_start()

    assert instance.state == ComponentInstanceState.STOPPED
    assert instance.revision == 4


def test_failed_instance_cannot_transition() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()
    instance.mark_failed(reason="startup failure")

    with pytest.raises(ValidationError):
        instance.mark_ready()

    assert instance.state == ComponentInstanceState.FAILED
    assert instance.revision == 2


def test_instance_identity_is_stable() -> None:
    instance = ComponentInstance(
        make_component(),
        "runtime-1",
        instance_id="instance-immutable",
    )

    instance.begin_start()
    instance.mark_ready()

    assert instance.instance_id == "instance-immutable"
    assert instance.component_id == "component-1"
    assert instance.runtime_id == "runtime-1"


def test_instance_history_is_immutable_from_public_view() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()

    history = instance.history

    assert isinstance(history, tuple)
    assert len(history) == 2


def test_instance_history_preserves_prior_snapshot() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()

    original_history = instance.history

    instance.mark_ready()

    assert len(original_history) == 2
    assert original_history[-1].to_state == ComponentInstanceState.STARTING
    assert instance.history[-1].to_state == ComponentInstanceState.READY


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ComponentInstance(
            make_component(),
            "runtime-1",
            created_at=datetime(2026, 10, 8, 10, 0),
        )


def test_invalid_runtime_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ComponentInstance(make_component(), "   ")


def test_invalid_instance_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ComponentInstance(
            make_component(),
            "runtime-1",
            instance_id="   ",
        )


def test_reason_is_normalized() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()

    transition = instance.mark_failed(reason="  dependency unavailable  ")

    assert transition.reason == "dependency unavailable"


def test_concurrent_transition_has_one_authoritative_winner() -> None:
    instance = ComponentInstance(make_component(), "runtime-1")
    instance.begin_start()

    barrier = Barrier(3)
    results: list[str] = []

    def attempt_transition() -> None:
        barrier.wait()
        try:
            instance.mark_ready()
        except ValidationError:
            results.append("rejected")
        else:
            results.append("accepted")

    workers = [
        Thread(target=attempt_transition),
        Thread(target=attempt_transition),
    ]

    for worker in workers:
        worker.start()

    barrier.wait()

    for worker in workers:
        worker.join()

    assert sorted(results) == ["accepted", "rejected"]
    assert instance.state == ComponentInstanceState.READY
    assert instance.revision == 2
    assert len(instance.history) == 3
