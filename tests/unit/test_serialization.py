from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

import pytest

from backend.app.core.errors import ValidationError
from backend.app.core.serialization import serialize


class ExampleStatus(StrEnum):
    ACTIVE = "active"


@dataclass(frozen=True)
class ExampleData:
    name: str
    value: int


def test_dataclass_serialization() -> None:
    value = ExampleData(
        name="INVARIUS",
        value=1,
    )

    assert serialize(value) == {
        "name": "INVARIUS",
        "value": 1,
    }


def test_enum_serialization() -> None:
    assert serialize(ExampleStatus.ACTIVE) == "active"


def test_nested_serialization() -> None:
    value = {
        "items": [
            ExampleStatus.ACTIVE,
            ExampleData(name="test", value=42),
        ]
    }

    assert serialize(value) == {
        "items": [
            "active",
            {
                "name": "test",
                "value": 42,
            },
        ]
    }


def test_dictionary_serialization_is_key_order_deterministic() -> None:
    first = {
        "a": 1,
        "b": 2,
        "c": 3,
    }

    second = {
        "c": 3,
        "a": 1,
        "b": 2,
    }

    assert serialize(first) == serialize(second)
    assert list(serialize(first)) == ["a", "b", "c"]


def test_json_compatible_values() -> None:
    value = {
        "string": "value",
        "integer": 42,
        "float": 3.14,
        "boolean": True,
        "null": None,
    }

    assert serialize(value) == value


def test_datetime_serialization() -> None:
    value = datetime(
        2026,
        9,
        6,
        12,
        30,
        tzinfo=timezone.utc,
    )

    assert serialize(value) == "2026-09-06T12:30:00+00:00"


def test_naive_datetime_is_rejected() -> None:
    value = datetime(2026, 9, 6, 12, 30)

    with pytest.raises(ValidationError):
        serialize(value)


def test_set_serialization_is_deterministic() -> None:
    value = {"beta", "alpha", "gamma"}

    assert serialize(value) == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_non_string_dictionary_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        serialize({1: "value"})


def test_non_finite_float_is_rejected() -> None:
    with pytest.raises(ValidationError):
        serialize(float("nan"))

    with pytest.raises(ValidationError):
        serialize(float("inf"))

    with pytest.raises(ValidationError):
        serialize(float("-inf"))


def test_unsupported_type_is_rejected() -> None:
    class Unsupported:
        pass

    with pytest.raises(ValidationError):
        serialize(Unsupported())
