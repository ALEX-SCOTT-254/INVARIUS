"""Explicit authorization records for recovery operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from backend.app.core.errors import ValidationError
from backend.app.platform.recovery import RecoveryAttempt, RecoveryScope


class AuthorizationDecision(StrEnum):
    """Outcome recorded by an external authorization authority."""

    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class RecoveryAuthorization:
    """Immutable authorization decision bound to one recovery attempt."""

    recovery_id: str
    failure_id: str
    scope: RecoveryScope
    target_id: str
    action_id: str
    authorized_by: str
    decision: AuthorizationDecision
    decision_reason: str

    authorization_id: str = field(default_factory=lambda: uuid4().hex)
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        """Validate authorization record fields."""
        for name in (
            "authorization_id",
            "recovery_id",
            "failure_id",
            "target_id",
            "action_id",
            "authorized_by",
            "decision_reason",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{name} must be non-empty text.")
            if len(value) > 2000:
                raise ValidationError(f"{name} exceeds the maximum length.")

        if not isinstance(self.scope, RecoveryScope):
            raise ValidationError("Authorization scope must be a RecoveryScope.")

        if not isinstance(self.decision, AuthorizationDecision):
            raise ValidationError("Authorization decision must be an AuthorizationDecision.")

        if not isinstance(self.decided_at, datetime):
            raise ValidationError("Authorization timestamp must be a datetime.")

        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValidationError("Authorization timestamp must be timezone-aware.")

        object.__setattr__(
            self,
            "decided_at",
            self.decided_at.astimezone(timezone.utc),
        )

    def applies_to(self, recovery: RecoveryAttempt) -> bool:
        """Check whether this decision matches the exact attempt."""
        return (
            self.recovery_id == recovery.recovery_id
            and self.failure_id == recovery.failure.failure_id
            and self.scope is recovery.scope
            and self.target_id == recovery.target_id
            and self.action_id == recovery.action_id
        )

    def permits(self, recovery: RecoveryAttempt) -> bool:
        """Return true only for an approved, matching authorization."""
        return self.decision is AuthorizationDecision.APPROVED and self.applies_to(recovery)
