"""Adversarial tests for M2.6 communication identity integrity."""

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.result import Result, ResultStatus
from backend.app.platform.communication import (
    DispatchStatus,
    InProcessCommunicator,
)
from backend.app.platform.component import Component, ComponentInstance
from backend.app.platform.message import Message
from backend.app.platform.runtime import Runtime


def make_running_runtime(runtime_id: str) -> Runtime:
    """Create a running runtime with a known identity."""
    runtime = Runtime(runtime_id=runtime_id)
    runtime.begin_start()
    runtime.mark_running()
    return runtime


def make_ready_instance(
    runtime: Runtime,
    *,
    component_id: str,
    instance_id: str,
) -> ComponentInstance:
    """Create a ready component instance attached to the runtime ID."""
    component = Component(
        component_id=component_id,
        name=f"{component_id}-component",
        contract_version="1.0",
        implementation_version="1.0",
        capabilities=frozenset({"communicate"}),
        declared_dependencies=frozenset(),
    )
    instance = ComponentInstance(
        component=component,
        runtime_id=runtime.runtime_id,
        instance_id=instance_id,
    )
    instance.begin_start()
    instance.mark_ready()
    return instance


def test_different_runtime_objects_cannot_share_one_runtime_identity() -> None:
    """A runtime ID identifies one authoritative runtime lifetime."""
    communicator = InProcessCommunicator()

    first_runtime = make_running_runtime("runtime-shared")
    first_instance = make_ready_instance(
        first_runtime,
        component_id="component-a",
        instance_id="instance-a",
    )
    assert communicator.register_endpoint(first_runtime, first_instance)

    second_runtime = make_running_runtime("runtime-shared")
    second_instance = make_ready_instance(
        second_runtime,
        component_id="component-b",
        instance_id="instance-b",
    )

    with pytest.raises(ValidationError, match="runtime ID"):
        communicator.register_endpoint(second_runtime, second_instance)


def test_runtime_identity_cannot_be_rebound_after_endpoint_removal() -> None:
    """Removing endpoints must not silently reassign a runtime identity."""
    communicator = InProcessCommunicator()

    first_runtime = make_running_runtime("runtime-historical")
    first_instance = make_ready_instance(
        first_runtime,
        component_id="component-a",
        instance_id="instance-a",
    )
    communicator.register_endpoint(first_runtime, first_instance)

    assert communicator.unregister_endpoint(first_runtime, first_instance)

    replacement_runtime = make_running_runtime("runtime-historical")
    replacement_instance = make_ready_instance(
        replacement_runtime,
        component_id="component-b",
        instance_id="instance-b",
    )

    with pytest.raises(ValidationError, match="runtime ID"):
        communicator.register_endpoint(
            replacement_runtime,
            replacement_instance,
        )


def test_sender_runtime_identity_cannot_be_spoofed_in_message() -> None:
    """The message sender runtime must match the registered endpoint."""
    communicator = InProcessCommunicator()

    sender_runtime = make_running_runtime("runtime-sender")
    sender = make_ready_instance(
        sender_runtime,
        component_id="sender",
        instance_id="sender-instance",
    )

    recipient_runtime = make_running_runtime("runtime-recipient")
    recipient = make_ready_instance(
        recipient_runtime,
        component_id="recipient",
        instance_id="recipient-instance",
    )

    communicator.register_endpoint(sender_runtime, sender)
    communicator.register_endpoint(recipient_runtime, recipient)

    communicator.register_handler(
        recipient,
        "test.message",
        "v1",
        lambda message: Result(status=ResultStatus.SUCCESS),
    )

    message = Message(
        message_type="test.message",
        sender_runtime_id="runtime-spoofed",
        sender_component_id=sender.component_id,
        sender_instance_id=sender.instance_id,
        destination_runtime_id=recipient.runtime_id,
        destination_component_id=recipient.component_id,
        destination_instance_id=recipient.instance_id,
        correlation_id="correlation-a",
        payload={"test": True},
    )

    receipt = communicator.send(sender, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "SENDER_IDENTITY_MISMATCH"
