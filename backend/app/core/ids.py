"""Canonical identifier utilities for INVARIUS."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from enum import StrEnum

from .errors import ValidationError

CANONICAL_ID_VERSION = "v1"


class IdentifierType(StrEnum):
    """Supported canonical identifier types."""

    PROJECT = "project"
    FILE = "file"
    MODULE = "module"
    SYMBOL = "symbol"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    TEST = "test"
    EVIDENCE = "evidence"
    RELATIONSHIP = "relationship"


def _normalize_value(value: str) -> str:
    """Normalize a value according to the v1 identity rules."""

    if not isinstance(value, str):
        raise ValidationError("Identifier value must be a string.")

    normalized = unicodedata.normalize("NFC", value).strip()

    if not normalized:
        raise ValidationError("Identifier value cannot be empty.")

    return normalized


def canonical_id(
    identifier_type: IdentifierType,
    value: str,
) -> str:
    """Create a deterministic, versioned canonical identifier."""

    if not isinstance(identifier_type, IdentifierType):
        raise ValidationError("Identifier type must be a valid IdentifierType.")

    normalized = _normalize_value(value)

    identity_material = f"{CANONICAL_ID_VERSION}|{identifier_type.value}|{normalized}"

    digest = hashlib.sha256(identity_material.encode("utf-8")).hexdigest()

    return f"{CANONICAL_ID_VERSION}:{identifier_type.value}:{digest}"


def is_valid_canonical_id(value: str) -> bool:
    """Return whether a value matches the canonical ID format."""

    pattern = (
        r"^v1:"
        r"[a-z]+:"
        r"[0-9a-f]{64}$"
    )

    return bool(re.fullmatch(pattern, value))
