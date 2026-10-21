"""E0 SQLite native graph journal delta: typed oracle, policy and source races."""
from __future__ import annotations

import sqlite3

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.benchmark_indexed_native_graph_g5_cpu_e0 import (
    GROUP,
    PRINCIPAL,
    QUERY,
    _synthetic_router,
)


def _tool(key: str) -> ToolSpec:
    return ToolSpec(
        name=key, source_type="research", license="host-reviewed-synthetic",
        endpoints=[EndpointSpec(
            name="read", read_only=True, output_fields=[
                FieldSpec(name="label", semantic_id="research.label",
                          json_schema={"type": "string"}),
            ],
        )],
    )


def _seed(reg: SQLiteRegistry, count: int = 16) -> SchemaRouter:
    reference = _synthetic_router(count)
    reg.update_many(reference.registry.tools())
    return SchemaRouter(
        registry=reg,
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("reader",),
            ),),
        ),
    )


def _full(reg: SQLiteRegistry) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(reg))


def _change_consumer(reg: SQLiteRegistry, field_type: str) -> None:
    changed = reg.get("case_service")
    endpoint = changed.endpoint("read")
    endpoint.parameters[0].json_schema = {"type": field_type}
    endpoint.input_schema = {
        "type": "object",
        "properties": {"customer_id": {"type": field_type}},
        "required": ["customer_id"],
    }
    reg.register(changed, replace=True)


@pytest.mark.parametrize("change", (
    "add", "replace_incompatible", "replace_compatible",
    "delete", "batch", "transient",
))
def test_sqlite_g5_journal_graph_exact_full_oracle_and_scoped_query(
    tmp_path, change,
):
    with SQLiteRegistry(tmp_path / "graph-source.sqlite3") as reg:
        router = _seed(reg)
        original = _full(reg)
        if change == "add":
            reg.register(_tool("added"))
        elif change == "replace_incompatible":
            _change_consumer(reg, "integer")
        elif change == "replace_compatible":
            _change_consumer(reg, "integer")
            _change_consumer(reg, "string")
        elif change == "delete":
            reg.unregister("unrelated_00002")
        elif change == "batch":
            reg.update_many((_tool("batch-added"), _tool("unrelated_00002")),
                            replace=True)
        else:
            reg.register(_tool("transient"))
            reg.unregister("transient")
        new = NativeSchemaGraphIndex.refresh_from_sqlite_journal(original, reg)
        full = _full(reg)
        assert new.field_index.registry_version == full.field_index.registry_version
        assert new.field_index.snapshot_id == full.field_index.snapshot_id
        assert dict(new.field_index.postings) == dict(full.field_index.postings)
        assert dict(new.field_index.route_fingerprints) == dict(
            full.field_index.route_fingerprints
        )
        assert dict(new.field_index.tool_fingerprints) == dict(
            full.field_index.tool_fingerprints
        )
        assert new.graph.capability_ids == full.graph.capability_ids
        assert new.graph.edges == full.graph.edges
        assert new.native_root_count == full.native_root_count
        assert new.native_consumer_count == full.native_consumer_count
        assert new.edge_consumer_routes == full.edge_consumer_routes
        for principal in (
            PRINCIPAL,
            PrincipalContext(subject="denied", roles=("visitor",)),
        ):
            observed = new.lookup(router, QUERY, group=GROUP, principal=principal)
            assert observed == full.lookup(
                router, QUERY, group=GROUP, principal=principal,
            )
            if principal == PRINCIPAL:
                assert observed.qualified_path_count == (
                    0 if change == "replace_incompatible" else 1
                )
            else:
                assert observed.qualified_path_count == 0


def test_sqlite_g5_journal_graph_never_scans_unchanged_source(
    tmp_path, monkeypatch,
):
    with SQLiteRegistry(tmp_path / "no-global-source-scan.sqlite3") as reg:
        _seed(reg, count=125)
        old = _full(reg)
        _change_consumer(reg, "integer")
        get = reg.get

        def changed_only(key):
            if key != "case_service":
                pytest.fail("SQLite G5 journal delta read unchanged native tool")
            return get(key)

        with monkeypatch.context() as scoped:
            scoped.setattr(reg, "get", changed_only)
            scoped.setattr(
                reg, "keys",
                lambda: pytest.fail("SQLite journal graph walked global source keys"),
            )
            scoped.setattr(
                reg, "tools",
                lambda: pytest.fail("SQLite journal graph scanned native tool list"),
            )
            updated = NativeSchemaGraphIndex.refresh_from_sqlite_journal(old, reg)
        assert updated.graph.edges == ()
        assert updated.field_index.registry_version == reg.version


def test_sqlite_g5_journal_graph_fails_closed_wrong_source_and_no_change(tmp_path):
    with SQLiteRegistry(tmp_path / "one.sqlite3") as reg:
        _seed(reg)
        previous = _full(reg)
        with pytest.raises(PolicyViolationError, match="invalid versioned changes"):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(previous, reg)
        with SQLiteRegistry(tmp_path / "foreign.sqlite3") as foreign:
            foreign.register(_tool("foreign"))
            with pytest.raises(PolicyViolationError, match="source mismatch"):
                NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                    previous, foreign,
                )
        with pytest.raises(PolicyViolationError, match="exact SQLite"):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                previous, _synthetic_router(1).registry,
            )


def test_sqlite_g5_graph_refuses_missing_source_receipt(tmp_path):
    path = tmp_path / "missing-source-receipt.sqlite3"
    with SQLiteRegistry(path) as reg:
        _seed(reg)
        previous = _full(reg)
        reg.register(_tool("added"))
        with sqlite3.connect(path) as outside:
            outside.execute(
                "DELETE FROM schemarouter_registry_mutations WHERE version = ?",
                (reg.version,),
            )
        with pytest.raises(PolicyViolationError, match="full build required"):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(previous, reg)


def test_sqlite_g5_journal_graph_concurrent_writer_fails_closed(
    tmp_path, monkeypatch,
):
    path = tmp_path / "source-race.sqlite3"
    with SQLiteRegistry(path) as reg, SQLiteRegistry(path) as concurrent:
        _seed(reg)
        before = _full(reg)
        _change_consumer(reg, "integer")
        original_get = reg.get
        mutated = False

        def mutate_while_reading(key):
            nonlocal mutated
            if not mutated:
                mutated = True
                concurrent.register(_tool("raced-new-tool"))
            return original_get(key)

        monkeypatch.setattr(reg, "get", mutate_while_reading)
        with pytest.raises(PolicyViolationError):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(before, reg)
        assert mutated


def test_sqlite_g5_journal_graph_preserves_failed_original_history_limits(tmp_path):
    with SQLiteRegistry(tmp_path / "journal-barrier.sqlite3") as reg:
        _seed(reg)
        original = _full(reg)
        reg.update_many(_tool(f"oversized_{n}") for n in range(65))
        with pytest.raises(PolicyViolationError, match="full build required"):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(original, reg)
