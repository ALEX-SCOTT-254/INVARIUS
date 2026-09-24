"""Investigation contract for INVARIUS."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .errors import ValidationError
from .evidence import Evidence

INVESTIGATION_CONTRACT_VERSION = "v1"


class InvestigationStatus(StrEnum):
    """Lifecycle states for an INVARIUS investigation."""

    ACTIVE = "active"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class UnresolvedItem:
    """A structured explanation of something an investigation could not establish."""

    question: str
    reason: str
    next_step: str

    def __post_init__(self) -> None:
        """Validate unresolved-item invariants."""

        if not isinstance(self.question, str):
            raise ValidationError("Unresolved question must be a string.")

        if not self.question.strip():
            raise ValidationError("Unresolved question cannot be empty.")

        if not isinstance(self.reason, str):
            raise ValidationError("Unresolved reason must be a string.")

        if not self.reason.strip():
            raise ValidationError("Unresolved reason cannot be empty.")

        if not isinstance(self.next_step, str):
            raise ValidationError("Unresolved next step must be a string.")

        if not self.next_step.strip():
            raise ValidationError("Unresolved next step cannot be empty.")


@dataclass(frozen=True)
class Investigation:
    """Immutable record of what an investigation established and what remains unresolved."""

    investigation_id: str
    subject: str
    scope: str
    status: InvestigationStatus
    summary: str
    evidence: tuple[Evidence, ...] = ()
    unresolved: tuple[UnresolvedItem, ...] = ()
    next_steps: tuple[str, ...] = ()
    investigation_contract_version: str = INVESTIGATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        """Validate investigation invariants."""

        if not isinstance(self.investigation_id, str):
            raise ValidationError("Investigation ID must be a string.")

        if not self.investigation_id.strip():
            raise ValidationError("Investigation ID cannot be empty.")

        if not isinstance(self.subject, str):
            raise ValidationError("Investigation subject must be a string.")

        if not self.subject.strip():
            raise ValidationError("Investigation subject cannot be empty.")

        if not isinstance(self.scope, str):
            raise ValidationError("Investigation scope must be a string.")

        if not self.scope.strip():
            raise ValidationError("Investigation scope cannot be empty.")

        if not isinstance(self.status, InvestigationStatus):
            raise ValidationError("Investigation status must be a valid InvestigationStatus.")

        if not isinstance(self.summary, str):
            raise ValidationError("Investigation summary must be a string.")

        if not self.summary.strip():
            raise ValidationError("Investigation summary cannot be empty.")

        if not isinstance(self.evidence, tuple):
            raise ValidationError("Investigation evidence must be a tuple.")

        if not all(isinstance(item, Evidence) for item in self.evidence):
            raise ValidationError("Investigation evidence must contain only Evidence objects.")

        if not isinstance(self.unresolved, tuple):
            raise ValidationError("Investigation unresolved items must be a tuple.")

        if not all(isinstance(item, UnresolvedItem) for item in self.unresolved):
            raise ValidationError(
                "Investigation unresolved items must contain only UnresolvedItem objects."
            )

        if not isinstance(self.next_steps, tuple):
            raise ValidationError("Investigation next steps must be a tuple.")

        if not all(isinstance(item, str) for item in self.next_steps):
            raise ValidationError("Investigation next steps must contain only strings.")

        if not isinstance(
            self.investigation_contract_version,
            str,
        ):
            raise ValidationError("Investigation contract version must be a string.")

        if not self.investigation_contract_version.strip():
            raise ValidationError("Investigation contract version cannot be empty.")
