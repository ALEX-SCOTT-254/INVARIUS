"""Tests for the M2.6 in-process communication boundary."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from threading import Event, Lock

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.result import Result, ResultStatus
from backend.app.platform.communication import (
    DispatchReceipt,
    DispatchStatus,
    InProcessCommunicator,
)
from backend.app.platform.component import (
    Component,
    ComponentInstance,
)
from backend.app.platform.message import Message
from backend.app.platform.runtime import Runtime


def make_runtime(runtime_id: str = "runtime-a") -> Runtime:
    """Create a running runtime."""
    runtime = Runtime(runtime_id=runtime_id)
    runtime.begin_start()
    runtime.mark_running()
    return runtime


def make_instance(
    runtime: Runtime,
    component_id: str,
    instance_id: str,
    *,
    ready: bool = True,
    instance_runtime_id: str | None = None,
) -> ComponentInstance:
    """Create a component instance with optional readiness."""
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
        runtime_id=(runtime.runtime_id if instance_runtime_id is None else instance_runtime_id),
        instance_id=instance_id,
    )

    if ready:
        instance.begin_start()
        instance.mark_ready()

    return instance


def make_environment() -> tuple[
    InProcessCommunicator,
    Runtime,
    ComponentInstance,
    Runtime,
    ComponentInstance,
]:
    """Create registered sender and recipient in separate runtimes."""
    communicator = InProcessCommunicator()

    sender_runtime = make_runtime("runtime-sender")
    sender = make_instance(
        sender_runtime,
        "ingestion",
        "ingestion-instance",
    )

    recipient_runtime = make_runtime("runtime-recipient")
    recipient = make_instance(
        recipient_runtime,
        "language-analysis",
        "language-analysis-instance",
    )

    communicator.register_endpoint(sender_runtime, sender)
    communicator.register_endpoint(recipient_runtime, recipient)

    return (
        communicator,
        sender_runtime,
        sender,
        recipient_runtime,
        recipient,
    )


def make_message(
    sender: ComponentInstance,
    recipient: ComponentInstance,
    *,
    sender_runtime_id: str | None = None,
    sender_component_id: str | None = None,
    sender_instance_id: str | None = None,
    destination_runtime_id: str | None = None,
    destination_component_id: str | None = None,
    destination_instance_id: str | None = None,
    message_type: str = "project.inspect",
    payload_schema_version: str = "v1",
    message_id: str = "message-a",
) -> Message:
    """Build a message for the supplied endpoints."""
    return Message(
        message_id=message_id,
        message_type=message_type,
        sender_runtime_id=(sender.runtime_id if sender_runtime_id is None else sender_runtime_id),
        sender_component_id=(
            sender.component_id if sender_component_id is None else sender_component_id
        ),
        sender_instance_id=(
            sender.instance_id if sender_instance_id is None else sender_instance_id
        ),
        destination_runtime_id=(
            recipient.runtime_id if destination_runtime_id is None else destination_runtime_id
        ),
        destination_component_id=(
            recipient.component_id if destination_component_id is None else destination_component_id
        ),
        destination_instance_id=(
            recipient.instance_id if destination_instance_id is None else destination_instance_id
        ),
        correlation_id="correlation-a",
        operation_id="operation-a",
        payload={"project_id": "project-a"},
        payload_schema_version=payload_schema_version,
    )


def make_result(
    status: ResultStatus = ResultStatus.SUCCESS,
) -> Result:
    """Build the existing core operation outcome."""
    return Result(status=status)


def register_success_handler(
    communicator: InProcessCommunicator,
    recipient: ComponentInstance,
    *,
    result: Result | None = None,
) -> Result:
    """Register a handler that returns one known core Result."""
    handler_result = make_result() if result is None else result

    def handler(message: Message) -> Result:
        assert message.message_type == "project.inspect"
        return handler_result

    communicator.register_handler(
        recipient,
        "project.inspect",
        "v1",
        handler,
    )
    return handler_result


def test_endpoint_registration_accepts_ready_endpoint() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")

    assert communicator.register_endpoint(runtime, instance) is True


def test_identical_endpoint_registration_is_idempotent() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")

    assert communicator.register_endpoint(runtime, instance) is True
    assert communicator.register_endpoint(runtime, instance) is False


@pytest.mark.parametrize("kind", ["runtime", "instance"])
def test_endpoint_registration_rejects_wrong_object_types(
    kind: str,
) -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")

    with pytest.raises(ValidationError):
        if kind == "runtime":
            communicator.register_endpoint(
                object(),  # type: ignore[arg-type]
                instance,
            )
        else:
            communicator.register_endpoint(
                runtime,
                object(),  # type: ignore[arg-type]
            )


def test_endpoint_registration_rejects_runtime_identity_mismatch() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime("runtime-a")
    instance = make_instance(
        runtime,
        "component-a",
        "instance-a",
        instance_runtime_id="runtime-b",
    )

    with pytest.raises(ValidationError, match="different runtime"):
        communicator.register_endpoint(runtime, instance)


def test_endpoint_registration_rejects_non_running_runtime() -> None:
    communicator = InProcessCommunicator()
    runtime = Runtime(runtime_id="runtime-created")
    instance = make_instance(
        runtime,
        "component-a",
        "instance-a",
        ready=False,
    )

    with pytest.raises(ValidationError, match="runtime is not running"):
        communicator.register_endpoint(runtime, instance)


def test_endpoint_registration_rejects_unready_instance() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(
        runtime,
        "component-a",
        "instance-a",
        ready=False,
    )

    with pytest.raises(ValidationError, match="instance is not ready"):
        communicator.register_endpoint(runtime, instance)


def test_endpoint_registration_rejects_conflicting_instance_object() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    first = make_instance(runtime, "component-a", "instance-a")
    conflicting = make_instance(runtime, "component-b", "instance-a")

    communicator.register_endpoint(runtime, first)

    with pytest.raises(ValidationError, match="different endpoint"):
        communicator.register_endpoint(runtime, conflicting)


def test_unregister_endpoint_removes_exact_registration() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")
    communicator.register_endpoint(runtime, instance)

    assert communicator.unregister_endpoint(runtime, instance) is True
    assert communicator.unregister_endpoint(runtime, instance) is False


def test_unregister_endpoint_rejects_conflicting_instance_object() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    registered = make_instance(runtime, "component-a", "instance-a")
    conflicting = make_instance(runtime, "component-b", "instance-a")
    communicator.register_endpoint(runtime, registered)

    with pytest.raises(ValidationError, match="does not match"):
        communicator.unregister_endpoint(runtime, conflicting)


def test_handler_registration_requires_registered_endpoint() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")

    with pytest.raises(ValidationError, match="unregistered endpoint"):
        communicator.register_handler(
            instance,
            "project.inspect",
            "v1",
            lambda message: make_result(),
        )


def test_handler_registration_rejects_non_callable_handler() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")
    communicator.register_endpoint(runtime, instance)

    with pytest.raises(ValidationError, match="must be callable"):
        communicator.register_handler(
            instance,
            "project.inspect",
            "v1",
            object(),  # type: ignore[arg-type]
        )


def test_handler_registration_is_idempotent_for_same_handler() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")
    communicator.register_endpoint(runtime, instance)

    def handler(message: Message) -> Result:
        return make_result()

    assert communicator.register_handler(instance, "project.inspect", "v1", handler) is True
    assert communicator.register_handler(instance, "project.inspect", "v1", handler) is False


def test_handler_registration_rejects_conflicting_handler() -> None:
    communicator = InProcessCommunicator()
    runtime = make_runtime()
    instance = make_instance(runtime, "component-a", "instance-a")
    communicator.register_endpoint(runtime, instance)

    def first(message: Message) -> Result:
        return make_result()

    def second(message: Message) -> Result:
        return make_result()

    communicator.register_handler(instance, "project.inspect", "v1", first)

    with pytest.raises(ValidationError, match="different handler"):
        communicator.register_handler(instance, "project.inspect", "v1", second)


def test_send_delivers_to_registered_handler() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    message = make_message(sender, recipient)
    observed: list[Message] = []
    result = make_result()

    def handler(received: Message) -> Result:
        observed.append(received)
        return result

    communicator.register_handler(recipient, "project.inspect", "v1", handler)

    receipt = communicator.send(sender, message)

    assert receipt.status is DispatchStatus.DELIVERED
    assert receipt.message_id == message.message_id
    assert receipt.result is result
    assert observed == [message]
    assert receipt.error_code is None
    assert receipt.reason is None


@pytest.mark.parametrize(
    "status",
    [
        ResultStatus.SUCCESS,
        ResultStatus.PARTIAL,
        ResultStatus.FAILURE,
        ResultStatus.UNRESOLVED,
    ],
)
def test_delivery_preserves_operation_result_status(
    status: ResultStatus,
) -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    result = make_result(status)
    register_success_handler(communicator, recipient, result=result)

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.DELIVERED
    assert receipt.result is result
    assert receipt.result.status is status


def test_send_rejects_unregistered_sender() -> None:
    (
        communicator,
        _sender_runtime,
        _sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    other_runtime = make_runtime("runtime-unregistered")
    unregistered = make_instance(
        other_runtime,
        "unregistered",
        "unregistered-instance",
    )
    message = make_message(unregistered, recipient)

    receipt = communicator.send(unregistered, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "SENDER_NOT_REGISTERED"


def test_send_rejects_sender_identity_mismatch_in_message() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    register_success_handler(communicator, recipient)
    message = make_message(
        sender,
        recipient,
        sender_component_id="spoofed-component",
    )

    receipt = communicator.send(sender, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "SENDER_IDENTITY_MISMATCH"


def test_send_rejects_different_object_claiming_registered_sender_ids() -> None:
    (
        communicator,
        sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    register_success_handler(communicator, recipient)
    spoof = make_instance(
        sender_runtime,
        sender.component_id,
        sender.instance_id,
    )
    message = make_message(sender, recipient)

    receipt = communicator.send(spoof, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "SENDER_IDENTITY_MISMATCH"


def test_send_rejects_missing_recipient() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    message = make_message(
        sender,
        recipient,
        destination_runtime_id="missing-runtime",
    )

    receipt = communicator.send(sender, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "RECIPIENT_NOT_REGISTERED"


def test_send_rejects_destination_component_mismatch() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    message = make_message(
        sender,
        recipient,
        destination_component_id="different-component",
    )

    receipt = communicator.send(sender, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "RECIPIENT_IDENTITY_MISMATCH"


def test_send_rejects_sender_whose_runtime_is_stopping() -> None:
    (
        communicator,
        sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    register_success_handler(communicator, recipient)
    sender_runtime.begin_stop()

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "SENDER_UNAVAILABLE"


def test_send_rejects_recipient_whose_instance_is_stopping() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    register_success_handler(communicator, recipient)
    recipient.begin_stop()

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "RECIPIENT_UNAVAILABLE"


def test_send_rejects_missing_handler() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "HANDLER_NOT_REGISTERED"


def test_send_rejects_unsupported_payload_schema() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    register_success_handler(communicator, recipient)
    message = make_message(
        sender,
        recipient,
        payload_schema_version="v2",
    )

    receipt = communicator.send(sender, message)

    assert receipt.status is DispatchStatus.REJECTED
    assert receipt.error_code == "UNSUPPORTED_PAYLOAD_SCHEMA"


def test_handler_exception_is_an_explicit_failure() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()

    def handler(message: Message) -> Result:
        raise RuntimeError("sensitive internal diagnostic")

    communicator.register_handler(recipient, "project.inspect", "v1", handler)

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.HANDLER_FAILED
    assert receipt.error_code == "HANDLER_EXCEPTION"
    assert receipt.exception_type == "RuntimeError"
    assert "sensitive internal diagnostic" not in (receipt.reason or "")


def test_handler_returning_non_result_is_a_failure() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()

    communicator.register_handler(
        recipient,
        "project.inspect",
        "v1",
        lambda message: object(),  # type: ignore[arg-type,return-value]
    )

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.HANDLER_FAILED
    assert receipt.error_code == "INVALID_HANDLER_RESULT"


def test_handler_failure_does_not_claim_delivery() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()

    def handler(message: Message) -> Result:
        raise ValueError("failure")

    communicator.register_handler(recipient, "project.inspect", "v1", handler)
    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.HANDLER_FAILED
    assert receipt.result is None


def test_send_rejects_non_component_sender() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()

    with pytest.raises(ValidationError, match="ComponentInstance"):
        communicator.send(
            object(),  # type: ignore[arg-type]
            make_message(sender, recipient),
        )


def test_send_rejects_non_message() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()

    with pytest.raises(ValidationError, match="valid Message"):
        communicator.send(
            sender,
            object(),  # type: ignore[arg-type]
        )


def test_dispatch_receipt_is_immutable() -> None:
    receipt = DispatchReceipt(
        message_id="message-a",
        status=DispatchStatus.DELIVERED,
        occurred_at=datetime.now(timezone.utc),
        result=make_result(),
    )

    with pytest.raises(FrozenInstanceError):
        receipt.message_id = "changed"  # type: ignore[misc]


def test_dispatch_receipt_rejects_delivery_without_result() -> None:
    with pytest.raises(ValidationError, match="requires a core Result"):
        DispatchReceipt(
            message_id="message-a",
            status=DispatchStatus.DELIVERED,
            occurred_at=datetime.now(timezone.utc),
        )


def test_dispatch_receipt_rejects_failure_without_error_details() -> None:
    with pytest.raises(ValidationError, match="error code and reason"):
        DispatchReceipt(
            message_id="message-a",
            status=DispatchStatus.REJECTED,
            occurred_at=datetime.now(timezone.utc),
        )


def test_dispatch_receipt_normalizes_timestamp_to_utc() -> None:
    receipt = DispatchReceipt(
        message_id="message-a",
        status=DispatchStatus.DELIVERED,
        occurred_at=datetime(
            2026,
            1,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        result=make_result(),
    )

    assert receipt.occurred_at.utcoffset().total_seconds() == 0


def test_concurrent_dispatches_preserve_each_result() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    count = 0
    count_lock = Lock()

    def handler(message: Message) -> Result:
        nonlocal count
        with count_lock:
            count += 1
        return Result(
            status=ResultStatus.SUCCESS,
            value={"message_id": message.message_id},
        )

    communicator.register_handler(recipient, "project.inspect", "v1", handler)

    messages = [
        make_message(sender, recipient, message_id=f"message-{index}") for index in range(32)
    ]

    with ThreadPoolExecutor(max_workers=8) as executor:
        receipts = list(
            executor.map(
                lambda message: communicator.send(sender, message),
                messages,
            )
        )

    assert count == 32
    assert all(receipt.status is DispatchStatus.DELIVERED for receipt in receipts)
    assert {
        receipt.result.value["message_id"] for receipt in receipts if receipt.result is not None
    } == {message.message_id for message in messages}


def test_handler_runs_without_holding_global_registry_lock() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        recipient_runtime,
        recipient,
    ) = make_environment()
    handler_entered = Event()
    release_handler = Event()

    def blocking_handler(message: Message) -> Result:
        handler_entered.set()
        if not release_handler.wait(timeout=5):
            raise RuntimeError("test handler release timed out")
        return make_result()

    communicator.register_handler(
        recipient,
        "project.inspect",
        "v1",
        blocking_handler,
    )

    message = make_message(sender, recipient)

    with ThreadPoolExecutor(max_workers=2) as executor:
        dispatch_future = executor.submit(communicator.send, sender, message)

        try:
            assert handler_entered.wait(timeout=2)

            unregister_future = executor.submit(
                communicator.unregister_endpoint,
                recipient_runtime,
                recipient,
            )

            assert unregister_future.result(timeout=2) is True
        finally:
            release_handler.set()

        receipt = dispatch_future.result(timeout=2)

    assert receipt.status is DispatchStatus.DELIVERED
    assert receipt.result is not None


def test_overlong_handler_exception_type_returns_bounded_failure_receipt() -> None:
    (
        communicator,
        _sender_runtime,
        sender,
        _recipient_runtime,
        recipient,
    ) = make_environment()
    exception_name = "X" * 129
    custom_exception = type(exception_name, (RuntimeError,), {})

    def handler(message: Message) -> Result:
        raise custom_exception("internal diagnostic must not escape")

    communicator.register_handler(recipient, "project.inspect", "v1", handler)

    receipt = communicator.send(sender, make_message(sender, recipient))

    assert receipt.status is DispatchStatus.HANDLER_FAILED
    assert receipt.error_code == "HANDLER_EXCEPTION"
    assert receipt.exception_type == exception_name[:128]
    assert receipt.reason is not None
    assert len(receipt.reason) <= 256
    assert "internal diagnostic must not escape" not in receipt.reason
