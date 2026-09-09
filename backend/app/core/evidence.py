"""Evidence model for INVARIUS."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum

from .errors import ValidationError


class EvidenceState(StrEnum):
    """State describing the epistemic status of evidence."""

    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    UNRESOLVED = "unresolved"
    CONFLICT = "conflict"
    STALE = "stale"


@dataclass(frozen=True)
class Evidence:
    """A traceable piece of information used by INVARIUS."""

    state: EvidenceState
    statement: str
    source: str
    confidence: float
    observed_at: datetime

    def __post_init__(self) -> None:
        """Validate evidence invariants."""

        if not isinstance(self.state, EvidenceState):
            raise ValidationError("Evidence state must be a valid EvidenceState.")

        if not isinstance(self.statement, str):
            raise ValidationError("Evidence statement must be a string.")

        if not self.statement.strip():
            raise ValidationError("Evidence statement cannot be empty.")

        if not isinstance(self.source, str):
            raise ValidationError("Evidence source must be a string.")

        if not self.source.strip():
            raise ValidationError("Evidence source cannot be empty.")

        if isinstance(self.confidence, bool) or not isinstance(
            self.confidence,
            (int, float),
        ):
            raise ValidationError("Evidence confidence must be a number.")

        if not math.isfinite(float(self.confidence)):
            raise ValidationError("Evidence confidence must be finite.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("Evidence confidence must be between 0.0 and 1.0.")

        if not isinstance(self.observed_at, datetime):
            raise ValidationError("Evidence timestamp must be a datetime.")

        if self.observed_at.tzinfo is None:
            raise ValidationError("Evidence timestamp must include timezone information.")

    @classmethod
    def now(
        cls,
        *,
        state: EvidenceState,
        statement: str,
        source: str,
        confidence: float,
    ) -> "Evidence":
        """Create evidence using the current UTC timestamp."""

        return cls(
            state=state,
            statement=statement,
            source=source,
            confidence=confidence,
            observed_at=datetime.now(timezone.utc),
        )
