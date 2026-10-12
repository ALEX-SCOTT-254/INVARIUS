"""Tests for the M2.5 execution and operation-context integration."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.core.errors import InvariusError, ValidationError
from backend.app.core.evidence import Evidence, EvidenceState
from backend.app.core.operation import Operation
from backend.app.core.result import Result, ResultStatus
from backend.app.platform.component import (
    Component,
    ComponentInstance,
    ComponentInstanceState,
)
from backend.app.platform.execution import (
    ExecutionTransition,
    OperationExecution,
    OperationExecutionContext,
    OperationExecutionState,
)
from backend.app.platform.runtime import Runtime


def make_component() -> Component:
    """Build a logical component definition."""
    return Component(
        component_id="component-a",
        name="sample-component",
        contract_version="1.0",
        implementation_version="2.3",
        capabilities=frozenset({"inspect"}),
        declared_dependencies=frozenset(),
    )


def make_running_runtime(
    runtime_id: str = "runtime-a",
) -> Runtime:
    """Create a runtime in its authoritative RUNNING state."""
    runtime = Runtime(runtime_id=runtime_id)
    runtime.begin_start()
    runtime.mark_running()
    return runtime


def make_component_instance(
    runtime: Runtime,
    *,
    instance_id: str = "instance-a",
    ready: bool = True,
) -> ComponentInstance:
    """Create a component instance associated with the supplied runtime."""
    instance = ComponentInstance(
        component=make_component(),
        runtime_id=runtime.runtime_id,
        instance_id=instance_id,
    )

    if ready:
        instance.begin_start()
        instance.mark_ready()

    return instance


def make_operation(
    operation_id: str = "operation-a",
) -> Operation:
    """Create the authoritative M1.5 operation contract."""
    return Operation(
        operation_id=operation_id,
        operation_type="unit-test",
        started_at=datetime.now(timezone.utc),
    )


def make_context() -> OperationExecutionContext:
    """Create a bounded operation execution context."""
    return OperationExecutionContext(
        correlation_id="correlation-a",
        source="unit-test",
    )


def make_execution(
    *,
    runtime: Runtime | None = None,
    component_instance: ComponentInstance | None = None,
    operation: Operation | None = None,
    context: OperationExecutionContext | None = None,
) -> OperationExecution:
    """Build an execution object using the real M2.1 and M2.2 APIs."""
    resolved_runtime = make_running_runtime() if runtime is None else runtime
    resolved_instance = (
        make_component_instance(resolved_runtime)
        if component_instance is None
        else component_instance
    )

    return OperationExecution(
        operation=make_operation() if operation is None else operation,
        runtime=resolved_runtime,
        component_instance=resolved_instance,
        context=make_context() if context is None else context,
    )


def make_result(
    status: ResultStatus = ResultStatus.SUCCESS,
) -> Result:
    """Build an outcome using the existing M1.5 Result contract."""
    return Result(status=status)


def test_execution_starts_in_created_state() -> None:
    execution = make_execution()

    assert execution.state is OperationExecutionState.CREATED
    assert execution.revision == 0
    assert execution.history == ()
    assert execution.result is None


def test_execution_reuses_original_m15_operation() -> None:
    operation = make_operation()
    execution = make_execution(operation=operation)

    assert execution.operation is operation
    assert execution.operation_id == operation.operation_id


def test_execution_does_not_generate_a_competing_operation_id() -> None:
    operation = make_operation("original-operation-id")
    execution = make_execution(operation=operation)

    assert execution.operation_id == "original-operation-id"


def test_execution_captures_runtime_component_and_version_identity() -> None:
    execution = make_execution()

    assert execution.runtime_id == "runtime-a"
    assert execution.component_id == "component-a"
    assert execution.component_instance_id == "instance-a"
    assert execution.implementation_version == "2.3"


def test_execution_retains_supplied_context() -> None:
    context = OperationExecutionContext(
        correlation_id="trace-42",
        source="scheduler",
        parent_operation_id="parent-operation",
    )
    execution = make_execution(context=context)

    assert execution.context is context
    assert execution.context.correlation_id == "trace-42"
    assert execution.context.source == "scheduler"
    assert execution.context.parent_operation_id == "parent-operation"


def test_execution_start_records_transition_history() -> None:
    execution = make_execution()

    transition = execution.begin_start(" preparing ")

    assert transition.operation_id == execution.operation_id
    assert transition.revision == 1
    assert transition.from_state is OperationExecutionState.CREATED
    assert transition.to_state is OperationExecutionState.STARTING
    assert transition.reason == "preparing"
    assert transition.occurred_at.tzinfo is not None
    assert execution.state is OperationExecutionState.STARTING
    assert execution.revision == 1
    assert execution.history == (transition,)


def test_execution_can_enter_running_state() -> None:
    execution = make_execution()
    execution.begin_start()

    transition = execution.mark_running()

    assert transition.from_state is OperationExecutionState.STARTING
    assert transition.to_state is OperationExecutionState.RUNNING
    assert execution.state is OperationExecutionState.RUNNING
    assert execution.revision == 2
    assert [event.revision for event in execution.history] == [1, 2]


def test_execution_requires_running_runtime_to_start() -> None:
    runtime = Runtime(runtime_id="runtime-not-running")
    instance = make_component_instance(runtime)
    execution = make_execution(
        runtime=runtime,
        component_instance=instance,
    )

    with pytest.raises(ValidationError):
        execution.begin_start()

    assert execution.state is OperationExecutionState.CREATED
    assert execution.revision == 0
    assert execution.history == ()


def test_execution_requires_ready_component_instance_to_start() -> None:
    runtime = make_running_runtime()
    instance = make_component_instance(runtime, ready=False)
    execution = make_execution(
        runtime=runtime,
        component_instance=instance,
    )

    with pytest.raises(ValidationError):
        execution.begin_start()

    assert instance.state is ComponentInstanceState.CREATED
    assert execution.state is OperationExecutionState.CREATED
    assert execution.revision == 0


def test_execution_cannot_enter_running_directly_from_created() -> None:
    execution = make_execution()

    with pytest.raises(ValidationError):
        execution.mark_running()

    assert execution.state is OperationExecutionState.CREATED
    assert execution.history == ()


def test_execution_rejects_component_instance_from_another_runtime() -> None:
    runtime = make_running_runtime("runtime-a")
    other_runtime = make_running_runtime("runtime-b")
    instance = make_component_instance(other_runtime)

    with pytest.raises(ValidationError):
        make_execution(
            runtime=runtime,
            component_instance=instance,
        )


def test_execution_rejects_non_operation_contract() -> None:
    runtime = make_running_runtime()
    instance = make_component_instance(runtime)

    with pytest.raises(ValidationError):
        OperationExecution(
            operation=object(),  # type: ignore[arg-type]
            runtime=runtime,
            component_instance=instance,
            context=make_context(),
        )


def test_execution_rejects_non_runtime_object() -> None:
    runtime = make_running_runtime()
    instance = make_component_instance(runtime)

    with pytest.raises(ValidationError):
        OperationExecution(
            operation=make_operation(),
            runtime=object(),  # type: ignore[arg-type]
            component_instance=instance,
            context=make_context(),
        )


def test_execution_rejects_non_component_instance() -> None:
    runtime = make_running_runtime()

    with pytest.raises(ValidationError):
        OperationExecution(
            operation=make_operation(),
            runtime=runtime,
            component_instance=object(),  # type: ignore[arg-type]
            context=make_context(),
        )


def test_execution_rejects_invalid_context_type() -> None:
    runtime = make_running_runtime()
    instance = make_component_instance(runtime)

    with pytest.raises(ValidationError):
        OperationExecution(
            operation=make_operation(),
            runtime=runtime,
            component_instance=instance,
            context=object(),  # type: ignore[arg-type]
        )


def test_completed_execution_preserves_original_result() -> None:
    execution = make_execution()
    execution.begin_start()
    execution.mark_running()
    result = make_result()

    execution.mark_completed(result)

    assert execution.state is OperationExecutionState.COMPLETED
    assert execution.result is result
    assert execution.result.status is ResultStatus.SUCCESS


@pytest.mark.parametrize(
    "status",
    [
        ResultStatus.SUCCESS,
        ResultStatus.PARTIAL,
        ResultStatus.FAILURE,
        ResultStatus.UNRESOLVED,
    ],
)
def test_execution_lifecycle_does_not_override_result_status(
    status: ResultStatus,
) -> None:
    execution = make_execution()
    result = make_result(status)

    execution.mark_completed(result)

    assert execution.state is OperationExecutionState.COMPLETED
    assert execution.result is result
    assert execution.result.status is status


def test_execution_reuses_existing_evidence_and_error_contracts() -> None:
    evidence = Evidence.now(
        state=EvidenceState.FACT,
        statement="The operation returned a failure.",
        source="unit-test",
        confidence=1.0,
    )
    error = InvariusError(
        "Operation failed.",
        code="TEST_FAILURE",
    )
    result = Result(
        status=ResultStatus.FAILURE,
        evidence=(evidence,),
        errors=(error,),
    )
    execution = make_execution()

    execution.mark_completed(result)

    assert execution.result is result
    assert execution.result.evidence == (evidence,)
    assert execution.result.evidence[0] is evidence
    assert execution.result.errors == (error,)
    assert execution.result.errors[0] is error


def test_completion_rejects_non_result_without_mutation() -> None:
    execution = make_execution()

    with pytest.raises(ValidationError):
        execution.mark_completed("success")  # type: ignore[arg-type]

    assert execution.state is OperationExecutionState.CREATED
    assert execution.result is None
    assert execution.revision == 0
    assert execution.history == ()


def test_cancellation_request_is_not_confirmed_cancellation() -> None:
    execution = make_execution()
    execution.begin_start()
    execution.mark_running()

    execution.request_cancel(" user requested ")

    assert execution.state is OperationExecutionState.CANCEL_REQUESTED
    assert execution.result is None
    assert execution.history[-1].reason == "user requested"


def test_cancellation_must_be_requested_before_confirmation() -> None:
    execution = make_execution()

    with pytest.raises(ValidationError):
        execution.mark_cancelled()

    assert execution.state is OperationExecutionState.CREATED
    assert execution.history == ()


def test_requested_cancellation_can_be_confirmed() -> None:
    execution = make_execution()
    execution.begin_start()
    execution.mark_running()
    execution.request_cancel()

    execution.mark_cancelled(" cancellation confirmed ")

    assert execution.state is OperationExecutionState.CANCELLED
    assert execution.history[-1].reason == "cancellation confirmed"
    assert execution.result is None


def test_interruption_does_not_invent_a_result() -> None:
    execution = make_execution()
    execution.begin_start()
    execution.mark_running()

    execution.mark_interrupted("runtime ended unexpectedly")

    assert execution.state is OperationExecutionState.INTERRUPTED
    assert execution.result is None
    assert execution.history[-1].reason == "runtime ended unexpectedly"


@pytest.mark.parametrize(
    "terminal_state",
    [
        OperationExecutionState.COMPLETED,
        OperationExecutionState.CANCELLED,
        OperationExecutionState.INTERRUPTED,
    ],
)
def test_terminal_execution_cannot_transition_again(
    terminal_state: OperationExecutionState,
) -> None:
    execution = make_execution()

    if terminal_state is OperationExecutionState.COMPLETED:
        execution.mark_completed(make_result())
    elif terminal_state is OperationExecutionState.CANCELLED:
        execution.request_cancel()
        execution.mark_cancelled()
    else:
        execution.mark_interrupted()

    previous_state = execution.state
    previous_revision = execution.revision
    previous_history = execution.history

    with pytest.raises(ValidationError):
        execution.begin_start()

    assert execution.state is previous_state
    assert execution.revision == previous_revision
    assert execution.history == previous_history


def test_invalid_transition_does_not_mutate_execution() -> None:
    execution = make_execution()

    with pytest.raises(ValidationError):
        execution.mark_running()

    assert execution.state is OperationExecutionState.CREATED
    assert execution.revision == 0
    assert execution.history == ()


def test_execution_history_is_an_immutable_snapshot() -> None:
    execution = make_execution()
    execution.begin_start()

    earlier_history = execution.history

    execution.mark_running()

    assert len(earlier_history) == 1
    assert len(execution.history) == 2


def test_execution_transition_is_immutable() -> None:
    execution = make_execution()
    transition = execution.begin_start()

    with pytest.raises(FrozenInstanceError):
        transition.revision = 99  # type: ignore[misc]


def test_execution_transition_normalizes_timestamp_to_utc() -> None:
    offset = timezone(timedelta(hours=3))
    timestamp = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=offset,
    )

    transition = ExecutionTransition(
        operation_id="operation-a",
        revision=1,
        from_state=OperationExecutionState.CREATED,
        to_state=OperationExecutionState.STARTING,
        occurred_at=timestamp,
    )

    assert transition.occurred_at.utcoffset() == timedelta(0)
    assert transition.occurred_at.hour == 9


def test_execution_transition_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ExecutionTransition(
            operation_id="operation-a",
            revision=1,
            from_state=OperationExecutionState.CREATED,
            to_state=OperationExecutionState.STARTING,
            occurred_at=datetime(2026, 1, 1),
        )


@pytest.mark.parametrize("revision", [0, -1, True, 1.5])
def test_execution_transition_rejects_invalid_revision(
    revision: object,
) -> None:
    with pytest.raises(ValidationError):
        ExecutionTransition(
            operation_id="operation-a",
            revision=revision,  # type: ignore[arg-type]
            from_state=OperationExecutionState.CREATED,
            to_state=OperationExecutionState.STARTING,
            occurred_at=datetime.now(timezone.utc),
        )


def test_execution_transition_rejects_empty_operation_id() -> None:
    with pytest.raises(ValidationError):
        ExecutionTransition(
            operation_id="   ",
            revision=1,
            from_state=OperationExecutionState.CREATED,
            to_state=OperationExecutionState.STARTING,
            occurred_at=datetime.now(timezone.utc),
        )


def test_execution_context_normalizes_text_fields() -> None:
    context = OperationExecutionContext(
        correlation_id="  correlation-a  ",
        source="  test-suite  ",
        parent_operation_id="  parent-operation  ",
    )

    assert context.correlation_id == "correlation-a"
    assert context.source == "test-suite"
    assert context.parent_operation_id == "parent-operation"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"correlation_id": " "},
        {"source": " "},
        {"parent_operation_id": " "},
    ],
)
def test_execution_context_rejects_empty_required_or_provided_text(
    kwargs: dict[str, str],
) -> None:
    values = {
        "correlation_id": "correlation-a",
        "source": "unit-test",
    }
    values.update(kwargs)

    with pytest.raises(ValidationError):
        OperationExecutionContext(**values)


def test_execution_context_is_immutable() -> None:
    context = make_context()

    with pytest.raises(FrozenInstanceError):
        context.source = "changed"  # type: ignore[misc]


def test_concurrent_running_transition_has_one_winner() -> None:
    execution = make_execution()
    execution.begin_start()

    def attempt_transition(_: int) -> bool:
        try:
            execution.mark_running()
        except ValidationError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(attempt_transition, range(64)))

    assert sum(results) == 1
    assert execution.state is OperationExecutionState.RUNNING
    assert execution.revision == 2
    assert len(execution.history) == 2
