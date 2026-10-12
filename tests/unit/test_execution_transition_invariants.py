"""Adversarial tests for execution-transition integrity."""

from datetime import datetime, timezone

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.execution import (
    ExecutionTransition,
    OperationExecutionState,
)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (
            OperationExecutionState.CREATED,
            OperationExecutionState.RUNNING,
        ),
        (
            OperationExecutionState.STARTING,
            OperationExecutionState.CANCELLED,
        ),
        (
            OperationExecutionState.CANCEL_REQUESTED,
            OperationExecutionState.RUNNING,
        ),
        (
            OperationExecutionState.COMPLETED,
            OperationExecutionState.INTERRUPTED,
        ),
        (
            OperationExecutionState.CANCELLED,
            OperationExecutionState.COMPLETED,
        ),
        (
            OperationExecutionState.INTERRUPTED,
            OperationExecutionState.RUNNING,
        ),
    ],
)
def test_transition_record_rejects_disallowed_state_changes(
    from_state: OperationExecutionState,
    to_state: OperationExecutionState,
) -> None:
    """A standalone transition record must obey the lifecycle contract."""
    with pytest.raises(ValidationError, match="Invalid execution transition"):
        ExecutionTransition(
            operation_id="operation-a",
            revision=1,
            from_state=from_state,
            to_state=to_state,
            occurred_at=datetime.now(timezone.utc),
        )


def test_transition_record_accepts_a_permitted_state_change() -> None:
    """A legitimate transition remains constructible and immutable."""
    transition = ExecutionTransition(
        operation_id="operation-a",
        revision=1,
        from_state=OperationExecutionState.CREATED,
        to_state=OperationExecutionState.STARTING,
        occurred_at=datetime.now(timezone.utc),
    )

    assert transition.from_state is OperationExecutionState.CREATED
    assert transition.to_state is OperationExecutionState.STARTING
    assert transition.revision == 1
