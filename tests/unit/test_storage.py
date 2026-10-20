"""Unit tests for the M2.7 persistence and storage boundary."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.app.core.errors import ValidationError
from backend.app.platform.storage import (
    DEFAULT_STORAGE_SCHEMA_VERSION,
    SQLiteStorage,
    StorageBackendError,
    StorageConflictError,
    StoredRecord,
)


@pytest.fixture
def database_path(tmp_path):
    """Return a file-backed database path in a temporary directory."""
    return tmp_path / "invarius-storage.db"


@pytest.fixture
def storage(database_path):
    """Provide an open storage adapter and close it after each test."""
    adapter = SQLiteStorage(database_path)
    try:
        yield adapter
    finally:
        adapter.close()


def test_write_and_read_record(storage):
    payload = {"name": "INVARIUS", "count": 3, "enabled": True}

    written = storage.write("projects", "project-1", payload)
    read = storage.read("projects", "project-1")

    assert read == written
    assert read is not None
    assert read.namespace == "projects"
    assert read.record_id == "project-1"
    assert read.schema_version == DEFAULT_STORAGE_SCHEMA_VERSION
    assert read.revision == 1
    assert read.payload == payload
    assert read.created_at.tzinfo is not None
    assert read.updated_at.tzinfo is not None


def test_read_missing_record_returns_none(storage):
    assert storage.read("projects", "missing") is None


def test_records_are_isolated_by_namespace(storage):
    storage.write("projects", "same-id", {"value": "project"})
    storage.write("evidence", "same-id", {"value": "evidence"})

    assert storage.read("projects", "same-id").payload == {"value": "project"}
    assert storage.read("evidence", "same-id").payload == {"value": "evidence"}


def test_create_only_write_cannot_overwrite_existing_record(storage):
    original = storage.write("projects", "p1", {"value": 1})

    with pytest.raises(StorageConflictError):
        storage.write("projects", "p1", {"value": 2})

    assert storage.read("projects", "p1") == original


def test_update_increments_revision_and_preserves_creation_time(storage):
    original = storage.write("projects", "p1", {"value": 1})

    updated = storage.write(
        "projects",
        "p1",
        {"value": 2},
        expected_revision=original.revision,
    )

    assert updated.revision == original.revision + 1
    assert updated.created_at == original.created_at
    assert updated.updated_at >= original.updated_at
    assert updated.payload == {"value": 2}


def test_update_requires_existing_record(storage):
    with pytest.raises(StorageConflictError):
        storage.write(
            "projects",
            "missing",
            {"value": 1},
            expected_revision=1,
        )


def test_update_rejects_stale_revision_without_changing_record(storage):
    original = storage.write("projects", "p1", {"value": 1})

    with pytest.raises(StorageConflictError):
        storage.write(
            "projects",
            "p1",
            {"value": 2},
            expected_revision=original.revision + 1,
        )

    assert storage.read("projects", "p1") == original


def test_delete_missing_record_returns_false(storage):
    assert storage.delete("projects", "missing", expected_revision=1) is False


def test_delete_requires_matching_revision(storage):
    original = storage.write("projects", "p1", {"value": 1})

    with pytest.raises(StorageConflictError):
        storage.delete(
            "projects",
            "p1",
            expected_revision=original.revision + 1,
        )

    assert storage.read("projects", "p1") == original


def test_delete_matching_revision_removes_record(storage):
    original = storage.write("projects", "p1", {"value": 1})

    assert (
        storage.delete(
            "projects",
            "p1",
            expected_revision=original.revision,
        )
        is True
    )
    assert storage.read("projects", "p1") is None


def test_data_survives_adapter_reopen(database_path):
    first = SQLiteStorage(database_path)
    first.write("projects", "p1", {"value": "persistent"})
    first.close()

    second = SQLiteStorage(database_path)
    try:
        record = second.read("projects", "p1")
        assert record is not None
        assert record.payload == {"value": "persistent"}
        assert record.revision == 1
    finally:
        second.close()


def test_payload_serialization_is_deterministic(storage):
    first = storage.write(
        "projects",
        "first",
        {"z": 1, "a": {"y": 2, "b": 3}},
    )
    second = storage.write(
        "projects",
        "second",
        {"a": {"b": 3, "y": 2}, "z": 1},
    )

    assert first.payload_json == second.payload_json
    assert first.payload_json == '{"a":{"b":3,"y":2},"z":1}'


def test_payload_access_returns_a_fresh_dictionary(storage):
    storage.write("projects", "p1", {"nested": {"value": 1}})

    first_read = storage.read("projects", "p1")
    assert first_read is not None

    exposed_payload = first_read.payload
    exposed_payload["nested"]["value"] = 99
    exposed_payload["new_key"] = True

    second_read = storage.read("projects", "p1")
    assert second_read is not None
    assert second_read.payload == {"nested": {"value": 1}}


def test_custom_schema_version_is_preserved(storage):
    record = storage.write(
        "projects",
        "p1",
        {"value": 1},
        schema_version="schema-v2",
    )

    assert record.schema_version == "schema-v2"
    assert storage.read("projects", "p1").schema_version == "schema-v2"


@pytest.mark.parametrize(
    ("namespace", "record_id"),
    [
        ("", "p1"),
        ("   ", "p1"),
        ("projects", ""),
        ("projects", "   "),
        (None, "p1"),
        ("projects", None),
        ("x" * 129, "p1"),
        ("projects", "x" * 257),
    ],
)
def test_invalid_record_keys_are_rejected(storage, namespace, record_id):
    with pytest.raises(ValidationError):
        storage.read(namespace, record_id)


@pytest.mark.parametrize("revision", [0, -1, True, 1.5, "1"])
def test_invalid_expected_revisions_are_rejected(storage, revision):
    with pytest.raises(ValidationError):
        storage.write(
            "projects",
            "p1",
            {"value": 1},
            expected_revision=revision,
        )


def test_non_dictionary_payload_is_rejected(storage):
    with pytest.raises(ValidationError):
        storage.write("projects", "p1", ["not", "a", "dictionary"])


def test_non_json_payload_value_is_rejected(storage):
    with pytest.raises(ValidationError):
        storage.write("projects", "p1", {"value": object()})


@pytest.mark.parametrize("number", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_numbers_are_rejected(storage, number):
    with pytest.raises(ValidationError):
        storage.write("projects", "p1", {"value": number})


def test_oversized_payload_is_rejected(storage):
    with pytest.raises(ValidationError):
        storage.write("projects", "p1", {"value": "x" * 1_100_000})


def test_excessively_nested_payload_is_rejected(storage):
    nested = {"value": "leaf"}
    for _ in range(34):
        nested = {"child": nested}

    with pytest.raises(ValidationError):
        storage.write("projects", "p1", nested)


def test_invalid_database_path_is_rejected():
    with pytest.raises(ValidationError):
        SQLiteStorage("")

    with pytest.raises(ValidationError):
        SQLiteStorage(":memory:")


@pytest.mark.parametrize("timeout", [0, -1, True, float("nan"), float("inf")])
def test_invalid_timeout_is_rejected(tmp_path, timeout):
    with pytest.raises(ValidationError):
        SQLiteStorage(tmp_path / "invalid-timeout.db", timeout_seconds=timeout)


def test_missing_database_parent_is_reported(tmp_path):
    with pytest.raises(StorageBackendError):
        SQLiteStorage(tmp_path / "missing-directory" / "storage.db")


def test_unsupported_database_schema_version_is_rejected(database_path):
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA user_version = 999")
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(StorageBackendError):
        SQLiteStorage(database_path)


def test_corrupt_persisted_payload_is_reported(database_path):
    adapter = SQLiteStorage(database_path)
    adapter.write("projects", "p1", {"value": 1})
    adapter.close()

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            UPDATE invarius_storage_records
            SET payload_json = ?
            WHERE namespace = ? AND record_id = ?
            """,
            ("{invalid-json", "projects", "p1"),
        )
        connection.commit()
    finally:
        connection.close()

    reopened = SQLiteStorage(database_path)
    try:
        with pytest.raises(StorageBackendError):
            reopened.read("projects", "p1")
    finally:
        reopened.close()


def test_operations_after_close_raise_backend_error(database_path):
    adapter = SQLiteStorage(database_path)
    adapter.close()
    adapter.close()  # Closing repeatedly is documented as safe.

    with pytest.raises(StorageBackendError):
        adapter.read("projects", "p1")

    with pytest.raises(StorageBackendError):
        adapter.write("projects", "p1", {"value": 1})

    with pytest.raises(StorageBackendError):
        adapter.delete("projects", "p1", expected_revision=1)


def test_context_manager_closes_adapter(database_path):
    with SQLiteStorage(database_path) as adapter:
        adapter.write("projects", "p1", {"value": 1})

    with pytest.raises(StorageBackendError):
        adapter.read("projects", "p1")


def test_stored_record_normalizes_timestamps_to_utc():
    non_utc = timezone(timedelta(hours=3))
    created = datetime(2026, 1, 1, 12, 0, tzinfo=non_utc)
    updated = created + timedelta(minutes=1)

    record = StoredRecord(
        namespace="projects",
        record_id="p1",
        payload={"value": 1},
        created_at=created,
        updated_at=updated,
    )

    assert record.created_at.utcoffset() == timedelta(0)
    assert record.updated_at.utcoffset() == timedelta(0)


def test_stored_record_rejects_naive_timestamps():
    naive = datetime(2026, 1, 1)

    with pytest.raises(ValidationError):
        StoredRecord(
            namespace="projects",
            record_id="p1",
            payload={},
            created_at=naive,
        )


def test_stored_record_rejects_update_before_creation():
    created = datetime(2026, 1, 2, tzinfo=timezone.utc)
    updated = created - timedelta(seconds=1)

    with pytest.raises(ValidationError):
        StoredRecord(
            namespace="projects",
            record_id="p1",
            payload={},
            created_at=created,
            updated_at=updated,
        )


def test_record_payload_json_is_valid_canonical_json():
    record = StoredRecord(
        namespace="projects",
        record_id="p1",
        payload={"z": 2, "a": 1},
    )

    assert json.loads(record.payload_json) == {"a": 1, "z": 2}
    assert record.payload_size_bytes == len(record.payload_json.encode("utf-8"))


def test_malformed_existing_table_schema_is_rejected(
    tmp_path: Path,
) -> None:
    """Reject an existing storage table with an incompatible structure."""
    database_path = tmp_path / "malformed_schema.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE invarius_storage_records (
                wrong_column TEXT
            )
            """
        )

    with pytest.raises(StorageBackendError):
        SQLiteStorage(database_path)

    with sqlite3.connect(database_path) as connection:
        columns = connection.execute("PRAGMA table_info(invarius_storage_records)").fetchall()

    assert [column[1] for column in columns] == ["wrong_column"]


def test_incompatible_schema_rejection_preserves_journal_mode(
    tmp_path: Path,
) -> None:
    """Reject an incompatible schema without changing its journal mode."""
    database_path = tmp_path / "incompatible_journal_mode.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE invarius_storage_records (
                wrong_column TEXT
            )
            """
        )
        initial_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    with pytest.raises(StorageBackendError):
        SQLiteStorage(database_path)

    with sqlite3.connect(database_path) as connection:
        final_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

    assert final_mode == initial_mode == "delete"


def test_revision_constraint_in_sql_comment_is_rejected(
    tmp_path: Path,
) -> None:
    """A comment mentioning CHECK must not substitute for a real constraint."""
    database_path = tmp_path / "comment_only_constraint.db"

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE invarius_storage_records (
                namespace TEXT NOT NULL,
                record_id TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                revision INTEGER NOT NULL, -- CHECK (REVISION >= 1)
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (namespace, record_id)
            )
            """
        )

    with pytest.raises(StorageBackendError):
        SQLiteStorage(database_path)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(
            "SELECT namespace, record_id FROM invarius_storage_records"
        ).fetchall()

    assert rows == []
