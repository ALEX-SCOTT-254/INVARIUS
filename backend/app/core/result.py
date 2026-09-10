"""Result contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from .errors import InvariusError, ValidationError
from .evidence import Evidence

RESULT_CONTRACT_VERSION = "v1"


class ResultStatus(StrEnum):
    """Outcome states for an INVARIUS operation."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Result:
    """Immutable outcome of an INVARIUS operation."""

    status: ResultStatus
    value: Any = None
    evidence: tuple[Evidence, ...] = ()
    errors: tuple[InvariusError, ...] = ()
    contract_version: str = RESULT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate result invariants."""

        if not isinstance(self.status, ResultStatus):
            raise ValidationError("Result status must be a valid ResultStatus.")

        if not isinstance(self.evidence, tuple):
            raise ValidationError("Result evidence must be a tuple.")

        if not all(isinstance(item, Evidence) for item in self.evidence):
            raise ValidationError("Result evidence must contain only Evidence objects.")

        if not isinstance(self.errors, tuple):
            raise ValidationError("Result errors must be a tuple.")

        if not all(isinstance(item, InvariusError) for item in self.errors):
            raise ValidationError("Result errors must contain only INVARIUS errors.")

        if not isinstance(self.contract_version, str):
            raise ValidationError("Result contract version must be a string.")

        if not self.contract_version.strip():
            raise ValidationError("Result contract version cannot be empty.")
