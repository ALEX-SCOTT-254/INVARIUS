"""Core identity and principal domain models.

This module deliberately separates an entity's identity from the principal
representing an actor in a security operation.

Authentication and authorization are handled by later M3 milestones.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class IdentityType(StrEnum):
    """Types of entities represented by an INVARIUS identity."""

    HUMAN = "human"
    SERVICE = "service"
    API_CLIENT = "api_client"


class PrincipalType(StrEnum):
    """Types of actors that may participate in platform operations."""

    HUMAN = "human"
    SERVICE = "service"
    API_CLIENT = "api_client"
    FEDERATED = "federated"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class Identity:
    """Stable identity record for an entity in INVARIUS."""

    identity_id: UUID = field(default_factory=uuid4)
    identity_type: IdentityType = IdentityType.HUMAN
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    provenance: str = "invarius"
    version: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.identity_id, UUID):
            raise TypeError("identity_id must be a UUID")

        if not isinstance(self.identity_type, IdentityType):
            raise TypeError("identity_type must be an IdentityType")

        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError("provenance must be a non-empty string")

        if len(self.provenance) > 128:
            raise ValueError("provenance must not exceed 128 characters")

        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise TypeError("version must be an integer")

        if self.version < 1:
            raise ValueError("version must be positive")


@dataclass(frozen=True, slots=True)
class Principal:
    """Actor reference used by security-sensitive operations.

    Creating a Principal does not authenticate it or grant authority.
    A trusted authentication boundary must establish those properties.
    """

    principal_id: UUID
    principal_type: PrincipalType
    identity_id: UUID | None = None
    issuer: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, UUID):
            raise TypeError("principal_id must be a UUID")

        if not isinstance(self.principal_type, PrincipalType):
            raise TypeError("principal_type must be a PrincipalType")

        if self.identity_id is not None and not isinstance(self.identity_id, UUID):
            raise TypeError("identity_id must be a UUID or None")

        if self.issuer is not None:
            if not isinstance(self.issuer, str) or not self.issuer.strip():
                raise ValueError("issuer must be a non-empty string when provided")

            if len(self.issuer) > 256:
                raise ValueError("issuer must not exceed 256 characters")

        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")

        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        if (
            self.principal_type
            in {
                PrincipalType.HUMAN,
                PrincipalType.SERVICE,
                PrincipalType.API_CLIENT,
            }
            and self.identity_id is None
        ):
            raise ValueError("human, service, and API client principals require an identity")

        if self.principal_type == PrincipalType.FEDERATED and self.issuer is None:
            raise ValueError("federated principals require an issuer")
