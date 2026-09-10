"""Operation contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import ValidationError

OPERATION_CONTRACT_VERSION = "v1"


@dataclass(frozen=True)
class Operation:
    """Immutable description of an INVARIUS operation."""

    operation_id: str
    operation_type: str
    started_at: datetime
    contract_version: str = OPERATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate operation invariants."""

        if not isinstance(self.operation_id, str):
            raise ValidationError("Operation ID must be a string.")

        if not self.operation_id.strip():
            raise ValidationError("Operation ID cannot be empty.")

        if not isinstance(self.operation_type, str):
            raise ValidationError("Operation type must be a string.")

        if not self.operation_type.strip():
            raise ValidationError("Operation type cannot be empty.")

        if not isinstance(self.started_at, datetime):
            raise ValidationError("Operation start time must be a datetime.")

        if self.started_at.tzinfo is None:
            raise ValidationError("Operation start time must include timezone information.")

        if not isinstance(self.contract_version, str):
            raise ValidationError("Operation contract version must be a string.")

        if not self.contract_version.strip():
            raise ValidationError("Operation contract version cannot be empty.")
