"""M2.7 persistence and storage boundary for INVARIUS."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from backend.app.core.errors import InvariusError, ValidationError
from backend.app.core.serialization import serialize

STORAGE_CONTRACT_VERSION = "v1"
DEFAULT_STORAGE_SCHEMA_VERSION = "v1"

_MAX_NAMESPACE_LENGTH = 128
_MAX_RECORD_ID_LENGTH = 256
_MAX_SCHEMA_VERSION_LENGTH = 64
_MAX_PAYLOAD_BYTES = 1_048_576
_MAX_PAYLOAD_DEPTH = 32

_SQLITE_SCHEMA_VERSION = 1


class StorageError(InvariusError):
    """Base class for expected storage-boundary failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "STORAGE_ERROR",
    ) -> None:
        super().__init__(message, code=code)


class StorageConflictError(StorageError):
    """Raised when a storage write conflicts with the current record."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STORAGE_CONFLICT")


class StorageBackendError(StorageError):
    """Raised when a storage backend cannot complete an operation."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="STORAGE_BACKEND_ERROR")


def _normalize_text(
    value: object,
    field_name: str,
    *,
    max_length: int,
) -> str:
    """Validate and normalize a required bounded text field."""
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValidationError(f"{field_name} cannot be empty.")

    if len(normalized) > max_length:
        raise ValidationError(f"{field_name} cannot exceed {max_length} characters.")

    return normalized


def _normalize_revision(value: object) -> int:
    """Require a positive, non-boolean record revision."""
    if type(value) is not int or value < 1:
        raise ValidationError("Record revision must be a positive integer.")

    return value


def _normalize_timestamp(value: object) -> datetime:
    """Require a timezone-aware timestamp and normalize it to UTC."""
    if not isinstance(value, datetime):
        raise ValidationError("Storage timestamp must be a datetime.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Storage timestamp must include timezone information.")

    try:
        return value.astimezone(timezone.utc)
    except (OverflowError, ValueError) as exc:
        raise ValidationError("Storage timestamp cannot be represented in UTC.") from exc


def _utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _validate_json_value(value: object, *, depth: int = 0) -> None:
    """Validate a serialized value as bounded-depth JSON data."""
    if depth > _MAX_PAYLOAD_DEPTH:
        raise ValidationError("Storage payload exceeds the maximum nesting depth.")

    if value is None or type(value) in (str, bool, int):
        return

    if type(value) is float:
        if not math.isfinite(value):
            raise ValidationError("Storage payload numbers must be finite.")
        return

    if type(value) is list:
        for item in value:
            _validate_json_value(item, depth=depth + 1)
        return

    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValidationError("Storage payload dictionary keys must be strings.")
            _validate_json_value(item, depth=depth + 1)
        return

    raise ValidationError("Storage payload contains a value that is not JSON-compatible.")


def _encode_payload(payload: object) -> str:
    """Serialize a dictionary into a bounded canonical JSON snapshot."""
    if type(payload) is not dict:
        raise ValidationError("Storage payload must be a dictionary.")

    try:
        serialized = serialize(payload)
        _validate_json_value(serialized)

        if type(serialized) is not dict:
            raise ValidationError("Serialized storage payload must be a dictionary.")

        encoded = json.dumps(
            serialized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    except ValidationError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise ValidationError("Storage payload could not be serialized safely.") from exc

    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise ValidationError(
            f"Storage payload exceeds the maximum size of {_MAX_PAYLOAD_BYTES} bytes."
        )

    return encoded


@dataclass(frozen=True, slots=True, init=False)
class StoredRecord:
    """Immutable record returned by a storage adapter.

    Schema version describes the payload format. Record revision describes
    successive writes to the same namespace and record ID.

    Payload data is snapshotted as canonical JSON. Accessing payload
    returns a fresh dictionary.
    """

    namespace: str
    record_id: str
    schema_version: str
    revision: int
    created_at: datetime
    updated_at: datetime
    _payload_json: str = field(repr=False)

    def __init__(
        self,
        *,
        namespace: str,
        record_id: str,
        payload: dict[str, Any],
        schema_version: str = DEFAULT_STORAGE_SCHEMA_VERSION,
        revision: int = 1,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Validate and construct an immutable stored record."""
        normalized_namespace = _normalize_text(
            namespace,
            "Storage namespace",
            max_length=_MAX_NAMESPACE_LENGTH,
        )
        normalized_record_id = _normalize_text(
            record_id,
            "Storage record ID",
            max_length=_MAX_RECORD_ID_LENGTH,
        )
        normalized_schema_version = _normalize_text(
            schema_version,
            "Storage schema version",
            max_length=_MAX_SCHEMA_VERSION_LENGTH,
        )
        normalized_revision = _normalize_revision(revision)

        created_timestamp = _normalize_timestamp(
            _utc_now()
            if created_at is None and updated_at is None
            else updated_at
            if created_at is None
            else created_at
        )
        updated_timestamp = _normalize_timestamp(
            created_timestamp if updated_at is None else updated_at
        )

        if updated_timestamp < created_timestamp:
            raise ValidationError("Record updated timestamp cannot precede its creation timestamp.")

        payload_json = _encode_payload(payload)

        fields = {
            "namespace": normalized_namespace,
            "record_id": normalized_record_id,
            "schema_version": normalized_schema_version,
            "revision": normalized_revision,
            "created_at": created_timestamp,
            "updated_at": updated_timestamp,
            "_payload_json": payload_json,
        }

        for name, value in fields.items():
            object.__setattr__(self, name, value)

    @property
    def payload(self) -> dict[str, Any]:
        """Return a fresh dictionary decoded from the stored snapshot."""
        decoded = json.loads(self._payload_json)

        if not isinstance(decoded, dict):
            raise RuntimeError("Internal storage payload is invalid.")

        return decoded

    @property
    def payload_json(self) -> str:
        """Return the deterministic JSON representation of the payload."""
        return self._payload_json

    @property
    def payload_size_bytes(self) -> int:
        """Return the UTF-8 size of the payload snapshot."""
        return len(self._payload_json.encode("utf-8"))

    def to_dict(self) -> dict[str, Any]:
        """Return a serialization-friendly record representation."""
        return {
            "namespace": self.namespace,
            "record_id": self.record_id,
            "schema_version": self.schema_version,
            "revision": self.revision,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "payload": self.payload,
        }


class StoragePort(Protocol):
    """Replaceable interface for platform persistence adapters.

    A successful write creates a record or updates the exact revision
    supplied by the caller. Implementations must document their actual
    durability guarantees and report backend failures explicitly.
    """

    def read(
        self,
        namespace: str,
        record_id: str,
    ) -> StoredRecord | None:
        """Read a record, returning None when it does not exist."""
        ...

    def write(
        self,
        namespace: str,
        record_id: str,
        payload: dict[str, Any],
        *,
        schema_version: str = DEFAULT_STORAGE_SCHEMA_VERSION,
        expected_revision: int | None = None,
    ) -> StoredRecord:
        """Create a record or update an explicitly expected revision.

        With expected_revision=None, the operation is create-only.
        Otherwise, it updates only the record at that exact revision.
        """
        ...

    def delete(
        self,
        namespace: str,
        record_id: str,
        *,
        expected_revision: int,
    ) -> bool:
        """Delete a matching revision; return False if absent."""
        ...

    def close(self) -> None:
        """Release resources owned by the adapter."""
        ...


class SQLiteStorage:
    """Generic, file-backed SQLite implementation of the storage boundary.

    This adapter stores versioned JSON records without domain-specific
    CSR, evidence, investigation, or knowledge-graph tables.

    Writes use SQLite transactions and FULL synchronous mode. A successful
    write is returned only after SQLite reports a successful commit.
    Actual durability still depends on the operating system and hardware.

    A single adapter instance serializes access to its connection with a
    lock. SQLite coordinates transactions between separate connections.
    """

    def __init__(
        self,
        database_path: str | Path,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        """Open or initialize a storage database."""
        if not isinstance(database_path, (str, Path)):
            raise ValidationError("Storage database path must be a string or Path.")

        path_text = str(database_path).strip()

        if not path_text or path_text == ":memory:":
            raise ValidationError("Storage requires a non-empty file-backed database path.")

        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValidationError("Storage timeout must be a positive finite number.")

        try:
            path = Path(path_text).expanduser().resolve()
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValidationError("Storage database path is invalid.") from exc

        if not path.parent.is_dir():
            raise StorageBackendError("The storage database parent directory does not exist.")

        self._path = path
        self._lock = RLock()
        self._closed = False
        self._connection: sqlite3.Connection | None = None

        try:
            connection = sqlite3.connect(
                str(path),
                timeout=float(timeout_seconds),
                isolation_level=None,
                check_same_thread=False,
            )
            self._connection = connection
            connection.row_factory = sqlite3.Row

            connection.execute("PRAGMA foreign_keys = ON")

            current_schema = int(connection.execute("PRAGMA user_version").fetchone()[0])

            if current_schema not in (0, _SQLITE_SCHEMA_VERSION):
                raise StorageBackendError("The storage database schema version is unsupported.")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS invarius_storage_records (
                    namespace TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (namespace, record_id)
                )
                """
            )

            self._validate_existing_schema(connection)

            # Do not change persistent database settings until compatibility
            # validation has succeeded.
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")

            if current_schema == 0:
                connection.execute(f"PRAGMA user_version = {_SQLITE_SCHEMA_VERSION}")

        except StorageError:
            self._close_after_initialization_failure()
            raise
        except sqlite3.Error as exc:
            self._close_after_initialization_failure()
            raise StorageBackendError("The storage database could not be initialized.") from exc

    @staticmethod
    def _validate_existing_schema(
        connection: sqlite3.Connection,
    ) -> None:
        """Validate table structure and enforce revision bounds behaviorally.

        SQLite does not expose parsed CHECK constraints through
        ``pragma_table_list``. Instead, probe the constraint inside a savepoint
        and always roll the probe rows back. This also prevents SQL comments
        from satisfying a textual check-constraint search.
        """
        try:
            rows = connection.execute("PRAGMA table_info(invarius_storage_records)").fetchall()
            table_row = connection.execute(
                """
                SELECT sql
                FROM sqlite_master
                WHERE type = 'table' AND name = ?
                """,
                ("invarius_storage_records",),
            ).fetchone()
        except sqlite3.Error as exc:
            raise StorageBackendError("The storage table schema could not be inspected.") from exc

        expected_columns = (
            ("namespace", "TEXT", 1, 1),
            ("record_id", "TEXT", 1, 2),
            ("schema_version", "TEXT", 1, 0),
            ("revision", "INTEGER", 1, 0),
            ("payload_json", "TEXT", 1, 0),
            ("created_at", "TEXT", 1, 0),
            ("updated_at", "TEXT", 1, 0),
        )
        actual_columns = tuple(
            (
                row["name"],
                str(row["type"]).upper(),
                row["notnull"],
                row["pk"],
            )
            for row in rows
        )

        if actual_columns != expected_columns or table_row is None:
            raise StorageBackendError("The existing storage table has an incompatible schema.")

        if not isinstance(table_row["sql"], str):
            raise StorageBackendError("The storage table definition is unavailable.")

        savepoint_name = "invarius_schema_validation"
        savepoint_started = False
        insert_sql = """
            INSERT INTO invarius_storage_records (
                namespace, record_id, schema_version, revision,
                payload_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        timestamp = "2000-01-01T00:00:00.000000+00:00"

        try:
            connection.execute(f"SAVEPOINT {savepoint_name}")
            savepoint_started = True

            for revision in (1, 0, -1):
                parameters = (
                    "__invarius_schema_probe__",
                    f"__revision_{revision}__",
                    DEFAULT_STORAGE_SCHEMA_VERSION,
                    revision,
                    "{}",
                    timestamp,
                    timestamp,
                )
                try:
                    connection.execute(insert_sql, parameters)
                except sqlite3.IntegrityError as exc:
                    message = str(exc).lower()
                    if revision > 0 or (
                        "check constraint failed" not in message or "revision" not in message
                    ):
                        raise StorageBackendError(
                            "The storage table failed revision-constraint validation."
                        ) from exc
                else:
                    if revision <= 0:
                        raise StorageBackendError(
                            "The storage table lacks the required positive-revision constraint."
                        )
        except StorageError:
            raise
        except sqlite3.Error as exc:
            raise StorageBackendError(
                "The storage table revision constraint could not be validated."
            ) from exc
        finally:
            if savepoint_started:
                try:
                    connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                finally:
                    connection.execute(f"RELEASE SAVEPOINT {savepoint_name}")

    def _close_after_initialization_failure(self) -> None:
        """Close a partially initialized connection."""
        if self._connection is not None:
            try:
                self._connection.close()
            except sqlite3.Error:
                pass
            self._connection = None

    def _connection_or_raise(self) -> sqlite3.Connection:
        """Return the open connection or report a closed adapter."""
        if self._closed or self._connection is None:
            raise StorageBackendError("The storage adapter is closed.")

        return self._connection

    @staticmethod
    def _timestamp_text(value: datetime) -> str:
        """Format a UTC timestamp for deterministic storage."""
        return value.isoformat(timespec="microseconds")

    @staticmethod
    def _record_from_row(row: sqlite3.Row) -> StoredRecord:
        """Validate a database row against the public record contract."""
        try:
            payload = json.loads(row["payload_json"])
            created_at = datetime.fromisoformat(row["created_at"])
            updated_at = datetime.fromisoformat(row["updated_at"])

            return StoredRecord(
                namespace=row["namespace"],
                record_id=row["record_id"],
                schema_version=row["schema_version"],
                revision=row["revision"],
                payload=payload,
                created_at=created_at,
                updated_at=updated_at,
            )
        except StorageBackendError:
            raise
        except (
            InvariusError,
            KeyError,
            TypeError,
            ValueError,
            OverflowError,
            RecursionError,
        ) as exc:
            raise StorageBackendError(
                "A stored record failed storage-contract validation."
            ) from exc

    @staticmethod
    def _validate_key(
        namespace: str,
        record_id: str,
    ) -> tuple[str, str]:
        """Validate and normalize a record's composite identity."""
        return (
            _normalize_text(
                namespace,
                "Storage namespace",
                max_length=_MAX_NAMESPACE_LENGTH,
            ),
            _normalize_text(
                record_id,
                "Storage record ID",
                max_length=_MAX_RECORD_ID_LENGTH,
            ),
        )

    @staticmethod
    def _validate_expected_revision(
        value: object,
        *,
        allow_none: bool,
    ) -> int | None:
        """Validate an optional create-or-update revision precondition."""
        if value is None and allow_none:
            return None

        return _normalize_revision(value)

    def read(
        self,
        namespace: str,
        record_id: str,
    ) -> StoredRecord | None:
        """Read a record by namespace and record ID."""
        normalized_namespace, normalized_record_id = self._validate_key(
            namespace,
            record_id,
        )

        with self._lock:
            connection = self._connection_or_raise()

            try:
                row = connection.execute(
                    """
                    SELECT namespace, record_id, schema_version, revision,
                           payload_json, created_at, updated_at
                    FROM invarius_storage_records
                    WHERE namespace = ? AND record_id = ?
                    """,
                    (normalized_namespace, normalized_record_id),
                ).fetchone()
            except sqlite3.Error as exc:
                raise StorageBackendError("The storage read operation failed.") from exc

            if row is None:
                return None

            return self._record_from_row(row)

    def write(
        self,
        namespace: str,
        record_id: str,
        payload: dict[str, Any],
        *,
        schema_version: str = DEFAULT_STORAGE_SCHEMA_VERSION,
        expected_revision: int | None = None,
    ) -> StoredRecord:
        """Create a record or update an exact expected revision."""
        normalized_namespace, normalized_record_id = self._validate_key(
            namespace,
            record_id,
        )
        normalized_schema_version = _normalize_text(
            schema_version,
            "Storage schema version",
            max_length=_MAX_SCHEMA_VERSION_LENGTH,
        )
        normalized_expected_revision = self._validate_expected_revision(
            expected_revision,
            allow_none=True,
        )
        payload_json = _encode_payload(payload)
        payload_snapshot = json.loads(payload_json)
        now = _utc_now()

        with self._lock:
            connection = self._connection_or_raise()

            try:
                connection.execute("BEGIN IMMEDIATE")
                current_row = connection.execute(
                    """
                    SELECT namespace, record_id, schema_version, revision,
                           payload_json, created_at, updated_at
                    FROM invarius_storage_records
                    WHERE namespace = ? AND record_id = ?
                    """,
                    (normalized_namespace, normalized_record_id),
                ).fetchone()

                if normalized_expected_revision is None:
                    if current_row is not None:
                        raise StorageConflictError(
                            "The storage record already exists; creation cannot overwrite it."
                        )

                    revision = 1
                    created_at = now

                else:
                    if current_row is None:
                        raise StorageConflictError(
                            "The storage record no longer exists at the expected revision."
                        )

                    current = self._record_from_row(current_row)

                    if current.revision != normalized_expected_revision:
                        raise StorageConflictError(
                            "The storage record revision does not match the expected revision."
                        )

                    revision = current.revision + 1
                    created_at = current.created_at

                record = StoredRecord(
                    namespace=normalized_namespace,
                    record_id=normalized_record_id,
                    schema_version=normalized_schema_version,
                    revision=revision,
                    created_at=created_at,
                    updated_at=now,
                    payload=payload_snapshot,
                )

                if normalized_expected_revision is None:
                    connection.execute(
                        """
                        INSERT INTO invarius_storage_records (
                            namespace, record_id, schema_version, revision,
                            payload_json, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            record.namespace,
                            record.record_id,
                            record.schema_version,
                            record.revision,
                            record.payload_json,
                            self._timestamp_text(record.created_at),
                            self._timestamp_text(record.updated_at),
                        ),
                    )
                else:
                    cursor = connection.execute(
                        """
                        UPDATE invarius_storage_records
                        SET schema_version = ?, revision = ?, payload_json = ?,
                            updated_at = ?
                        WHERE namespace = ? AND record_id = ? AND revision = ?
                        """,
                        (
                            record.schema_version,
                            record.revision,
                            record.payload_json,
                            self._timestamp_text(record.updated_at),
                            record.namespace,
                            record.record_id,
                            normalized_expected_revision,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise StorageConflictError("The storage record changed during the update.")

                connection.execute("COMMIT")
                return record

            except StorageError:
                self._rollback_safely(connection)
                raise
            except sqlite3.Error as exc:
                self._rollback_safely(connection)
                raise StorageBackendError(
                    "The storage write failed; inspect the record before retrying."
                ) from exc
            except Exception:
                self._rollback_safely(connection)
                raise

    def delete(
        self,
        namespace: str,
        record_id: str,
        *,
        expected_revision: int,
    ) -> bool:
        """Delete a record only when its current revision matches."""
        normalized_namespace, normalized_record_id = self._validate_key(
            namespace,
            record_id,
        )
        normalized_expected_revision = _normalize_revision(expected_revision)

        with self._lock:
            connection = self._connection_or_raise()

            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT namespace, record_id, schema_version, revision,
                           payload_json, created_at, updated_at
                    FROM invarius_storage_records
                    WHERE namespace = ? AND record_id = ?
                    """,
                    (normalized_namespace, normalized_record_id),
                ).fetchone()

                if row is None:
                    connection.execute("ROLLBACK")
                    return False

                current = self._record_from_row(row)

                if current.revision != normalized_expected_revision:
                    raise StorageConflictError(
                        "The storage record revision does not match the expected deletion revision."
                    )

                cursor = connection.execute(
                    """
                    DELETE FROM invarius_storage_records
                    WHERE namespace = ? AND record_id = ? AND revision = ?
                    """,
                    (
                        normalized_namespace,
                        normalized_record_id,
                        normalized_expected_revision,
                    ),
                )

                if cursor.rowcount != 1:
                    raise StorageConflictError("The storage record changed during deletion.")

                connection.execute("COMMIT")
                return True

            except StorageError:
                self._rollback_safely(connection)
                raise
            except sqlite3.Error as exc:
                self._rollback_safely(connection)
                raise StorageBackendError("The storage delete operation failed.") from exc
            except Exception:
                self._rollback_safely(connection)
                raise

    @staticmethod
    def _rollback_safely(connection: sqlite3.Connection) -> None:
        """Roll back a failed transaction without hiding the original error."""
        try:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def close(self) -> None:
        """Close the storage connection; repeated calls are safe."""
        with self._lock:
            if self._closed:
                return

            connection = self._connection
            self._closed = True
            self._connection = None

            if connection is not None:
                try:
                    connection.close()
                except sqlite3.Error as exc:
                    raise StorageBackendError(
                        "The storage connection could not be closed cleanly."
                    ) from exc

    def __enter__(self) -> SQLiteStorage:
        """Support context-managed storage ownership."""
        with self._lock:
            self._connection_or_raise()
        return self

    def __exit__(
        self,
        exc_type: object,
        exc_value: object,
        traceback: object,
    ) -> None:
        """Close the adapter when leaving a context manager."""
        self.close()
