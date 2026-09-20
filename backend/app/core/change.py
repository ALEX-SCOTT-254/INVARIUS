"""Change contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import ValidationError

CHANGE_CONTRACT_VERSION = "v1"


class ChangeType(StrEnum):
    """Supported categories of system change."""

    SOURCE = "source"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    BUILD = "build"
    RUNTIME = "runtime"
    INFRASTRUCTURE = "infrastructure"
    DATA = "data"
    SCHEMA = "schema"
    SECURITY = "security"
    ENVIRONMENT = "environment"
    DEPLOYMENT = "deployment"
    EXTERNAL_SERVICE = "external_service"
    MIXED = "mixed"
    OTHER = "other"


@dataclass(frozen=True)
class ChangeContract:
    """Immutable description of a controlled system change."""

    change_id: str
    change_type: ChangeType
    source_version: str
    target_version: str
    reason: str
    change_contract_version: str = CHANGE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate change contract invariants."""

        if not isinstance(self.change_id, str):
            raise ValidationError("Change ID must be a string.")

        if not self.change_id.strip():
            raise ValidationError("Change ID cannot be empty.")

        if not isinstance(self.change_type, ChangeType):
            raise ValidationError("Change type must be a valid ChangeType.")

        if not isinstance(self.source_version, str):
            raise ValidationError("Source version must be a string.")

        if not self.source_version.strip():
            raise ValidationError("Source version cannot be empty.")

        if not isinstance(self.target_version, str):
            raise ValidationError("Target version must be a string.")

        if not self.target_version.strip():
            raise ValidationError("Target version cannot be empty.")

        if not isinstance(self.reason, str):
            raise ValidationError("Change reason must be a string.")

        if not self.reason.strip():
            raise ValidationError("Change reason cannot be empty.")

        if not isinstance(
            self.change_contract_version,
            str,
        ):
            raise ValidationError("Change contract version must be a string.")

        if not self.change_contract_version.strip():
            raise ValidationError("Change contract version cannot be empty.")
