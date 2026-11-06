"""Unit tests for M2.10 recovery lifecycle contracts."""

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.failures import FailureCategory, FailureRecord
from backend.app.platform.recovery import (
    RecoveryAttempt,
    RecoveryScope,
    RecoveryStatus,
)
from backend.app.platform.recovery_authorization import (
    AuthorizationDecision,
    RecoveryAuthorization,
)


def make_failure() -> FailureRecord:
    return FailureRecord(
        category=FailureCategory.RUNTIME,
        source="test",
        originating_boundary="runtime",
        safe_description="Runtime failure.",
    )


def make_recovery(**overrides: object) -> RecoveryAttempt:
    values: dict[str, object] = {
        "failure": make_failure(),
        "scope": RecoveryScope.RUNTIME,
        "target_id": "runtime-1",
        "action_id": "restart-runtime",
        "authorization_context": "test-authorized-context",
    }
    values.update(overrides)
    return RecoveryAttempt(**values)


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
        "decision_reason": "Test authorization decision.",
    }
    values.update(overrides)
    return RecoveryAuthorization(**values)


def authorize(recovery: RecoveryAttempt) -> RecoveryAttempt:
    """Create and apply an approved authorization for a recovery."""
    authorization = make_authorization(recovery)
    return recovery.transition(
        RecoveryStatus.AUTHORIZED,
        authorization=authorization,
    )


def make_running() -> RecoveryAttempt:
    return authorize(make_recovery()).transition(RecoveryStatus.RUNNING)


def test_recovery_has_identity_and_explicit_scope() -> None:
    recovery = make_recovery()

    assert recovery.recovery_id
    assert recovery.scope is RecoveryScope.RUNTIME
    assert recovery.target_id == "runtime-1"
    assert recovery.status is RecoveryStatus.REQUESTED


def test_recovery_record_is_immutable() -> None:
    recovery = make_recovery()

    with pytest.raises(FrozenInstanceError):
        recovery.target_id = "runtime-2"  # type: ignore[misc]


def test_recovery_requires_failure_record() -> None:
    with pytest.raises(ValidationError, match="FailureRecord"):
        make_recovery(failure="failure")  # type: ignore[arg-type]


def test_recovery_requires_explicit_scope() -> None:
    with pytest.raises(ValidationError, match="RecoveryScope"):
        make_recovery(scope="runtime")  # type: ignore[arg-type]


def test_recovery_rejects_empty_target_and_action() -> None:
    with pytest.raises(ValidationError):
        make_recovery(target_id="")

    with pytest.raises(ValidationError):
        make_recovery(action_id="")


def test_recovery_attempt_bounds_are_validated() -> None:
    with pytest.raises(ValidationError, match="max_attempts"):
        make_recovery(max_attempts=0)

    with pytest.raises(ValidationError, match="attempt_number"):
        make_recovery(max_attempts=2, attempt_number=3)


def test_recovery_duration_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="max_duration_seconds"):
        make_recovery(max_duration_seconds=0)


def test_requested_can_be_authorized_with_approved_matching_record() -> None:
    recovery = make_recovery()
    authorization = make_authorization(recovery)

    authorized = recovery.transition(
        RecoveryStatus.AUTHORIZED,
        authorization=authorization,
    )

    assert authorized.status is RecoveryStatus.AUTHORIZED
    assert authorized.recovery_id == recovery.recovery_id
    assert authorized.authorization_id == authorization.authorization_id
    assert recovery.status is RecoveryStatus.REQUESTED


def test_authorization_is_required_for_authorized_transition() -> None:
    recovery = make_recovery()

    with pytest.raises(ValidationError, match="record is required"):
        recovery.transition(RecoveryStatus.AUTHORIZED)


def test_rejected_authorization_cannot_authorize_recovery() -> None:
    recovery = make_recovery()
    authorization = make_authorization(
        recovery,
        decision=AuthorizationDecision.REJECTED,
    )

    with pytest.raises(ValidationError, match="rejected or does not match"):
        recovery.transition(
            RecoveryStatus.AUTHORIZED,
            authorization=authorization,
        )


@pytest.mark.parametrize(
    "mismatch",
    [
        {"recovery_id": "other-recovery"},
        {"failure_id": "other-failure"},
        {"scope": RecoveryScope.OPERATION},
        {"target_id": "other-target"},
        {"action_id": "other-action"},
    ],
)
def test_mismatched_authorization_cannot_authorize_recovery(
    mismatch: dict[str, object],
) -> None:
    recovery = make_recovery()
    authorization = make_authorization(recovery, **mismatch)

    with pytest.raises(ValidationError, match="does not match"):
        recovery.transition(
            RecoveryStatus.AUTHORIZED,
            authorization=authorization,
        )


def test_authorized_lifecycle_requires_authorization_id() -> None:
    recovery = make_recovery()

    with pytest.raises(ValidationError, match="authorization ID"):
        RecoveryAttempt(
            failure=recovery.failure,
            scope=recovery.scope,
            target_id=recovery.target_id,
            action_id=recovery.action_id,
            authorization_context=recovery.authorization_context,
            status=RecoveryStatus.AUTHORIZED,
        )


def test_authorized_can_start_and_preserves_authorization_id() -> None:
    authorized = authorize(make_recovery())

    running = authorized.transition(
        RecoveryStatus.RUNNING,
        at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert running.status is RecoveryStatus.RUNNING
    assert running.started_at == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert running.authorization_id == authorized.authorization_id
    assert not running.is_terminal


def test_success_requires_verification_reference() -> None:
    running = make_running()

    with pytest.raises(ValidationError, match="verification"):
        running.transition(RecoveryStatus.SUCCEEDED)


def test_success_requires_verified_evidence_and_is_terminal() -> None:
    running = make_running()

    succeeded = running.transition(
        RecoveryStatus.SUCCEEDED,
        verification_reference="verification-123",
    )

    assert succeeded.status is RecoveryStatus.SUCCEEDED
    assert succeeded.verification_reference == "verification-123"
    assert succeeded.authorization_id == running.authorization_id
    assert succeeded.completed_at is not None
    assert succeeded.is_terminal


def test_failure_requires_reason() -> None:
    running = make_running()

    with pytest.raises(ValidationError, match="failure reason"):
        running.transition(RecoveryStatus.FAILED)


def test_failure_can_record_reason() -> None:
    running = make_running()

    failed = running.transition(
        RecoveryStatus.FAILED,
        failure_reason="Recovery action failed.",
    )

    assert failed.status is RecoveryStatus.FAILED
    assert failed.failure_reason == "Recovery action failed."
    assert failed.authorization_id == running.authorization_id
    assert failed.is_terminal


@pytest.mark.parametrize(
    "terminal_status",
    [
        RecoveryStatus.SUCCEEDED,
        RecoveryStatus.FAILED,
        RecoveryStatus.REJECTED,
        RecoveryStatus.CANCELLED,
        RecoveryStatus.UNRESOLVED,
    ],
)
def test_terminal_status_cannot_be_reopened(
    terminal_status: RecoveryStatus,
) -> None:
    if terminal_status is RecoveryStatus.SUCCEEDED:
        recovery = make_running().transition(
            RecoveryStatus.SUCCEEDED,
            verification_reference="verification",
        )
    elif terminal_status is RecoveryStatus.FAILED:
        recovery = make_running().transition(
            RecoveryStatus.FAILED,
            failure_reason="Failed.",
        )
    elif terminal_status is RecoveryStatus.REJECTED:
        recovery = make_recovery().transition(RecoveryStatus.REJECTED)
    elif terminal_status is RecoveryStatus.CANCELLED:
        recovery = make_recovery().transition(RecoveryStatus.CANCELLED)
    else:
        recovery = make_running().transition(RecoveryStatus.UNRESOLVED)

    assert recovery.status is terminal_status
    assert recovery.is_terminal

    with pytest.raises(ValidationError, match="Invalid recovery transition"):
        recovery.transition(RecoveryStatus.REQUESTED)


def test_requested_cannot_skip_authorization() -> None:
    recovery = make_recovery()

    with pytest.raises(ValidationError, match="Invalid recovery transition"):
        recovery.transition(RecoveryStatus.RUNNING)


def test_authorized_cannot_succeed_without_running() -> None:
    authorized = authorize(make_recovery())

    with pytest.raises(ValidationError, match="Invalid recovery transition"):
        authorized.transition(
            RecoveryStatus.SUCCEEDED,
            verification_reference="verification",
        )


def test_running_can_be_marked_unresolved() -> None:
    running = make_running()

    unresolved = running.transition(RecoveryStatus.UNRESOLVED)

    assert unresolved.status is RecoveryStatus.UNRESOLVED
    assert unresolved.authorization_id == running.authorization_id
    assert unresolved.is_terminal


def test_recovery_transition_rejects_naive_timestamp() -> None:
    recovery = make_recovery()

    with pytest.raises(ValidationError, match="timezone-aware"):
        recovery.transition(
            RecoveryStatus.CANCELLED,
            at=datetime(2026, 1, 1),
        )


def test_recovery_scope_is_not_inferred_from_failure_category() -> None:
    failure = make_failure()

    recovery = RecoveryAttempt(
        failure=failure,
        scope=RecoveryScope.COMPONENT_INSTANCE,
        target_id="instance-1",
        action_id="replace-instance",
        authorization_context="explicit-context",
    )

    assert recovery.scope is RecoveryScope.COMPONENT_INSTANCE
