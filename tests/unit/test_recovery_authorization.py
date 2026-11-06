"""Tests for explicit recovery authorization."""

from dataclasses import FrozenInstanceError

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.failures import FailureCategory, FailureRecord
from backend.app.platform.recovery import RecoveryAttempt, RecoveryScope
from backend.app.platform.recovery_authorization import (
    AuthorizationDecision,
    RecoveryAuthorization,
)


def make_recovery() -> RecoveryAttempt:
    failure = FailureRecord(
        category=FailureCategory.RUNTIME,
        source="test",
        originating_boundary="runtime",
        safe_description="Runtime failure.",
    )
    return RecoveryAttempt(
        failure=failure,
        scope=RecoveryScope.RUNTIME,
        target_id="runtime-1",
        action_id="restart",
        authorization_context="authorization-pending",
    )


def make_authorization(
    recovery: RecoveryAttempt,
    *,
    decision: AuthorizationDecision = AuthorizationDecision.APPROVED,
    **overrides: object,
) -> RecoveryAuthorization:
    values: dict[str, object] = {
        "recovery_id": recovery.recovery_id,
        "failure_id": recovery.failure.failure_id,
        "scope": recovery.scope,
        "target_id": recovery.target_id,
        "action_id": recovery.action_id,
        "authorized_by": "test-authority",
        "decision": decision,
        "decision_reason": "Test decision.",
    }
    values.update(overrides)
    return RecoveryAuthorization(**values)


def test_approved_authorization_permits_matching_attempt() -> None:
    recovery = make_recovery()
    authorization = make_authorization(recovery)

    assert authorization.applies_to(recovery)
    assert authorization.permits(recovery)


def test_rejected_authorization_does_not_permit_attempt() -> None:
    recovery = make_recovery()
    authorization = make_authorization(
        recovery,
        decision=AuthorizationDecision.REJECTED,
    )

    assert authorization.applies_to(recovery)
    assert not authorization.permits(recovery)


@pytest.mark.parametrize(
    "field_name",
    ["recovery_id", "failure_id", "target_id", "action_id"],
)
def test_authorization_must_match_attempt_identity(field_name: str) -> None:
    recovery = make_recovery()
    authorization = make_authorization(
        recovery,
        **{field_name: "different-identity"},
    )

    assert not authorization.applies_to(recovery)
    assert not authorization.permits(recovery)


def test_authorization_scope_must_match() -> None:
    recovery = make_recovery()
    authorization = make_authorization(
        recovery,
        scope=RecoveryScope.OPERATION,
    )

    assert not authorization.applies_to(recovery)
    assert not authorization.permits(recovery)


def test_authorization_is_immutable() -> None:
    authorization = make_authorization(make_recovery())

    with pytest.raises(FrozenInstanceError):
        authorization.authorized_by = "changed"  # type: ignore[misc]


def test_authorization_rejects_empty_authority() -> None:
    recovery = make_recovery()

    with pytest.raises(ValidationError, match="authorized_by"):
        make_authorization(recovery, authorized_by="")


def test_authorization_rejects_naive_timestamp() -> None:
    from datetime import datetime

    recovery = make_recovery()

    with pytest.raises(ValidationError, match="timezone-aware"):
        make_authorization(
            recovery,
            decided_at=datetime(2026, 1, 1),
        )
