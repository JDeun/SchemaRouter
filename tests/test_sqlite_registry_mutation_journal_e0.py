"""SQLite E0: tool mutation receipts atomically persist with the source."""
from __future__ import annotations

import sqlite3

import pytest

from schemarouter import (
    EndpointSpec,
    RegistrationError,
    SQLiteRegistry,
    ToolSpec,
)
from schemarouter.registry import RegistryMutationReceipt


def _tool(key: str, description: str = "") -> ToolSpec:
    return ToolSpec(
        name=key, description=description,
        endpoints=[EndpointSpec(name="read")],
    )


def test_sqlite_mutation_receipt_persists_across_reopen_and_reader(tmp_path):
    path = tmp_path / "registry.sqlite3"
    with SQLiteRegistry(path) as writer:
        start = writer.version
        writer.register(_tool("contact"))
        writer.register(_tool("cases"))
        assert writer.changed_tool_keys_since(start) == RegistryMutationReceipt(
            start, start + 2, ("cases", "contact"),
        )
        with SQLiteRegistry(path) as reader:
            assert reader.changed_tool_keys_since(start) == (
                writer.changed_tool_keys_since(start)
            )
            writer.unregister("contact")
            assert reader.changed_tool_keys_since(start + 2) == (
                RegistryMutationReceipt(start + 2, start + 3, ("contact",))
            )
        last_version = writer.version
    with SQLiteRegistry(path) as reopened:
        assert reopened.version == last_version
        assert reopened.changed_tool_keys_since(start) == (
            RegistryMutationReceipt(start, last_version, ("cases", "contact"))
        )


def test_sqlite_receipt_covers_cas_batch_delete_and_restore(tmp_path):
    with SQLiteRegistry(tmp_path / "cas-batch.sqlite3") as reg:
        before = _tool("existing", "old")
        after = _tool("existing", "new")
        another = _tool("added")
        reg.register(before)
        start = reg.version
        reg.replace_if_fingerprint(
            after, expected_fingerprint=before.fingerprint,
            expected_version=start,
        )
        reg.update_many((after, another), replace=True)
        reg.restore_many_if_version(
            {"existing": before, "added": None},
            expected_current={
                "existing": after.fingerprint, "added": another.fingerprint,
            },
            expected_version=reg.version,
        )
        reg.update_many_if_version(
            (another,), expected_version=reg.version,
        )
        reg.unregister_many_if_version(
            {"added": another.fingerprint}, expected_version=reg.version,
        )
        reg.unregister_if_fingerprint(
            "existing", expected_fingerprint=before.fingerprint,
            expected_version=reg.version,
        )
        assert reg.changed_tool_keys_since(start) == RegistryMutationReceipt(
            start, start + 6, ("added", "existing"),
        )
        assert reg.keys() == ()


def test_sqlite_receipt_failed_write_and_noop_never_claim_success(tmp_path):
    with SQLiteRegistry(tmp_path / "abort.sqlite3") as reg:
        old = _tool("stable")
        reg.register(old)
        start = reg.version
        reg.update_many(())
        reg.update_many_if_version((), expected_version=start)
        reg.unregister_many_if_version({}, expected_version=start)
        reg.restore_many_if_version(
            {}, expected_current={}, expected_version=start,
        )
        with pytest.raises(RegistrationError):
            reg.register(old)
        with pytest.raises(RegistrationError):
            reg.replace_if_fingerprint(
                _tool("stable", "revision"),
                expected_fingerprint="bogus",
                expected_version=start,
            )
        with pytest.raises(KeyError):
            reg.unregister("absent")
        assert reg.version == start
        assert reg.changed_tool_keys_since(start) == RegistryMutationReceipt(
            start, start, (),
        )


def test_sqlite_receipt_rolls_back_together_with_writes_on_failure(
    tmp_path, monkeypatch,
):
    with SQLiteRegistry(tmp_path / "rollback.sqlite3") as reg:
        start = reg.version
        original = reg._bump_version

        def fail_after_mutation(keys):
            original(keys)
            raise RuntimeError("injected crash after journal insert")

        monkeypatch.setattr(reg, "_bump_version", fail_after_mutation)
        with pytest.raises(RuntimeError, match="injected crash"):
            reg.register(_tool("uncommitted"))
        assert reg.version == start
        assert reg.keys() == ()
        assert reg.changed_tool_keys_since(start) == RegistryMutationReceipt(
            start, start, (),
        )


def test_sqlite_existing_catalog_has_no_invented_retroactive_receipts(tmp_path):
    path = tmp_path / "older-catalog.sqlite3"
    with SQLiteRegistry(path) as reg:
        reg.register(_tool("legacy"))
        old_version = reg.version
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE schemarouter_registry_mutations")
    with SQLiteRegistry(path) as upgraded:
        assert upgraded.version == old_version
        with pytest.raises(RegistrationError, match="missing"):
            upgraded.changed_tool_keys_since(0)
        assert upgraded.changed_tool_keys_since(old_version) == (
            RegistryMutationReceipt(old_version, old_version, ())
        )
        upgraded.register(_tool("after_upgrade"))
        assert upgraded.changed_tool_keys_since(old_version) == (
            RegistryMutationReceipt(old_version, old_version + 1,
                                    ("after_upgrade",))
        )
        with pytest.raises(RegistrationError, match="missing"):
            upgraded.changed_tool_keys_since(0)


def test_sqlite_receipt_rejects_overbudget_history_without_blocking_writes(
    tmp_path,
):
    with SQLiteRegistry(tmp_path / "limits.sqlite3") as reg:
        for bad in (True, -1, "0", 1.0, 1):
            with pytest.raises(RegistrationError, match="invalid"):
                reg.changed_tool_keys_since(bad)
        for i in range(257):
            reg.register(_tool("cycled", str(i)), replace=True)
        with pytest.raises(RegistrationError, match="expired"):
            reg.changed_tool_keys_since(0)
        assert reg.changed_tool_keys_since(reg.version) == (
            RegistryMutationReceipt(reg.version, reg.version, ())
        )
        start = reg.version
        reg.update_many(_tool(f"wide_{i}") for i in range(65))
        with pytest.raises(RegistrationError, match="invalid"):
            reg.changed_tool_keys_since(start)
        assert reg.version == start + 1
        assert len(reg.keys()) == 66


def test_sqlite_receipt_rejects_bad_on_disk_journal_content(tmp_path):
    path = tmp_path / "tampered.sqlite3"
    with SQLiteRegistry(path) as reg:
        reg.register(_tool("safe"))
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE schemarouter_registry_mutations "
            "SET changed_keys = ? WHERE version = 1",
            ('["safe","safe"]',),
        )
    with SQLiteRegistry(path) as reg:
        with pytest.raises(RegistrationError, match="invalid"):
            reg.changed_tool_keys_since(0)


def test_sqlite_receipt_cross_connection_cas_failure_keeps_committed_version(
    tmp_path,
):
    path = tmp_path / "cross-connection.sqlite3"
    with SQLiteRegistry(path) as writer, SQLiteRegistry(path) as other:
        original = _tool("source")
        writer.register(original)
        old_version = writer.version
        other.register(_tool("other"))
        with pytest.raises(RegistrationError, match="concurrently"):
            writer.replace_if_fingerprint(
                _tool("source", "lost"),
                expected_fingerprint=original.fingerprint,
                expected_version=old_version,
            )
        assert writer.version == old_version + 1
        assert writer.changed_tool_keys_since(old_version) == (
            RegistryMutationReceipt(old_version, old_version + 1, ("other",))
        )
