"""Tests for bounded resource admission and ownership."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.resources import (
    ResourceLease,
    ResourceLimits,
    ResourceManager,
)


def make_manager(
    *,
    operations: int = 2,
    memory: int = 1024,
) -> ResourceManager:
    """Create a resource manager with test limits."""
    return ResourceManager(
        ResourceLimits(
            max_concurrent_operations=operations,
            max_reserved_memory_bytes=memory,
        )
    )


def test_resource_limits_reject_invalid_values() -> None:
    with pytest.raises(ValidationError):
        ResourceLimits(0, 1024)

    with pytest.raises(ValidationError):
        ResourceLimits(2, 0)

    with pytest.raises(ValidationError):
        ResourceLimits(True, 1024)

    with pytest.raises(ValidationError):
        ResourceLimits(2, False)


def test_resource_manager_rejects_invalid_limits_object() -> None:
    with pytest.raises(ValidationError):
        ResourceManager(None)  # type: ignore[arg-type]


def test_acquire_and_release_updates_accounting() -> None:
    manager = make_manager()

    lease = manager.acquire(
        operation_id="operation-a",
        memory_bytes=256,
    )

    assert manager.active_operations == 1
    assert manager.reserved_memory_bytes == 256
    assert lease.operation_id == "operation-a"
    assert lease.reserved_memory_bytes == 256
    assert lease.released is False

    lease.release()

    assert manager.active_operations == 0
    assert manager.reserved_memory_bytes == 0
    assert lease.released is True


def test_resource_lease_has_unique_identity() -> None:
    manager = make_manager()

    first = manager.acquire(operation_id="operation-a")
    second = manager.acquire(operation_id="operation-b")

    assert first.lease_id != second.lease_id
    assert isinstance(first, ResourceLease)

    first.release()
    second.release()


def test_operation_id_is_normalized() -> None:
    manager = make_manager()

    lease = manager.acquire(operation_id="  operation-a  ")

    assert lease.operation_id == "operation-a"

    lease.release()


@pytest.mark.parametrize(
    "operation_id",
    [
        "",
        "   ",
        None,
        123,
        "x" * 257,
    ],
)
def test_invalid_operation_id_is_rejected(
    operation_id: object,
) -> None:
    manager = make_manager()

    with pytest.raises(ValidationError):
        manager.acquire(
            operation_id=operation_id,  # type: ignore[arg-type]
        )


def test_resource_lease_context_manager_releases() -> None:
    manager = make_manager()

    with manager.acquire(
        operation_id="operation-a",
        memory_bytes=128,
    ) as lease:
        assert manager.active_operations == 1
        assert lease.released is False

    assert manager.active_operations == 0
    assert manager.reserved_memory_bytes == 0
    assert lease.released is True


def test_context_manager_releases_when_operation_raises() -> None:
    manager = make_manager()

    with pytest.raises(RuntimeError, match="operation failed"):
        with manager.acquire(operation_id="operation-a"):
            raise RuntimeError("operation failed")

    assert manager.active_operations == 0
    assert manager.reserved_memory_bytes == 0


def test_release_twice_is_rejected() -> None:
    manager = make_manager()
    lease = manager.acquire(operation_id="operation-a")

    lease.release()

    with pytest.raises(ValidationError, match="already been released"):
        lease.release()

    assert manager.active_operations == 0
    assert manager.reserved_memory_bytes == 0


def test_released_lease_cannot_be_entered() -> None:
    manager = make_manager()
    lease = manager.acquire(operation_id="operation-a")

    lease.release()

    with pytest.raises(ValidationError, match="released"):
        lease.__enter__()


def test_memory_limit_is_enforced() -> None:
    manager = make_manager(memory=512)

    with manager.acquire(
        operation_id="operation-a",
        memory_bytes=400,
    ):
        with pytest.raises(TimeoutError):
            manager.acquire(
                operation_id="operation-b",
                memory_bytes=200,
            )

    assert manager.reserved_memory_bytes == 0


def test_single_reservation_cannot_exceed_total_memory_limit() -> None:
    manager = make_manager(memory=512)

    with pytest.raises(ValidationError):
        manager.acquire(
            operation_id="operation-a",
            memory_bytes=513,
        )


@pytest.mark.parametrize(
    "memory_bytes",
    [-1, True, 1.5, None],
)
def test_invalid_memory_reservation_is_rejected(
    memory_bytes: object,
) -> None:
    manager = make_manager()

    with pytest.raises(ValidationError):
        manager.acquire(
            operation_id="operation-a",
            memory_bytes=memory_bytes,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "timeout",
    [-1, float("inf"), float("nan"), True, None],
)
def test_invalid_acquisition_timeout_is_rejected(
    timeout: object,
) -> None:
    manager = make_manager()

    with pytest.raises(ValidationError):
        manager.acquire(
            operation_id="operation-a",
            timeout_seconds=timeout,  # type: ignore[arg-type]
        )


def test_concurrency_limit_is_enforced() -> None:
    manager = make_manager(operations=1)

    lease = manager.acquire(operation_id="operation-a")

    with pytest.raises(TimeoutError):
        manager.acquire(operation_id="operation-b")

    lease.release()

    next_lease = manager.acquire(operation_id="operation-b")
    next_lease.release()

    assert manager.active_operations == 0


def test_waiting_acquisition_succeeds_after_release() -> None:
    manager = make_manager(operations=1)
    first = manager.acquire(operation_id="operation-a")
    started = Event()

    def acquire_second() -> ResourceLease:
        started.set()

        return manager.acquire(
            operation_id="operation-b",
            timeout_seconds=1.0,
        )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(acquire_second)

        assert started.wait(timeout=1)

        first.release()
        second = future.result(timeout=2)

    assert second.operation_id == "operation-b"
    assert manager.active_operations == 1

    second.release()

    assert manager.active_operations == 0


def test_acquisition_timeout_is_bounded() -> None:
    manager = make_manager(operations=1)
    lease = manager.acquire(operation_id="operation-a")

    started_at = monotonic()

    with pytest.raises(TimeoutError):
        manager.acquire(
            operation_id="operation-b",
            timeout_seconds=0.05,
        )

    elapsed = monotonic() - started_at

    lease.release()

    assert elapsed < 1.0


def test_concurrent_acquisitions_never_exceed_limit() -> None:
    manager = make_manager(operations=3)
    barrier = Event()

    def attempt(index: int) -> ResourceLease | None:
        barrier.wait()

        try:
            return manager.acquire(
                operation_id=f"operation-{index}",
                timeout_seconds=0,
            )
        except TimeoutError:
            return None

    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = [executor.submit(attempt, index) for index in range(16)]

        barrier.set()
        leases = [future.result(timeout=2) for future in futures]

    successful_leases = [lease for lease in leases if lease is not None]

    assert len(successful_leases) == 3
    assert manager.active_operations == 3

    for lease in successful_leases:
        lease.release()

    assert manager.active_operations == 0
    assert manager.reserved_memory_bytes == 0
