"""M2.6 immutable message contract for INVARIUS."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.app.core.errors import ValidationError
from backend.app.core.serialization import serialize

MESSAGE_CONTRACT_VERSION = "v1"
DEFAULT_PAYLOAD_SCHEMA_VERSION = "v1"

_MAX_MESSAGE_TEXT_LENGTH = 256
_MAX_MESSAGE_TYPE_LENGTH = 128
_MAX_PAYLOAD_BYTES = 1_048_576
_MAX_PAYLOAD_DEPTH = 32


def _normalize_text(
    value: object,
    field_name: str,
    *,
    max_length: int = _MAX_MESSAGE_TEXT_LENGTH,
) -> str:
    """Validate and normalize a required bounded text field."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(normalized) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")

    return normalized


def _normalize_optional_text(
    value: object,
    field_name: str,
) -> str | None:
    """Validate and normalize an optional text field."""
    if value is None:
        return None

    return _normalize_text(value, field_name)


def _normalize_timestamp(value: object) -> datetime:
    """Require a timezone-aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Message timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Message timestamp must include timezone information.")

    return value.astimezone(timezone.utc)


def _validate_payload_value(
    value: object,
    *,
    depth: int = 0,
) -> None:
    """Accept bounded-depth JSON values and reject live Python objects."""
    if depth > _MAX_PAYLOAD_DEPTH:
        raise ValidationError("Message payload exceeds the maximum nesting depth.")

    if value is None or type(value) in (str, bool, int):
        return

    if type(value) is float:
        if not math.isfinite(value):
            raise ValidationError("Message payload numbers must be finite.")
        return

    if type(value) is list:
        for item in value:
            _validate_payload_value(item, depth=depth + 1)
        return

    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValidationError("Message payload dictionary keys must be strings.")

            _validate_payload_value(item, depth=depth + 1)
        return

    raise ValidationError("Message payload contains a value that is not JSON-compatible.")


def _snapshot_payload(payload: object) -> tuple[str, int]:
    """Validate and snapshot a JSON payload into deterministic JSON text."""
    if type(payload) is not dict:
        raise ValidationError("Message payload must be a dictionary.")

    _validate_payload_value(payload)

    try:
        serialized = serialize(payload)
        encoded = json.dumps(
            serialized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        size_bytes = len(encoded.encode("utf-8"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationError("Message payload could not be serialized safely.") from exc

    if size_bytes > _MAX_PAYLOAD_BYTES:
        raise ValidationError(
            f"Message payload exceeds the maximum size of {_MAX_PAYLOAD_BYTES} bytes."
        )

    return encoded, size_bytes


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True, init=False)
class Message:
    """Immutable, versioned message envelope.

    Sender identity fields are metadata, not authentication credentials.
    The communication boundary must verify them against the registered
    sender endpoint before dispatch.

    Runtime IDs scope both sender and destination instance identities.
    Correlation, causation, and operation identity have separate meanings.

    The payload is snapshotted as canonical JSON at construction.
    Accessing payload returns a fresh dictionary.

    This contract does not implement routing, authentication, retries,
    persistence, or handler execution.
    """

    message_id: str
    message_type: str
    sender_runtime_id: str
    sender_component_id: str
    sender_instance_id: str
    destination_runtime_id: str
    destination_component_id: str
    destination_instance_id: str
    correlation_id: str
    causation_id: str | None
    operation_id: str | None
    contract_version: str
    payload_schema_version: str
    created_at: datetime
    _payload_json: str = field(repr=False)
    _payload_size_bytes: int = field(repr=False)

    def __init__(
        self,
        *,
        message_type: str,
        sender_runtime_id: str,
        sender_component_id: str,
        sender_instance_id: str,
        destination_runtime_id: str,
        destination_component_id: str,
        destination_instance_id: str,
        correlation_id: str,
        payload: dict[str, Any],
        operation_id: str | None = None,
        message_id: str | None = None,
        causation_id: str | None = None,
        contract_version: str = MESSAGE_CONTRACT_VERSION,
        payload_schema_version: str = DEFAULT_PAYLOAD_SCHEMA_VERSION,
        created_at: datetime | None = None,
    ) -> None:
        """Validate and construct an immutable message envelope."""
        resolved_message_id = uuid4().hex if message_id is None else message_id

        normalized_message_id = _normalize_text(
            resolved_message_id,
            "Message ID",
        )
        normalized_message_type = _normalize_text(
            message_type,
            "Message type",
            max_length=_MAX_MESSAGE_TYPE_LENGTH,
        )
        normalized_sender_runtime_id = _normalize_text(
            sender_runtime_id,
            "Sender runtime ID",
        )
        normalized_sender_component_id = _normalize_text(
            sender_component_id,
            "Sender component ID",
        )
        normalized_sender_instance_id = _normalize_text(
            sender_instance_id,
            "Sender instance ID",
        )
        normalized_destination_runtime_id = _normalize_text(
            destination_runtime_id,
            "Destination runtime ID",
        )
        normalized_destination_component_id = _normalize_text(
            destination_component_id,
            "Destination component ID",
        )
        normalized_destination_instance_id = _normalize_text(
            destination_instance_id,
            "Destination instance ID",
        )
        normalized_correlation_id = _normalize_text(
            correlation_id,
            "Correlation ID",
        )
        normalized_causation_id = _normalize_optional_text(
            causation_id,
            "Causation ID",
        )
        normalized_operation_id = _normalize_optional_text(
            operation_id,
            "Operation ID",
        )

        if normalized_causation_id == normalized_message_id:
            raise ValidationError("A message cannot identify itself as its own cause.")

        normalized_contract_version = _normalize_text(
            contract_version,
            "Message contract version",
        )
        if normalized_contract_version != MESSAGE_CONTRACT_VERSION:
            raise ValidationError(
                f"Unsupported message contract version: {normalized_contract_version}."
            )

        normalized_payload_schema_version = _normalize_text(
            payload_schema_version,
            "Payload schema version",
        )

        timestamp = _normalize_timestamp(_utc_now() if created_at is None else created_at)
        payload_json, payload_size_bytes = _snapshot_payload(payload)

        fields = {
            "message_id": normalized_message_id,
            "message_type": normalized_message_type,
            "sender_runtime_id": normalized_sender_runtime_id,
            "sender_component_id": normalized_sender_component_id,
            "sender_instance_id": normalized_sender_instance_id,
            "destination_runtime_id": normalized_destination_runtime_id,
            "destination_component_id": normalized_destination_component_id,
            "destination_instance_id": normalized_destination_instance_id,
            "correlation_id": normalized_correlation_id,
            "causation_id": normalized_causation_id,
            "operation_id": normalized_operation_id,
            "contract_version": normalized_contract_version,
            "payload_schema_version": normalized_payload_schema_version,
            "created_at": timestamp,
            "_payload_json": payload_json,
            "_payload_size_bytes": payload_size_bytes,
        }

        for name, value in fields.items():
            object.__setattr__(self, name, value)

    @property
    def payload(self) -> dict[str, Any]:
        """Return a fresh copy of the snapshotted payload."""
        decoded = json.loads(self._payload_json)

        if not isinstance(decoded, dict):
            raise RuntimeError("Internal message payload snapshot is invalid.")

        return decoded

    @property
    def payload_json(self) -> str:
        """Return the deterministic JSON representation of the payload."""
        return self._payload_json

    @property
    def payload_size_bytes(self) -> int:
        """Return the UTF-8 size of the stored payload snapshot."""
        return self._payload_size_bytes

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly representation of this message."""
        return {
            "message_id": self.message_id,
            "message_type": self.message_type,
            "sender_runtime_id": self.sender_runtime_id,
            "sender_component_id": self.sender_component_id,
            "sender_instance_id": self.sender_instance_id,
            "destination_runtime_id": self.destination_runtime_id,
            "destination_component_id": self.destination_component_id,
            "destination_instance_id": self.destination_instance_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "operation_id": self.operation_id,
            "contract_version": self.contract_version,
            "payload_schema_version": self.payload_schema_version,
            "created_at": self.created_at,
            "payload": self.payload,
        }
