"""E0 SQLite native posting delta: actual disk journal, exact oracle and races."""
from __future__ import annotations

import sqlite3
from threading import Event, Thread

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)


def _tool(key: str, description: str = "") -> ToolSpec:
    return ToolSpec(
        name=key,
        description=description,
        source_type="research",
        license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[FieldSpec(
                name="label", semantic_id="research.label",
                json_schema={"type": "string"},
            )],
        )],
    )


def _router(registry: SQLiteRegistry) -> SchemaRouter:
    return SchemaRouter(
        registry=registry,
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("reader",),
            ),),
        ),
    )


def _seed(registry: SQLiteRegistry) -> None:
    original = _synthetic_router(12)
    registry.update_many(original.registry.tools())


@pytest.mark.parametrize("change", [
    "add", "replace", "delete", "batch", "transient",
])
def test_sqlite_journal_postings_match_canonical_full_source(
    tmp_path, change,
):
    path = tmp_path / "source.sqlite3"
    with SQLiteRegistry(path) as registry:
        _seed(registry)
        router = _router(registry)
        old = NativeSchemaPostingIndex.build(registry)
        if change == "add":
            registry.register(_tool("added"))
        elif change == "replace":
            replaced = registry.get("unrelated_00002")
            replaced.description = "new source revision"
            registry.register(replaced, replace=True)
        elif change == "delete":
            registry.unregister("unrelated_00002")
        elif change == "batch":
            registry.update_many((
                _tool("batch-added"),
                _tool("unrelated_00002", "new source"),
            ), replace=True)
        else:
            registry.register(_tool("ephemeral"))
            registry.unregister("ephemeral")
        with SQLiteRegistry(path) as cross_reader:
            receipt = cross_reader.changed_tool_keys_since(old.registry_version)
            assert receipt.to_version == registry.version
        fresh = NativeSchemaPostingIndex.build(registry)
        fast = NativeSchemaPostingIndex.refresh_from_sqlite_journal(
            old, registry,
        )
        assert fast.snapshot_id == fresh.snapshot_id
        assert fast.registry_version == fresh.registry_version
        assert fast.indexed_route_count == fresh.indexed_route_count
        assert dict(fast.route_fingerprints) == dict(fresh.route_fingerprints)
        assert dict(fast.tool_fingerprints) == dict(fresh.tool_fingerprints)
        assert dict(fast.route_locations) == dict(fresh.route_locations)
        assert dict(fast.postings) == dict(fresh.postings)
        assert dict(fast.route_semantic_ids) == dict(fresh.route_semantic_ids)
        assert fast.review_route_ids == fresh.review_route_ids
        assert dict(fast.review_cursor_anchors) == dict(fresh.review_cursor_anchors)
        assert fast.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        ) == fresh.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )


def test_sqlite_journal_only_reads_changed_tool_snapshots(tmp_path, monkeypatch):
    with SQLiteRegistry(tmp_path / "no-global-scan.sqlite3") as registry:
        _seed(registry)
        old = NativeSchemaPostingIndex.build(registry)
        registry.register(_tool("added"))
        original_get = registry.get

        def changed_only(key):
            if key != "added":
                pytest.fail("SQLite journal fast path read an unchanged ToolSpec")
            return original_get(key)

        with monkeypatch.context() as scoped:
            scoped.setattr(registry, "get", changed_only)
            scoped.setattr(
                registry, "keys",
                lambda: pytest.fail("SQLite journal scanned catalog keys"),
            )
            scoped.setattr(
                registry, "tools",
                lambda: pytest.fail("SQLite journal scanned catalog tools"),
            )
            refreshed = NativeSchemaPostingIndex.refresh_from_sqlite_journal(
                old, registry,
            )
        assert refreshed.indexed_route_count == old.indexed_route_count + 1


def test_sqlite_journal_requires_exact_source_and_new_mutation(tmp_path):
    with SQLiteRegistry(tmp_path / "first.sqlite3") as first:
        _seed(first)
        old = NativeSchemaPostingIndex.build(first)
        with pytest.raises(PolicyViolationError, match="invalid delta"):
            NativeSchemaPostingIndex.refresh_from_sqlite_journal(old, first)
        with SQLiteRegistry(tmp_path / "foreign.sqlite3") as second:
            second.register(_tool("foreign"))
            with pytest.raises(PolicyViolationError, match="source mismatch"):
                NativeSchemaPostingIndex.refresh_from_sqlite_journal(old, second)
        with pytest.raises(PolicyViolationError, match="exact in-memory"):
            NativeSchemaPostingIndex.refresh_from_inmemory_journal(old, first)


def test_sqlite_journal_rejects_missing_or_corrupted_past_receipt(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with SQLiteRegistry(path) as reg:
        _seed(reg)
        old = NativeSchemaPostingIndex.build(reg)
        reg.register(_tool("added"))
    with sqlite3.connect(path) as conn:
        conn.execute(
            "DELETE FROM schemarouter_registry_mutations WHERE version = ?",
            (old.registry_version + 1,),
        )
    with SQLiteRegistry(path) as reg:
        # Exactly the same source instance is required. Build the baseline
        # before deleting rows when testing a corrupt receipt.
        current = NativeSchemaPostingIndex.build(reg)
        reg.register(_tool("more"))
        with sqlite3.connect(path) as conn:
            conn.execute(
                "UPDATE schemarouter_registry_mutations "
                "SET changed_keys = ? WHERE version = ?",
                ('["dup","dup"]', current.registry_version + 1),
            )
        with pytest.raises(PolicyViolationError, match="full rebuild required"):
            NativeSchemaPostingIndex.refresh_from_sqlite_journal(
                current, reg,
            )


def test_sqlite_journal_concurrent_cross_connection_change_fails_closed(
    tmp_path, monkeypatch,
):
    path = tmp_path / "race.sqlite3"
    with SQLiteRegistry(path) as reg, SQLiteRegistry(path) as other:
        _seed(reg)
        old = NativeSchemaPostingIndex.build(reg)
        reg.register(_tool("added"))
        actual_get = reg.get
        injected = False

        def read_after_other_writer(key):
            nonlocal injected
            if not injected:
                injected = True
                other.register(_tool("cross-concurrent"))
            return actual_get(key)

        monkeypatch.setattr(reg, "get", read_after_other_writer)
        with pytest.raises(PolicyViolationError, match="cannot verify changed"):
            NativeSchemaPostingIndex.refresh_from_sqlite_journal(old, reg)
        assert injected


def test_sqlite_journal_legacy_history_fails_and_requires_full_rebuild(
    tmp_path,
):
    path = tmp_path / "legacy.sqlite3"
    with SQLiteRegistry(path) as reg:
        _seed(reg)
        old = NativeSchemaPostingIndex.build(reg)
        reg.register(_tool("after"))
        # Simulates a database that existed before journaling, without
        # producing fictitious records on reopening.
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TABLE schemarouter_registry_mutations")
    with SQLiteRegistry(path) as reg:
        rebuilt = NativeSchemaPostingIndex.build(reg)
        reg.register(_tool("newer"))
        with pytest.raises(PolicyViolationError, match="source mismatch"):
            NativeSchemaPostingIndex.refresh_from_sqlite_journal(old, reg)
        with pytest.raises(PolicyViolationError, match="full rebuild required"):
            NativeSchemaPostingIndex.refresh_from_sqlite_journal(
                NativeSchemaPostingIndex(
                    registry_ref=reg,
                    registry_version=old.registry_version,
                    snapshot_id=old.snapshot_id,
                    indexed_route_count=old.indexed_route_count,
                    postings=old.postings,
                    route_fingerprints=old.route_fingerprints,
                    route_locations=old.route_locations,
                    tool_fingerprints=old.tool_fingerprints,
                ),
                reg,
            )
        fresh = NativeSchemaPostingIndex.refresh_from_sqlite_journal(
            rebuilt, reg,
        )
        assert fresh.snapshot_id == NativeSchemaPostingIndex.build(reg).snapshot_id


def test_sqlite_atomic_journal_reader_snapshots_one_writer_revision(
    tmp_path, monkeypatch,
):
    """An overlapping writer must not splice a later receipt into an old read.

    File WAL is required here: a second real connection commits while the
    first read transaction is paused after pinning its logical version.
    """
    path = tmp_path / "snapshot-race.sqlite3"
    with SQLiteRegistry(path) as reader, SQLiteRegistry(path) as writer:
        writer.register(_tool("initial"))
        start_read = Event()
        writer_committed = Event()
        replies = []
        failures = []
        read_current = reader._validated_logical_version

        def pause_after_sqlite_read_version():
            current = read_current()
            start_read.set()
            if not writer_committed.wait(timeout=15):
                raise RuntimeError("concurrent SQLite writer did not commit")
            return current

        monkeypatch.setattr(reader, "_validated_logical_version",
                            pause_after_sqlite_read_version)

        def read_atomic_receipt():
            try:
                replies.append(reader.changed_tool_keys_since(0))
            except Exception as exc:
                failures.append(exc)

        thread = Thread(target=read_atomic_receipt, daemon=True)
        thread.start()
        try:
            assert start_read.wait(timeout=15)
            # Its BEGIN IMMEDIATE transaction must commit while the reader
            # holds the earlier WAL snapshot, not block on the reader lock.
            writer.register(_tool("second"))
        finally:
            writer_committed.set()
            thread.join(timeout=15)
        assert not thread.is_alive()
        assert failures == []
        assert len(replies) == 1
        assert replies[0].from_version == 0
        assert replies[0].to_version == 1
        assert replies[0].changed_tool_keys == ("initial",)
        assert writer.changed_tool_keys_since(0).to_version == 2
        assert writer.changed_tool_keys_since(0).changed_tool_keys == (
            "initial", "second",
        )
