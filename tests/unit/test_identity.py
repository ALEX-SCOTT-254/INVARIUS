"""Unit tests for the M3.1 identity domain."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from uuid import uuid4

import pytest

from backend.app.identity.models import (
    Identity,
    IdentityType,
    Principal,
    PrincipalType,
)


class TestIdentity:
    def test_creates_identity_with_valid_defaults(self) -> None:
        identity = Identity()

        assert identity.identity_id is not None
        assert isinstance(identity.identity_id, type(uuid4()))
        assert identity.identity_type == IdentityType.HUMAN
        assert identity.created_at.tzinfo is not None
        assert identity.provenance == "invarius"
        assert identity.version == 1

    def test_creates_each_supported_identity_type(self) -> None:
        for identity_type in IdentityType:
            identity = Identity(identity_type=identity_type)
            assert identity.identity_type == identity_type

    def test_rejects_non_uuid_identity_id(self) -> None:
        with pytest.raises(TypeError, match="identity_id"):
            Identity(identity_id="invalid")  # type: ignore[arg-type]

    def test_rejects_invalid_identity_type(self) -> None:
        with pytest.raises(TypeError, match="identity_type"):
            Identity(identity_type="human")  # type: ignore[arg-type]

    def test_rejects_naive_creation_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            Identity(created_at=datetime(2026, 1, 1))  # type: ignore[arg-type]

    def test_rejects_empty_provenance(self) -> None:
        with pytest.raises(ValueError, match="provenance"):
            Identity(provenance=" ")

    def test_rejects_overlong_provenance(self) -> None:
        with pytest.raises(ValueError, match="128 characters"):
            Identity(provenance="x" * 129)

    def test_rejects_non_integer_version(self) -> None:
        with pytest.raises(TypeError, match="version"):
            Identity(version=True)  # type: ignore[arg-type]

    def test_rejects_non_positive_version(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            Identity(version=0)

    def test_identity_is_immutable(self) -> None:
        identity = Identity()

        with pytest.raises(FrozenInstanceError):
            identity.version = 2  # type: ignore[misc]


class TestPrincipal:
    def test_creates_human_principal_with_identity(self) -> None:
        identity_id = uuid4()

        principal = Principal(
            principal_id=uuid4(),
            principal_type=PrincipalType.HUMAN,
            identity_id=identity_id,
        )

        assert principal.identity_id == identity_id
        assert principal.principal_type == PrincipalType.HUMAN

    @pytest.mark.parametrize(
        "principal_type",
        [
            PrincipalType.HUMAN,
            PrincipalType.SERVICE,
            PrincipalType.API_CLIENT,
        ],
    )
    def test_requires_identity_for_local_principal_types(
        self,
        principal_type: PrincipalType,
    ) -> None:
        with pytest.raises(ValueError, match="require an identity"):
            Principal(
                principal_id=uuid4(),
                principal_type=principal_type,
            )

    def test_creates_federated_principal_with_issuer(self) -> None:
        principal = Principal(
            principal_id=uuid4(),
            principal_type=PrincipalType.FEDERATED,
            issuer="trusted-provider",
        )

        assert principal.issuer == "trusted-provider"
        assert principal.identity_id is None

    def test_federated_principal_requires_issuer(self) -> None:
        with pytest.raises(ValueError, match="require an issuer"):
            Principal(
                principal_id=uuid4(),
                principal_type=PrincipalType.FEDERATED,
            )

    def test_creates_agent_principal(self) -> None:
        principal = Principal(
            principal_id=uuid4(),
            principal_type=PrincipalType.AGENT,
        )

        assert principal.principal_type == PrincipalType.AGENT

    def test_rejects_non_uuid_principal_id(self) -> None:
        with pytest.raises(TypeError, match="principal_id"):
            Principal(
                principal_id="invalid",  # type: ignore[arg-type]
                principal_type=PrincipalType.HUMAN,
                identity_id=uuid4(),
            )

    def test_rejects_invalid_principal_type(self) -> None:
        with pytest.raises(TypeError, match="principal_type"):
            Principal(
                principal_id=uuid4(),
                principal_type="human",  # type: ignore[arg-type]
                identity_id=uuid4(),
            )

    def test_rejects_non_uuid_identity_reference(self) -> None:
        with pytest.raises(TypeError, match="identity_id"):
            Principal(
                principal_id=uuid4(),
                principal_type=PrincipalType.HUMAN,
                identity_id="invalid",  # type: ignore[arg-type]
            )

    def test_rejects_empty_issuer(self) -> None:
        with pytest.raises(ValueError, match="issuer"):
            Principal(
                principal_id=uuid4(),
                principal_type=PrincipalType.FEDERATED,
                issuer=" ",
            )

    def test_rejects_overlong_issuer(self) -> None:
        with pytest.raises(ValueError, match="256 characters"):
            Principal(
                principal_id=uuid4(),
                principal_type=PrincipalType.FEDERATED,
                issuer="x" * 257,
            )

    def test_rejects_naive_creation_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            Principal(
                principal_id=uuid4(),
                principal_type=PrincipalType.HUMAN,
                identity_id=uuid4(),
                created_at=datetime(2026, 1, 1),
            )

    def test_principal_is_immutable(self) -> None:
        principal = Principal(
            principal_id=uuid4(),
            principal_type=PrincipalType.HUMAN,
            identity_id=uuid4(),
        )

        with pytest.raises(FrozenInstanceError):
            principal.issuer = "another-issuer"  # type: ignore[misc]

    def test_principal_creation_does_not_grant_authority(self) -> None:
        principal = Principal(
            principal_id=uuid4(),
            principal_type=PrincipalType.HUMAN,
            identity_id=uuid4(),
        )

        assert not hasattr(principal, "permissions")
        assert not hasattr(principal, "authenticated")
