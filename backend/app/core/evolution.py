"""Evolution contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass

from .compatibility import Compatibility
from .errors import ValidationError
from .migration import Migration

EVOLUTION_CONTRACT_VERSION = "v1"


@dataclass(frozen=True)
class Evolution:
    """Immutable description of a controlled system evolution."""

    evolution_id: str
    subject: str
    source_version: str
    target_version: str
    reason: str
    compatibility: Compatibility
    migration: Migration
    evolution_contract_version: str = EVOLUTION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate evolution invariants."""

        if not isinstance(self.evolution_id, str):
            raise ValidationError("Evolution ID must be a string.")

        if not self.evolution_id.strip():
            raise ValidationError("Evolution ID cannot be empty.")

        if not isinstance(self.subject, str):
            raise ValidationError("Evolution subject must be a string.")

        if not self.subject.strip():
            raise ValidationError("Evolution subject cannot be empty.")

        if not isinstance(self.source_version, str):
            raise ValidationError("Source version must be a string.")

        if not self.source_version.strip():
            raise ValidationError("Source version cannot be empty.")

        if not isinstance(self.target_version, str):
            raise ValidationError("Target version must be a string.")

        if not self.target_version.strip():
            raise ValidationError("Target version cannot be empty.")

        if not isinstance(self.reason, str):
            raise ValidationError("Evolution reason must be a string.")

        if not self.reason.strip():
            raise ValidationError("Evolution reason cannot be empty.")

        if not isinstance(self.compatibility, Compatibility):
            raise ValidationError("Evolution compatibility must be a valid Compatibility object.")

        if not isinstance(self.migration, Migration):
            raise ValidationError("Evolution migration must be a valid Migration object.")

        if not isinstance(
            self.evolution_contract_version,
            str,
        ):
            raise ValidationError("Evolution contract version must be a string.")

        if not self.evolution_contract_version.strip():
            raise ValidationError("Evolution contract version cannot be empty.")
