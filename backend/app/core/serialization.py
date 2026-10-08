"""Serialization utilities for INVARIUS."""

from __future__ import annotations

import math
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Any

from .errors import ValidationError


def serialize(value: Any) -> Any:
    """Convert a supported Python value into a deterministic JSON structure."""

    if is_dataclass(value) and not isinstance(value, type):
        return serialize(asdict(value))

    if isinstance(value, Enum):
        return serialize(value.value)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValidationError("Datetime values must include timezone information.")

        return value.isoformat()

    if isinstance(value, (date, time)):
        return value.isoformat()

    if isinstance(value, dict):
        serialized: dict[str, Any] = {}

        for key in sorted(value):
            if not isinstance(key, str):
                raise ValidationError("Dictionary keys must be strings for serialization.")

            serialized[key] = serialize(value[key])

        return serialized

    if isinstance(value, (list, tuple)):
        return [serialize(item) for item in value]

    if isinstance(value, set):
        serialized_items = [serialize(item) for item in value]

        return sorted(
            serialized_items,
            key=lambda item: repr(item),
        )

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValidationError("Float values must be finite for serialization.")

        return value

    if isinstance(value, str) or value is None:
        return value

    raise ValidationError(f"Unsupported value type for serialization: {type(value).__name__}")
