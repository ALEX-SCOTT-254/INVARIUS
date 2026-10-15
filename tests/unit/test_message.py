"""Tests for the M2.6 immutable message contract."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.message import (
    DEFAULT_PAYLOAD_SCHEMA_VERSION,
    MESSAGE_CONTRACT_VERSION,
    Message,
)


def make_message(**overrides: object) -> Message:
    """Build a valid message with overridable contract fields."""
    values: dict[str, object] = {
        "message_type": "project.inspect",
        "sender_runtime_id": "runtime-a",
        "sender_component_id": "ingestion",
        "sender_instance_id": "ingestion-instance-a",
        "destination_runtime_id": "runtime-b",
        "destination_component_id": "language-analysis",
        "destination_instance_id": "language-analysis-instance-a",
        "correlation_id": "correlation-a",
        "payload": {"project_id": "project-a", "file_count": 3},
    }
    values.update(overrides)
    return Message(**values)  # type: ignore[arg-type]


def test_message_generates_nonempty_identity() -> None:
    message = make_message()

    assert isinstance(message.message_id, str)
    assert message.message_id.strip()


def test_each_new_message_gets_a_distinct_identity() -> None:
    first = make_message()
    second = make_message()

    assert first.message_id != second.message_id


def test_supplied_message_identity_is_preserved() -> None:
    message = make_message(message_id="message-42")

    assert message.message_id == "message-42"


def test_message_reuses_the_declared_contract_versions() -> None:
    message = make_message()

    assert message.contract_version == MESSAGE_CONTRACT_VERSION
    assert message.payload_schema_version == DEFAULT_PAYLOAD_SCHEMA_VERSION


def test_message_preserves_endpoint_and_traceability_fields() -> None:
    message = make_message(
        message_id="message-42",
        operation_id="operation-42",
        correlation_id="correlation-42",
        causation_id="message-parent",
    )

    assert message.message_id == "message-42"
    assert message.sender_runtime_id == "runtime-a"
    assert message.sender_component_id == "ingestion"
    assert message.sender_instance_id == "ingestion-instance-a"
    assert message.destination_runtime_id == "runtime-b"
    assert message.destination_component_id == "language-analysis"
    assert message.destination_instance_id == "language-analysis-instance-a"
    assert message.operation_id == "operation-42"
    assert message.correlation_id == "correlation-42"
    assert message.causation_id == "message-parent"


def test_operation_id_is_optional() -> None:
    assert make_message().operation_id is None


def test_operation_id_is_normalized() -> None:
    message = make_message(operation_id="  operation-42  ")

    assert message.operation_id == "operation-42"


def test_correlation_and_causation_are_distinct_fields() -> None:
    message = make_message(
        correlation_id="trace-100",
        causation_id="message-previous",
    )

    assert message.correlation_id == "trace-100"
    assert message.causation_id == "message-previous"
    assert message.correlation_id != message.causation_id


def test_causation_is_optional() -> None:
    assert make_message().causation_id is None


def test_message_rejects_self_causation() -> None:
    with pytest.raises(ValidationError, match="own cause"):
        make_message(
            message_id="message-self",
            causation_id="message-self",
        )


def test_message_normalizes_text_fields() -> None:
    message = make_message(
        message_id="  message-a  ",
        message_type="  project.inspect  ",
        sender_runtime_id="  runtime-a  ",
        sender_component_id="  ingestion  ",
        destination_runtime_id="  runtime-b  ",
        correlation_id="  correlation-a  ",
        operation_id="  operation-a  ",
    )

    assert message.message_id == "message-a"
    assert message.message_type == "project.inspect"
    assert message.sender_runtime_id == "runtime-a"
    assert message.sender_component_id == "ingestion"
    assert message.destination_runtime_id == "runtime-b"
    assert message.correlation_id == "correlation-a"
    assert message.operation_id == "operation-a"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("message_id", ""),
        ("message_id", "   "),
        ("message_type", ""),
        ("sender_runtime_id", " "),
        ("sender_component_id", " "),
        ("sender_instance_id", " "),
        ("destination_runtime_id", " "),
        ("destination_component_id", " "),
        ("destination_instance_id", " "),
        ("correlation_id", " "),
        ("operation_id", " "),
        ("contract_version", " "),
        ("payload_schema_version", " "),
    ],
)
def test_message_rejects_empty_required_or_provided_text(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        make_message(**{field: value})


def test_message_rejects_empty_provided_causation_id() -> None:
    with pytest.raises(ValidationError):
        make_message(causation_id="   ")


def test_message_rejects_non_string_message_type() -> None:
    with pytest.raises(ValidationError):
        make_message(message_type=42)


def test_message_rejects_unsupported_envelope_version() -> None:
    with pytest.raises(
        ValidationError,
        match="Unsupported message contract version",
    ):
        make_message(contract_version="v99")


def test_message_rejects_overlong_message_type() -> None:
    with pytest.raises(ValidationError, match="128 characters"):
        make_message(message_type="x" * 129)


def test_message_rejects_overlong_identity_text() -> None:
    with pytest.raises(ValidationError, match="256 characters"):
        make_message(correlation_id="x" * 257)


def test_message_normalizes_timestamp_to_utc() -> None:
    source_timestamp = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=timezone(timedelta(hours=3)),
    )

    message = make_message(created_at=source_timestamp)

    assert message.created_at.tzinfo is timezone.utc
    assert message.created_at.hour == 9
    assert message.created_at.minute == 0


def test_message_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone information"):
        make_message(created_at=datetime(2026, 1, 1, 12, 0))


def test_message_rejects_non_datetime_timestamp() -> None:
    with pytest.raises(ValidationError, match="must be a datetime"):
        make_message(created_at="2026-01-01T12:00:00Z")


def test_message_snapshots_the_original_payload() -> None:
    original_payload = {
        "project": {"name": "example"},
        "files": ["main.py"],
    }
    message = make_message(payload=original_payload)

    original_payload["project"]["name"] = "modified"
    original_payload["files"].append("secret.py")

    assert message.payload == {
        "project": {"name": "example"},
        "files": ["main.py"],
    }


def test_message_payload_access_returns_a_fresh_copy() -> None:
    message = make_message()
    returned_payload = message.payload

    returned_payload["project_id"] = "changed"
    returned_payload["new_field"] = True

    assert message.payload == {
        "project_id": "project-a",
        "file_count": 3,
    }


def test_message_payload_has_deterministic_json_representation() -> None:
    first = make_message(payload={"z": 3, "a": {"y": 2, "b": 1}})
    second = make_message(payload={"a": {"b": 1, "y": 2}, "z": 3})

    assert first.payload_json == second.payload_json
    assert first.payload_size_bytes == len(first.payload_json.encode("utf-8"))


def test_message_payload_rejects_non_dictionary_root() -> None:
    with pytest.raises(ValidationError, match="must be a dictionary"):
        make_message(payload=["not", "a", "dictionary"])


@pytest.mark.parametrize(
    "invalid_value",
    [
        object(),
        b"bytes",
        {1, 2, 3},
        (1, 2, 3),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    ],
)
def test_message_payload_rejects_non_json_values(
    invalid_value: object,
) -> None:
    with pytest.raises(ValidationError):
        make_message(payload={"value": invalid_value})


@pytest.mark.parametrize(
    "invalid_number",
    [float("nan"), float("inf"), float("-inf")],
)
def test_message_payload_rejects_non_finite_numbers(
    invalid_number: float,
) -> None:
    with pytest.raises(ValidationError, match="finite"):
        make_message(payload={"value": invalid_number})


def test_message_payload_rejects_non_string_dictionary_keys() -> None:
    with pytest.raises(ValidationError, match="keys must be strings"):
        make_message(payload={"valid": {1: "invalid"}})


def test_message_payload_rejects_excessive_nesting() -> None:
    nested_payload: dict[str, object] = {"value": "bottom"}

    for _ in range(35):
        nested_payload = {"nested": nested_payload}

    with pytest.raises(ValidationError, match="nesting depth"):
        make_message(payload=nested_payload)


def test_message_payload_rejects_excessive_size() -> None:
    with pytest.raises(ValidationError, match="maximum size"):
        make_message(payload={"data": "x" * 1_048_600})


def test_message_is_immutable() -> None:
    message = make_message()

    with pytest.raises(FrozenInstanceError):
        message.message_id = "changed"  # type: ignore[misc]


def test_to_dict_contains_the_public_message_contract() -> None:
    message = make_message(
        message_id="message-a",
        operation_id="operation-a",
        causation_id="message-parent",
    )

    assert message.to_dict() == {
        "message_id": "message-a",
        "message_type": "project.inspect",
        "sender_runtime_id": "runtime-a",
        "sender_component_id": "ingestion",
        "sender_instance_id": "ingestion-instance-a",
        "destination_runtime_id": "runtime-b",
        "destination_component_id": "language-analysis",
        "destination_instance_id": "language-analysis-instance-a",
        "correlation_id": "correlation-a",
        "causation_id": "message-parent",
        "operation_id": "operation-a",
        "contract_version": MESSAGE_CONTRACT_VERSION,
        "payload_schema_version": DEFAULT_PAYLOAD_SCHEMA_VERSION,
        "created_at": message.created_at,
        "payload": {"project_id": "project-a", "file_count": 3},
    }


def test_to_dict_does_not_expose_internal_payload_storage() -> None:
    result = make_message().to_dict()

    assert "_payload_json" not in result
    assert "_payload_size_bytes" not in result
