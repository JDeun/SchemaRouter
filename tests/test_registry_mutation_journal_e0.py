"""E0: source-owned, lock-atomic bounded in-memory mutation receipts.

No document payload, credentials, graph result, model or source executor.
"""
from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    InMemoryRegistry,
    RegistrationError,
    SQLiteRegistry,
    ToolSpec,
)
from schemarouter.registry import RegistryMutationReceipt


def _tool(name: str, description: str = "") -> ToolSpec:
    return ToolSpec(
        name=name,
        description=description,
        endpoints=[EndpointSpec(name="read")],
    )


def test_atomic_registry_journal_records_add_replace_delete_and_cas():
    registry = InMemoryRegistry()
    assert registry.changed_tool_keys_since(0) == RegistryMutationReceipt(0, 0, ())
    original = _tool("case", "before")
    replacement = _tool("case", "after")
    registry.register(original)
    assert registry.changed_tool_keys_since(0) == RegistryMutationReceipt(
        0, 1, ("case",),
    )
    registry.replace_if_fingerprint(
        replacement,
        expected_fingerprint=original.fingerprint,
        expected_version=1,
    )
    assert registry.changed_tool_keys_since(1) == RegistryMutationReceipt(
        1, 2, ("case",),
    )
    registry.unregister_if_fingerprint(
        "case",
        expected_fingerprint=replacement.fingerprint,
        expected_version=2,
    )
    assert registry.changed_tool_keys_since(2) == RegistryMutationReceipt(
        2, 3, ("case",),
    )
    registry.register(original)
    registry.unregister("case")
    assert registry.changed_tool_keys_since(3) == RegistryMutationReceipt(
        3, 5, ("case",),
    )


def test_atomic_registry_journal_reports_batch_and_rollback_as_single_versions():
    registry = InMemoryRegistry()
    old = _tool("existing", "old")
    new = _tool("existing", "new")
    added = _tool("added")
    registry.register(old)
    start = registry.version
    registry.update_many((new, added), replace=True)
    assert registry.changed_tool_keys_since(start) == RegistryMutationReceipt(
        start, start + 1, ("added", "existing"),
    )
    registry.restore_many_if_version(
        {"existing": old, "added": None},
        expected_current={"existing": new.fingerprint, "added": added.fingerprint},
        expected_version=registry.version,
    )
    assert registry.changed_tool_keys_since(start + 1) == RegistryMutationReceipt(
        start + 1, start + 2, ("added", "existing"),
    )
    registry.update_many_if_version(
        (added,), expected_version=registry.version,
    )
    assert registry.changed_tool_keys_since(start + 2).changed_tool_keys == (
        "added",
    )
    registry.unregister_many_if_version(
        {"added": added.fingerprint}, expected_version=registry.version,
    )
    assert registry.changed_tool_keys_since(start + 3).changed_tool_keys == (
        "added",
    )


def test_atomic_registry_journal_no_op_and_failed_mutation_never_bump_receipt():
    registry = InMemoryRegistry()
    registry.register(_tool("stable"))
    version = registry.version
    registry.update_many(())
    registry.update_many_if_version((), expected_version=version)
    registry.unregister_many_if_version({}, expected_version=version)
    registry.restore_many_if_version(
        {}, expected_current={}, expected_version=version,
    )
    with pytest.raises(RegistrationError):
        registry.register(_tool("stable"))
    with pytest.raises(RegistrationError):
        registry.replace_if_fingerprint(
            _tool("stable", "new"),
            expected_fingerprint="invalid",
            expected_version=version,
        )
    with pytest.raises(RegistrationError):
        registry.update_many_if_version(
            (_tool("stable", "new"),), expected_version=version - 1,
            replace=True,
        )
    with pytest.raises(KeyError):
        registry.unregister("not-present")
    assert registry.version == version
    assert registry.changed_tool_keys_since(version) == RegistryMutationReceipt(
        version, version, (),
    )


def test_atomic_registry_journal_rejects_invalid_expired_and_large_cursors():
    registry = InMemoryRegistry()
    for bad in (True, -1, 1, 1.0, "0"):
        with pytest.raises(RegistrationError, match="invalid"):
            registry.changed_tool_keys_since(bad)
    for i in range(257):
        registry.register(_tool(f"case_{i % 3}", str(i)), replace=True)
    with pytest.raises(RegistrationError, match="expired"):
        registry.changed_tool_keys_since(0)
    assert registry.changed_tool_keys_since(registry.version) == (
        RegistryMutationReceipt(registry.version, registry.version, ())
    )
    before_many = registry.version
    for i in range(65):
        registry.register(_tool(f"wide_{i}"))
    with pytest.raises(RegistrationError, match="safe bound"):
        registry.changed_tool_keys_since(before_many)


def test_atomic_registry_journal_limits_returned_data_to_version_and_keys():
    registry = InMemoryRegistry()
    registry.register(_tool("source", "private source payload 123"))
    receipt = registry.changed_tool_keys_since(0)
    assert receipt.changed_tool_keys == ("source",)
    assert "private source payload" not in repr(receipt)
    with pytest.raises(AttributeError):
        receipt.changed_tool_keys = ("forged",)


def test_sqlite_registry_has_separate_persistent_mutation_receipts(tmp_path):
    """SQLite journal is distinct from in-memory-only posting fast path."""
    with SQLiteRegistry(tmp_path / "journal-positive.sqlite3") as registry:
        assert registry.changed_tool_keys_since(0) == RegistryMutationReceipt(
            0, 0, (),
        )
