"""Bounded resource admission and ownership for INVARIUS platform operations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from threading import Condition
from time import monotonic
from uuid import uuid4

from backend.app.core.errors import ValidationError

_MAX_OPERATION_ID_LENGTH = 256


def _validate_positive_integer(value: object, field_name: str) -> int:
    """Validate a strictly positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError(f"{field_name} must be a positive integer.")

    return value


def _validate_non_negative_integer(value: object, field_name: str) -> int:
    """Validate a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"{field_name} must be a non-negative integer.")

    return value


def _validate_timeout(value: object) -> float:
    """Validate a finite, non-negative acquisition timeout."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError("Acquisition timeout must be a number.")

    timeout = float(value)

    if not math.isfinite(timeout) or timeout < 0:
        raise ValidationError("Acquisition timeout must be finite and non-negative.")

    return timeout


def _validate_operation_id(value: object) -> str:
    """Validate and normalize an operation identity."""
    if not isinstance(value, str):
        raise ValidationError("Operation ID must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError("Operation ID cannot be empty.")

    if len(normalized) > _MAX_OPERATION_ID_LENGTH:
        raise ValidationError("Operation ID exceeds the maximum length.")

    return normalized


@dataclass(frozen=True, slots=True)
class ResourceLimits:
    """Immutable limits for a resource manager."""

    max_concurrent_operations: int
    max_reserved_memory_bytes: int

    def __post_init__(self) -> None:
        """Validate configured resource limits."""
        _validate_positive_integer(
            self.max_concurrent_operations,
            "Maximum concurrent operations",
        )

        _validate_positive_integer(
            self.max_reserved_memory_bytes,
            "Maximum reserved memory",
        )


class ResourceLease:
    """A resource reservation owned by one operation."""

    def __init__(
        self,
        *,
        manager: ResourceManager,
        lease_id: str,
        operation_id: str,
        reserved_memory_bytes: int,
    ) -> None:
        """Create a lease managed by ResourceManager."""
        self._manager = manager
        self._lease_id = lease_id
        self._operation_id = operation_id
        self._reserved_memory_bytes = reserved_memory_bytes
        self._released = False

    @property
    def lease_id(self) -> str:
        """Return the unique lease identity."""
        return self._lease_id

    @property
    def operation_id(self) -> str:
        """Return the operation owning this lease."""
        return self._operation_id

    @property
    def reserved_memory_bytes(self) -> int:
        """Return the memory reservation associated with this lease."""
        return self._reserved_memory_bytes

    @property
    def released(self) -> bool:
        """Return whether the lease has been released."""
        with self._manager._condition:
            return self._released

    def release(self) -> None:
        """Release this lease exactly once."""
        self._manager._release(self)

    def __enter__(self) -> ResourceLease:
        """Return the lease for context-manager use."""
        if self.released:
            raise ValidationError("Cannot enter a released resource lease.")

        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        """Release resources when leaving a context."""
        self.release()


class ResourceManager:
    """Thread-safe bounded resource admission manager.

    Memory values represent reservations, not measured process memory or
    hard operating-system memory enforcement.
    """

    def __init__(self, limits: ResourceLimits) -> None:
        """Initialize resource accounting."""
        if not isinstance(limits, ResourceLimits):
            raise ValidationError("Resource manager requires ResourceLimits.")

        self._limits = limits
        self._condition = Condition()
        self._active_leases: dict[str, ResourceLease] = {}
        self._active_operations = 0
        self._reserved_memory_bytes = 0

    @property
    def limits(self) -> ResourceLimits:
        """Return immutable resource limits."""
        return self._limits

    @property
    def active_operations(self) -> int:
        """Return the number of active leases."""
        with self._condition:
            return self._active_operations

    @property
    def reserved_memory_bytes(self) -> int:
        """Return the current reserved-memory total."""
        with self._condition:
            return self._reserved_memory_bytes

    def acquire(
        self,
        *,
        operation_id: str,
        memory_bytes: int = 0,
        timeout_seconds: float = 0,
    ) -> ResourceLease:
        """Acquire a bounded operation and memory reservation.

        Acquisition waits only up to timeout_seconds. A timeout of zero
        means immediate admission or rejection.
        """
        normalized_operation_id = _validate_operation_id(operation_id)

        normalized_memory = _validate_non_negative_integer(
            memory_bytes,
            "Memory reservation",
        )

        timeout = _validate_timeout(timeout_seconds)

        if normalized_memory > self._limits.max_reserved_memory_bytes:
            raise ValidationError("Memory reservation exceeds the configured resource limit.")

        deadline = monotonic() + timeout

        with self._condition:
            while not self._has_capacity(normalized_memory):
                remaining = deadline - monotonic()

                if remaining <= 0:
                    raise TimeoutError("Resource acquisition timed out.")

                self._condition.wait(timeout=remaining)

            lease_id = uuid4().hex

            lease = ResourceLease(
                manager=self,
                lease_id=lease_id,
                operation_id=normalized_operation_id,
                reserved_memory_bytes=normalized_memory,
            )

            self._active_leases[lease_id] = lease
            self._active_operations += 1
            self._reserved_memory_bytes += normalized_memory

            return lease

    def _has_capacity(self, memory_bytes: int) -> bool:
        """Check admission capacity while holding the condition lock."""
        return (
            self._active_operations < self._limits.max_concurrent_operations
            and self._reserved_memory_bytes + memory_bytes <= self._limits.max_reserved_memory_bytes
        )

    def _release(self, lease: ResourceLease) -> None:
        """Release an active lease and notify waiting acquisitions."""
        with self._condition:
            if not isinstance(lease, ResourceLease):
                raise ValidationError("Invalid resource lease.")

            if lease._manager is not self:
                raise ValidationError("Resource lease is not owned by this manager.")

            if lease._released:
                raise ValidationError("Resource lease has already been released.")

            active = self._active_leases.get(lease.lease_id)

            if active is not lease:
                raise ValidationError("Resource lease is not owned by this manager.")

            self._active_operations -= 1
            self._reserved_memory_bytes -= lease.reserved_memory_bytes
            lease._released = True

            del self._active_leases[lease.lease_id]

            if self._active_operations < 0 or self._reserved_memory_bytes < 0:
                raise RuntimeError("Resource accounting invariant violated.")

            self._condition.notify_all()
