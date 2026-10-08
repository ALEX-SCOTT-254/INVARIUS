"""Tests for M2.1 runtime lifecycle."""

from datetime import datetime, timezone
from threading import Barrier, Thread

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.runtime import Runtime, RuntimeState


def test_runtime_starts_in_created_state() -> None:
    created_at = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)

    runtime = Runtime("runtime-1", created_at=created_at)

    assert runtime.runtime_id == "runtime-1"
    assert runtime.created_at == created_at
    assert runtime.state == RuntimeState.CREATED
    assert runtime.revision == 0
    assert runtime.is_terminal is False
    assert len(runtime.history) == 1
    assert runtime.history[0].to_state == RuntimeState.CREATED


def test_runtime_generates_identity_when_not_supplied() -> None:
    runtime = Runtime()

    assert isinstance(runtime.runtime_id, str)
    assert runtime.runtime_id


def test_runtime_startup_path_is_revisioned() -> None:
    runtime = Runtime("runtime-1")

    starting = runtime.begin_start(at=datetime(2026, 10, 6, 10, 1, tzinfo=timezone.utc))
    running = runtime.mark_running(at=datetime(2026, 10, 6, 10, 2, tzinfo=timezone.utc))

    assert starting.revision == 1
    assert starting.from_state == RuntimeState.CREATED
    assert starting.to_state == RuntimeState.STARTING

    assert running.revision == 2
    assert running.from_state == RuntimeState.STARTING
    assert running.to_state == RuntimeState.RUNNING

    assert runtime.state == RuntimeState.RUNNING
    assert runtime.revision == 2


def test_runtime_shutdown_path_reaches_terminal_state() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()
    runtime.mark_running()

    stopping = runtime.begin_stop(at=datetime(2026, 10, 6, 10, 3, tzinfo=timezone.utc))
    stopped = runtime.mark_stopped(at=datetime(2026, 10, 6, 10, 4, tzinfo=timezone.utc))

    assert stopping.to_state == RuntimeState.STOPPING
    assert stopped.to_state == RuntimeState.STOPPED
    assert runtime.state == RuntimeState.STOPPED
    assert runtime.is_terminal is True


@pytest.mark.parametrize(
    "starting_state",
    [
        RuntimeState.STARTING,
        RuntimeState.RUNNING,
        RuntimeState.STOPPING,
    ],
)
def test_runtime_can_fail_from_active_states(
    starting_state: str,
) -> None:
    runtime = Runtime("runtime-1")

    if starting_state == RuntimeState.STARTING:
        runtime.begin_start()
    elif starting_state == RuntimeState.RUNNING:
        runtime.begin_start()
        runtime.mark_running()
    else:
        runtime.begin_start()
        runtime.mark_running()
        runtime.begin_stop()

    transition = runtime.mark_failed(reason="platform failure")

    assert transition.to_state == RuntimeState.FAILED
    assert transition.reason == "platform failure"
    assert runtime.state == RuntimeState.FAILED
    assert runtime.is_terminal is True


@pytest.mark.parametrize(
    ("action", "expected"),
    [
        ("mark_running", RuntimeState.RUNNING),
        ("begin_stop", RuntimeState.STOPPING),
        ("mark_stopped", RuntimeState.STOPPED),
        ("mark_failed", RuntimeState.FAILED),
    ],
)
def test_invalid_transitions_do_not_mutate_runtime(
    action: str,
    expected: str,
) -> None:
    runtime = Runtime("runtime-1")

    with pytest.raises(ValidationError):
        getattr(runtime, action)()

    assert runtime.state == RuntimeState.CREATED
    assert runtime.revision == 0
    assert len(runtime.history) == 1
    assert expected != runtime.state


def test_terminal_runtime_cannot_transition() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()
    runtime.mark_running()
    runtime.begin_stop()
    runtime.mark_stopped()

    with pytest.raises(ValidationError):
        runtime.begin_start()

    assert runtime.state == RuntimeState.STOPPED
    assert runtime.revision == 4


def test_failed_runtime_cannot_transition() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()
    runtime.mark_failed(reason="startup failure")

    with pytest.raises(ValidationError):
        runtime.mark_running()

    assert runtime.state == RuntimeState.FAILED
    assert runtime.revision == 2


def test_runtime_identity_remains_stable() -> None:
    runtime = Runtime("runtime-immutable")

    runtime.begin_start()
    runtime.mark_running()

    assert runtime.runtime_id == "runtime-immutable"


def test_runtime_history_is_immutable_from_public_view() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()

    history = runtime.history

    assert isinstance(history, tuple)
    assert len(history) == 2


def test_runtime_history_preserves_original_transition() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()
    original_history = runtime.history

    runtime.mark_running()

    assert len(original_history) == 2
    assert original_history[-1].to_state == RuntimeState.STARTING
    assert runtime.history[-1].to_state == RuntimeState.RUNNING


def test_naive_created_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Runtime(
            "runtime-1",
            created_at=datetime(2026, 10, 6, 10, 0),
        )


def test_naive_transition_timestamp_is_rejected() -> None:
    runtime = Runtime("runtime-1")

    with pytest.raises(ValidationError):
        runtime.begin_start(
            at=datetime(2026, 10, 6, 10, 0),
        )

    assert runtime.state == RuntimeState.CREATED
    assert runtime.revision == 0


def test_empty_runtime_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Runtime("   ")


def test_non_string_runtime_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Runtime(123)  # type: ignore[arg-type]


def test_empty_failure_reason_is_rejected() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()

    with pytest.raises(ValidationError):
        runtime.mark_failed(reason="   ")

    assert runtime.state == RuntimeState.STARTING
    assert runtime.revision == 1


def test_transition_reason_is_normalized() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()

    transition = runtime.mark_failed(reason="  startup failure  ")

    assert transition.reason == "startup failure"


def test_concurrent_transition_has_one_authoritative_winner() -> None:
    runtime = Runtime("runtime-1")
    runtime.begin_start()

    barrier = Barrier(3)
    results: list[str] = []

    def attempt_transition() -> None:
        barrier.wait()
        try:
            runtime.mark_running()
        except ValidationError:
            results.append("rejected")
        else:
            results.append("accepted")

    workers = [
        Thread(target=attempt_transition),
        Thread(target=attempt_transition),
    ]

    for worker in workers:
        worker.start()

    barrier.wait()

    for worker in workers:
        worker.join()

    assert sorted(results) == ["accepted", "rejected"]
    assert runtime.state == RuntimeState.RUNNING
    assert runtime.revision == 2
    assert len(runtime.history) == 3
