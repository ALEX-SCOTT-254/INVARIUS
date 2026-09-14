"""Migration contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError

MIGRATION_CONTRACT_VERSION = "v1"


@dataclass(frozen=True)
class Migration:
    """Immutable description of a version transition."""

    source_version: str
    target_version: str
    reason: str
    migration_contract_version: str = MIGRATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate migration invariants."""

        if not isinstance(self.source_version, str):
            raise ValidationError("Source version must be a string.")

        if not self.source_version.strip():
            raise ValidationError("Source version cannot be empty.")

        if not isinstance(self.target_version, str):
            raise ValidationError("Target version must be a string.")

        if not self.target_version.strip():
            raise ValidationError("Target version cannot be empty.")

        if not isinstance(self.reason, str):
            raise ValidationError("Migration reason must be a string.")

        if not self.reason.strip():
            raise ValidationError("Migration reason cannot be empty.")

        if not isinstance(
            self.migration_contract_version,
            str,
        ):
            raise ValidationError("Migration contract version must be a string.")

        if not self.migration_contract_version.strip():
            raise ValidationError("Migration contract version cannot be empty.")
