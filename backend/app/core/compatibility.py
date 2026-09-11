"""Compatibility contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError

COMPATIBILITY_CONTRACT_VERSION = "v1"


@dataclass(frozen=True)
class Compatibility:
    """Immutable assessment of contract compatibility."""

    compatible: bool
    contract_version: str
    reason: str
    compatibility_contract_version: str = COMPATIBILITY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate compatibility invariants."""

        if not isinstance(self.compatible, bool):
            raise ValidationError("Compatibility state must be a boolean.")

        if not isinstance(self.contract_version, str):
            raise ValidationError("Contract version must be a string.")

        if not self.contract_version.strip():
            raise ValidationError("Contract version cannot be empty.")

        if not isinstance(self.reason, str):
            raise ValidationError("Compatibility reason must be a string.")

        if not self.reason.strip():
            raise ValidationError("Compatibility reason cannot be empty.")

        if not isinstance(
            self.compatibility_contract_version,
            str,
        ):
            raise ValidationError("Compatibility contract version must be a string.")

        if not self.compatibility_contract_version.strip():
            raise ValidationError("Compatibility contract version cannot be empty.")
