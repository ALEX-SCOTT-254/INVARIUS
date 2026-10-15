"""M2.6 in-process communication boundary for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from threading import RLock
from typing import Callable, Protocol

from backend.app.core.errors import ValidationError
from backend.app.core.result import Result
from backend.app.platform.component import (
    ComponentInstance,
    ComponentInstanceState,
)
from backend.app.platform.message import (
    MESSAGE_CONTRACT_VERSION,
    Message,
)
from backend.app.platform.runtime import Runtime, RuntimeState

_MAX_TEXT_LENGTH = 256
_MAX_CODE_LENGTH = 128


class DispatchStatus(StrEnum):
    """Communication-level outcome, separate from operation outcome."""

    DELIVERED = "delivered"
    REJECTED = "rejected"
    HANDLER_FAILED = "handler_failed"


MessageHandler = Callable[[Message], Result]


def _normalize_text(
    value: object,
    field_name: str,
    *,
    max_length: int = _MAX_TEXT_LENGTH,
) -> str:
    """Validate and normalize bounded non-empty text."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(normalized) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")

    return normalized


def _normalize_timestamp(value: object) -> datetime:
    """Require a timezone-aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Dispatch timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Dispatch timestamp must include timezone information.")

    return value.astimezone(timezone.utc)


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _safe_exception_type(exc: Exception) -> str:
    """Return a bounded, non-empty exception type suitable for a receipt."""
    exception_type = type(exc).__name__

    if not isinstance(exception_type, str):
        return "Exception"

    normalized = exception_type.strip()[:_MAX_CODE_LENGTH]
    return normalized or "Exception"


@dataclass(frozen=True, slots=True)
class DispatchReceipt:
    """Immutable record of one communication attempt.

    DELIVERED means the registered handler returned a core Result.
    It does not mean that the operation itself succeeded.

    REJECTED means the message was not admitted for handler execution.
    HANDLER_FAILED means handler execution did not yield a valid Result.
    """

    message_id: str
    status: DispatchStatus
    occurred_at: datetime
    result: Result | None = None
    error_code: str | None = None
    reason: str | None = None
    exception_type: str | None = None

    def __post_init__(self) -> None:
        """Validate receipt invariants."""
        object.__setattr__(
            self,
            "message_id",
            _normalize_text(self.message_id, "Receipt message ID"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _normalize_timestamp(self.occurred_at),
        )

        if not isinstance(self.status, DispatchStatus):
            raise ValidationError("Dispatch status is invalid.")

        if self.result is not None and not isinstance(self.result, Result):
            raise ValidationError("Dispatch receipt result must be a core Result.")

        if self.status is DispatchStatus.DELIVERED:
            if self.result is None:
                raise ValidationError("A delivered receipt requires a core Result.")

            if (
                self.error_code is not None
                or self.reason is not None
                or self.exception_type is not None
            ):
                raise ValidationError("A delivered receipt cannot contain failure metadata.")
            return

        if self.result is not None:
            raise ValidationError("A failed dispatch receipt cannot contain a result.")

        if self.error_code is None or self.reason is None:
            raise ValidationError("A failed dispatch receipt requires an error code and reason.")

        object.__setattr__(
            self,
            "error_code",
            _normalize_text(
                self.error_code,
                "Dispatch error code",
                max_length=_MAX_CODE_LENGTH,
            ),
        )
        object.__setattr__(
            self,
            "reason",
            _normalize_text(self.reason, "Dispatch failure reason"),
        )

        if self.status is DispatchStatus.REJECTED:
            if self.exception_type is not None:
                raise ValidationError("A rejected receipt cannot contain an exception type.")
            return

        if self.status is DispatchStatus.HANDLER_FAILED:
            if self.exception_type is not None:
                object.__setattr__(
                    self,
                    "exception_type",
                    _normalize_text(
                        self.exception_type,
                        "Handler exception type",
                        max_length=_MAX_CODE_LENGTH,
                    ),
                )
            return


class CommunicationPort(Protocol):
    """Stable communication interface for component code."""

    def send(
        self,
        sender: ComponentInstance,
        message: Message,
    ) -> DispatchReceipt:
        """Submit a message from the registered sender endpoint."""
        ...


@dataclass(slots=True)
class _Endpoint:
    """Private registration owned by the in-process communicator."""

    runtime: Runtime
    instance: ComponentInstance
    handlers: dict[tuple[str, str], MessageHandler] = field(default_factory=dict)


class InProcessCommunicator:
    """Thread-safe, single-recipient, in-process communication.

    Endpoints are identified by runtime ID and component-instance ID.

    A runtime ID is permanently associated with the original Runtime
    object for this communicator's lifetime. Removing an endpoint does
    not permit a different Runtime object to reuse that runtime ID.

    Endpoint registration binds identifiers to actual runtime and
    component-instance objects. Message sender fields are checked against
    the registered sender endpoint; those fields are not authentication
    credentials.

    Endpoint lifecycle is checked at registration, handler registration,
    and dispatch admission. Once a handler has been admitted, unregistering
    its endpoint does not revoke that in-flight invocation.

    The communicator never holds its global lock while executing a handler.
    It does not implement authentication, authorization, persistence,
    background delivery, retries, timeouts, or distributed transport.
    """

    __slots__ = ("_endpoints", "_runtimes", "_lock")

    def __init__(self) -> None:
        self._endpoints: dict[tuple[str, str], _Endpoint] = {}
        # Retain runtime ownership even after its last endpoint is removed.
        # This prevents a new Runtime object from reusing a historical ID.
        self._runtimes: dict[str, Runtime] = {}
        self._lock = RLock()

    @staticmethod
    def _key(
        runtime_id: str,
        instance_id: str,
    ) -> tuple[str, str]:
        return runtime_id, instance_id

    @staticmethod
    def _require_ready(
        runtime: Runtime,
        instance: ComponentInstance,
        role: str,
    ) -> str | None:
        """Return a failure reason if an endpoint is not available."""
        if runtime.state is not RuntimeState.RUNNING:
            return f"{role} runtime is not running."

        if instance.state is not ComponentInstanceState.READY:
            return f"{role} component instance is not ready."

        return None

    @staticmethod
    def _rejected(
        message: Message,
        error_code: str,
        reason: str,
    ) -> DispatchReceipt:
        """Create an explicit pre-handler rejection receipt."""
        return DispatchReceipt(
            message_id=message.message_id,
            status=DispatchStatus.REJECTED,
            occurred_at=_utc_now(),
            error_code=error_code,
            reason=reason,
        )

    def register_endpoint(
        self,
        runtime: Runtime,
        instance: ComponentInstance,
    ) -> bool:
        """Register one running runtime and ready component instance.

        Returns False for the identical existing registration. Conflicting
        objects, including a different Runtime with an already-claimed
        runtime ID, are rejected.
        """
        if not isinstance(runtime, Runtime):
            raise ValidationError("Endpoint registration requires a platform Runtime.")

        if not isinstance(instance, ComponentInstance):
            raise ValidationError("Endpoint registration requires a ComponentInstance.")

        if instance.runtime_id != runtime.runtime_id:
            raise ValidationError("Component instance belongs to a different runtime.")

        unavailable = self._require_ready(runtime, instance, "Registered")
        if unavailable is not None:
            raise ValidationError(unavailable)

        key = self._key(runtime.runtime_id, instance.instance_id)

        with self._lock:
            known_runtime = self._runtimes.get(runtime.runtime_id)

            if known_runtime is not None and known_runtime is not runtime:
                raise ValidationError(
                    "A different Runtime object is already associated "
                    f"with runtime ID '{runtime.runtime_id}'."
                )

            current = self._endpoints.get(key)

            if current is not None:
                if current.runtime is runtime and current.instance is instance:
                    return False

                raise ValidationError(
                    "A different endpoint is already registered for "
                    f"runtime '{runtime.runtime_id}' and "
                    f"instance '{instance.instance_id}'."
                )

            # Recheck availability before admitting the endpoint.
            unavailable = self._require_ready(
                runtime,
                instance,
                "Registered",
            )
            if unavailable is not None:
                raise ValidationError(unavailable)

            self._runtimes[runtime.runtime_id] = runtime
            self._endpoints[key] = _Endpoint(
                runtime=runtime,
                instance=instance,
            )
            return True

    def unregister_endpoint(
        self,
        runtime: Runtime,
        instance: ComponentInstance,
    ) -> bool:
        """Remove an exact endpoint registration.

        Returns False if the endpoint no longer exists. A conflicting
        object claiming the same IDs is rejected rather than removed.
        Runtime identity ownership is retained.
        """
        if not isinstance(runtime, Runtime):
            raise ValidationError("Endpoint requires a platform Runtime.")

        if not isinstance(instance, ComponentInstance):
            raise ValidationError("Endpoint requires a ComponentInstance.")

        key = self._key(runtime.runtime_id, instance.instance_id)

        with self._lock:
            known_runtime = self._runtimes.get(runtime.runtime_id)

            if known_runtime is not None and known_runtime is not runtime:
                raise ValidationError(
                    "Runtime object does not match the object associated "
                    f"with runtime ID '{runtime.runtime_id}'."
                )

            current = self._endpoints.get(key)

            if current is None:
                return False

            if current.runtime is not runtime or current.instance is not instance:
                raise ValidationError("Endpoint identity does not match the registered objects.")

            del self._endpoints[key]
            return True

    def register_handler(
        self,
        instance: ComponentInstance,
        message_type: str,
        payload_schema_version: str,
        handler: MessageHandler,
    ) -> bool:
        """Register a handler for an exact message type and schema version.

        Returns False when the same handler object is already registered.
        Conflicting handlers for the same key are rejected.
        """
        if not isinstance(instance, ComponentInstance):
            raise ValidationError("Handler registration requires a ComponentInstance.")

        normalized_message_type = _normalize_text(
            message_type,
            "Handler message type",
            max_length=128,
        )
        normalized_schema_version = _normalize_text(
            payload_schema_version,
            "Handler payload schema version",
        )

        if not callable(handler):
            raise ValidationError("Message handler must be callable.")

        key = self._key(instance.runtime_id, instance.instance_id)
        handler_key = (normalized_message_type, normalized_schema_version)

        with self._lock:
            endpoint = self._endpoints.get(key)

            if endpoint is None or endpoint.instance is not instance:
                raise ValidationError("Cannot register a handler for an unregistered endpoint.")

            unavailable = self._require_ready(
                endpoint.runtime,
                endpoint.instance,
                "Handler registration",
            )
            if unavailable is not None:
                raise ValidationError(unavailable)

            current = endpoint.handlers.get(handler_key)

            if current is handler:
                return False

            if current is not None:
                raise ValidationError(
                    "A different handler is already registered for "
                    f"message type '{normalized_message_type}' and "
                    f"schema version '{normalized_schema_version}'."
                )

            endpoint.handlers[handler_key] = handler
            return True

    def send(
        self,
        sender: ComponentInstance,
        message: Message,
    ) -> DispatchReceipt:
        """Validate, route, and synchronously dispatch one message."""
        if not isinstance(sender, ComponentInstance):
            raise ValidationError("Dispatch requires a registered sender ComponentInstance.")

        if not isinstance(message, Message):
            raise ValidationError("Dispatch requires a valid Message.")

        if message.contract_version != MESSAGE_CONTRACT_VERSION:
            return self._rejected(
                message,
                "UNSUPPORTED_MESSAGE_CONTRACT",
                "The message contract version is not supported.",
            )

        sender_key = self._key(sender.runtime_id, sender.instance_id)

        # Admission checks and handler lookup happen under the registry lock.
        # The handler itself executes after the lock has been released.
        with self._lock:
            sender_endpoint = self._endpoints.get(sender_key)

            if sender_endpoint is None:
                return self._rejected(
                    message,
                    "SENDER_NOT_REGISTERED",
                    "The sender endpoint is not registered.",
                )

            if sender_endpoint.instance is not sender:
                return self._rejected(
                    message,
                    "SENDER_IDENTITY_MISMATCH",
                    "The sender object does not match its registered endpoint.",
                )

            if self._runtimes.get(sender.runtime_id) is not sender_endpoint.runtime:
                return self._rejected(
                    message,
                    "SENDER_IDENTITY_MISMATCH",
                    "The sender runtime does not match its registered runtime.",
                )

            if (
                message.sender_runtime_id != sender_endpoint.runtime.runtime_id
                or message.sender_component_id != sender.component_id
                or message.sender_instance_id != sender.instance_id
            ):
                return self._rejected(
                    message,
                    "SENDER_IDENTITY_MISMATCH",
                    "Message sender fields do not match the registered sender.",
                )

            sender_unavailable = self._require_ready(
                sender_endpoint.runtime,
                sender_endpoint.instance,
                "Sender",
            )
            if sender_unavailable is not None:
                return self._rejected(
                    message,
                    "SENDER_UNAVAILABLE",
                    sender_unavailable,
                )

            destination_key = self._key(
                message.destination_runtime_id,
                message.destination_instance_id,
            )
            destination = self._endpoints.get(destination_key)

            if destination is None:
                return self._rejected(
                    message,
                    "RECIPIENT_NOT_REGISTERED",
                    "The destination endpoint is not registered.",
                )

            if self._runtimes.get(message.destination_runtime_id) is not destination.runtime:
                return self._rejected(
                    message,
                    "RECIPIENT_IDENTITY_MISMATCH",
                    "The destination runtime does not match the registered runtime.",
                )

            if destination.instance.component_id != message.destination_component_id:
                return self._rejected(
                    message,
                    "RECIPIENT_IDENTITY_MISMATCH",
                    "The destination component ID does not match the endpoint.",
                )

            destination_unavailable = self._require_ready(
                destination.runtime,
                destination.instance,
                "Recipient",
            )
            if destination_unavailable is not None:
                return self._rejected(
                    message,
                    "RECIPIENT_UNAVAILABLE",
                    destination_unavailable,
                )

            handler_key = (
                message.message_type,
                message.payload_schema_version,
            )
            handler = destination.handlers.get(handler_key)

            if handler is None:
                supported_types = {registered_type for registered_type, _ in destination.handlers}

                if message.message_type not in supported_types:
                    return self._rejected(
                        message,
                        "HANDLER_NOT_REGISTERED",
                        "No handler is registered for this message type.",
                    )

                return self._rejected(
                    message,
                    "UNSUPPORTED_PAYLOAD_SCHEMA",
                    "No handler supports this payload schema version.",
                )

        # Never invoke user-supplied code while holding the global lock.
        try:
            result = handler(message)
        except Exception as exc:
            exception_type = _safe_exception_type(exc)

            return DispatchReceipt(
                message_id=message.message_id,
                status=DispatchStatus.HANDLER_FAILED,
                occurred_at=_utc_now(),
                error_code="HANDLER_EXCEPTION",
                # Do not expose the original exception message; keep the
                # reason bounded and independent of user-defined class names.
                reason="The handler raised an unexpected exception.",
                exception_type=exception_type,
            )

        if not isinstance(result, Result):
            return DispatchReceipt(
                message_id=message.message_id,
                status=DispatchStatus.HANDLER_FAILED,
                occurred_at=_utc_now(),
                error_code="INVALID_HANDLER_RESULT",
                reason="The handler did not return a core Result instance.",
            )

        # Delivery success is independent from the Result's status.
        return DispatchReceipt(
            message_id=message.message_id,
            status=DispatchStatus.DELIVERED,
            occurred_at=_utc_now(),
            result=result,
        )
