"""Original API-owned SQLite native G5 graph delta E0: full typed oracle."""
from __future__ import annotations

import sqlite3

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    NativeDeclaredFieldGroup,
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


def _seed(registry: SQLiteRegistry) -> SchemaRouter:
    registry.update_many(_synthetic_router(12).registry.tools())
    return SchemaRouter(
        registry=registry,
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("reader",),
            ),),
        ),
    )


def _build(registry: SQLiteRegistry) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(registry))


@pytest.mark.parametrize("change", [
    "incompatible_input", "metadata_change", "new_tool",
    "delete_tool", "transient",
])
def test_sqlite_journal_g5_graph_matches_original_full_build(tmp_path, change):
    path = tmp_path / "g5.sqlite3"
    with SQLiteRegistry(path) as source:
        router = _seed(source)
        old = _build(source)
        if change == "incompatible_input":
            tool = source.get("case_service")
            endpoint = tool.endpoint("read")
            endpoint.parameters[0].json_schema = {"type": "integer"}
            endpoint.input_schema = {
                "type": "object",
                "properties": {"customer_id": {"type": "integer"}},
                "required": ["customer_id"],
            }
            source.register(tool, replace=True)
        elif change == "metadata_change":
            tool = source.get("unrelated_00002")
            tool.description = "a source-native metadata-only update"
            source.register(tool, replace=True)
        elif change == "new_tool":
            source.register(ToolSpec(
                name="added", endpoints=[EndpointSpec(name="read")],
            ))
        elif change == "delete_tool":
            source.unregister("unrelated_00002")
        else:
            source.register(ToolSpec(
                name="transient", endpoints=[EndpointSpec(name="read")],
            ))
            source.unregister("transient")
        expected = _build(source)
        actual = NativeSchemaGraphIndex.refresh_from_sqlite_journal(
            old, source,
        )
        assert actual.field_index.snapshot_id == expected.field_index.snapshot_id
        assert actual.field_index.indexed_route_count == (
            expected.field_index.indexed_route_count
        )
        assert dict(actual.field_index.postings) == dict(expected.field_index.postings)
        assert actual.graph.capability_ids == expected.graph.capability_ids
        assert actual.graph.edges == expected.graph.edges
        assert actual.native_root_count == expected.native_root_count
        assert actual.native_consumer_count == expected.native_consumer_count
        assert actual.edge_consumer_routes == expected.edge_consumer_routes
        assert actual.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        ) == expected.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        )
        count = actual.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        ).qualified_path_count
        assert count == (0 if change == "incompatible_input" else 1)
        # These are source-host *declared* language aliases, not inferred
        # translations or evidence that a multilingual ranker succeeded.
        multilingual = NativeDeclaredFieldGroup(
            aliases=(QUERY, "사례 상태", "案件ステータス"),
            required_fields=GROUP.required_fields,
            source_type=GROUP.source_type,
            license=GROUP.license,
        )
        denied = PrincipalContext(
            subject="denied",
            roles=("unprivileged",),
        )
        for actor in (PRINCIPAL, denied):
            for label in multilingual.aliases:
                actual_result = actual.lookup(
                    router, label, group=multilingual, principal=actor,
                )
                expected_result = expected.lookup(
                    router, label, group=multilingual, principal=actor,
                )
                assert actual_result == expected_result
                if actor == denied:
                    assert actual_result.qualified_path_count == 0
                else:
                    assert actual_result.qualified_path_count == count
        with pytest.raises(ValueError, match="approved semantic edge"):
            actual.lookup(
                router, "unknown unapproved alias",
                group=multilingual, principal=PRINCIPAL,
            )
        with SQLiteRegistry(path) as cross_reader:
            changes = cross_reader.changed_tool_keys_since(
                old.field_index.registry_version,
            )
            assert changes.to_version == source.version


def test_sqlite_journal_g5_delta_does_not_scan_unmodified_catalog(
    tmp_path, monkeypatch,
):
    with SQLiteRegistry(tmp_path / "delta.sqlite3") as source:
        router = _seed(source)
        old = _build(source)
        tool = source.get("case_service")
        tool.description = "new native version"
        source.register(tool, replace=True)
        real_get = source.get

        def changed_only(key):
            if key != "case_service":
                pytest.fail("SQLite G5 journal read an unchanged tool")
            return real_get(key)

        with monkeypatch.context() as scoped:
            scoped.setattr(source, "get", changed_only)
            scoped.setattr(
                source, "tools",
                lambda: pytest.fail("SQLite G5 journal scanned whole catalog"),
            )
            scoped.setattr(
                source, "keys",
                lambda: pytest.fail("SQLite G5 journal scanned all keys"),
            )
            delta = NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                old, source,
            )
        assert delta.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
        ).qualified_path_count == 1


def test_sqlite_journal_g5_refuses_wrong_source_and_no_change(tmp_path):
    with SQLiteRegistry(tmp_path / "first.sqlite3") as source:
        _seed(source)
        old = _build(source)
        with pytest.raises(PolicyViolationError, match="invalid versioned changes"):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(old, source)
        other_path = tmp_path / "second.sqlite3"
        with SQLiteRegistry(other_path) as other:
            _seed(other)
            other.register(ToolSpec(
                name="changed", endpoints=[EndpointSpec(name="read")],
            ))
            with pytest.raises(PolicyViolationError, match="source mismatch"):
                NativeSchemaGraphIndex.refresh_from_sqlite_journal(old, other)


def test_sqlite_journal_g5_rejects_cross_connection_concurrent_writer(
    tmp_path, monkeypatch,
):
    path = tmp_path / "race.sqlite3"
    with SQLiteRegistry(path) as source, SQLiteRegistry(path) as other:
        _seed(source)
        old = _build(source)
        changed = source.get("case_service")
        changed.description = "before racing writer"
        source.register(changed, replace=True)
        real_get = source.get
        written = False

        def raced(key):
            nonlocal written
            if not written:
                written = True
                other.register(ToolSpec(
                    name="unexpected", endpoints=[EndpointSpec(name="read")],
                ))
            return real_get(key)

        monkeypatch.setattr(source, "get", raced)
        with pytest.raises(PolicyViolationError):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                old, source,
            )
        assert written


def test_sqlite_journal_g5_rejects_corrupt_receipt(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    with SQLiteRegistry(path) as source:
        _seed(source)
        old = _build(source)
        source.register(ToolSpec(
            name="new_native", endpoints=[EndpointSpec(name="read")],
        ))
        with sqlite3.connect(path) as conn:
            conn.execute(
                "UPDATE schemarouter_registry_mutations "
                "SET changed_keys = ? WHERE version = ?",
                ('["new_native","new_native"]', source.version),
            )
        with pytest.raises(PolicyViolationError, match="history unavailable"):
            NativeSchemaGraphIndex.refresh_from_sqlite_journal(
                old, source,
            )
