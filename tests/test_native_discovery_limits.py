from __future__ import annotations

import sqlite3

import pytest

from schemarouter import (
    GraphNodeTypeSpec,
    GraphPropertySpec,
    GraphSourceSpec,
    NativeDiscoveryLimits,
    RecordFieldSpec,
    RecordSourceSpec,
    SchemaRouter,
    VectorCollectionSpec,
    VectorMetadataField,
)
from schemarouter.errors import RegistrationError


def _limits(**overrides: int) -> NativeDiscoveryLimits:
    values = {
        "max_sources": 8,
        "max_fields_per_source": 8,
        "max_node_types_per_source": 8,
        "max_relationship_types_per_source": 8,
        "max_properties_per_type": 8,
        "max_total_items": 64,
        "max_descriptor_bytes": 64 * 1024,
    }
    values.update(overrides)
    return NativeDiscoveryLimits(**values)


def test_native_discovery_limits_require_positive_integer_values() -> None:
    with pytest.raises(ValueError, match="max_sources"):
        NativeDiscoveryLimits(max_sources=0)
    with pytest.raises(ValueError, match="max_sources"):
        NativeDiscoveryLimits(max_sources=True)


def test_vector_discovery_stops_after_one_item_past_source_budget() -> None:
    class Backend:
        def __init__(self) -> None:
            self.consumed = 0

        def list_collections(self):
            for index in range(100):
                self.consumed += 1
                yield VectorCollectionSpec(
                    name=f"collection_{index}",
                    dimension=3,
                )

        def search(self, **_kwargs):
            return []

    backend = Backend()
    router = SchemaRouter()

    with pytest.raises(RegistrationError, match="vector collection count"):
        router.add_vector_store(
            backend,
            lambda _query: [0.0, 0.0, 0.0],
            database_name="vectors",
            remote=False,
            discovery_limits=_limits(max_sources=2),
        )

    assert backend.consumed == 3
    assert router.registry.keys() == ()


def test_vector_allowlist_stops_after_requested_descriptor() -> None:
    class Backend:
        def __init__(self) -> None:
            self.consumed = 0

        def list_collections(self):
            for name in ("wanted", "unrelated_a", "unrelated_b"):
                self.consumed += 1
                yield VectorCollectionSpec(name=name, dimension=3)

        def search(self, **_kwargs):
            return []

    backend = Backend()
    router = SchemaRouter()
    keys = router.add_vector_store(
        backend,
        lambda _query: [0.0, 0.0, 0.0],
        database_name="vectors",
        collections={"wanted"},
        remote=False,
        discovery_limits=_limits(max_sources=1),
    )

    assert keys == ("vectors.wanted",)
    assert backend.consumed == 1


def test_vector_allowlist_still_reports_missing_requested_source() -> None:
    class Backend:
        def list_collections(self):
            yield VectorCollectionSpec(name="available", dimension=3)

        def search(self, **_kwargs):
            return []

    with pytest.raises(RegistrationError, match="unknown vector collections"):
        SchemaRouter().add_vector_store(
            Backend(),
            lambda _query: [0.0, 0.0, 0.0],
            database_name="vectors",
            collections={"missing"},
            remote=False,
            discovery_limits=_limits(max_sources=2),
        )


def test_vector_discovery_rejects_oversized_descriptor_before_publish() -> None:
    class Backend:
        def list_collections(self):
            return (
                VectorCollectionSpec(
                    name="docs",
                    dimension=3,
                    metadata_fields=tuple(
                        VectorMetadataField(name=f"field_{index}")
                        for index in range(3)
                    ),
                ),
            )

        def search(self, **_kwargs):
            return []

    router = SchemaRouter()
    with pytest.raises(RegistrationError, match="metadata field count"):
        router.add_vector_store(
            Backend(),
            lambda _query: [0.0, 0.0, 0.0],
            database_name="vectors",
            remote=False,
            discovery_limits=_limits(max_fields_per_source=2),
        )
    assert router.registry.keys() == ()


def test_graph_discovery_bounds_properties_and_is_failure_atomic() -> None:
    class Backend:
        def list_graphs(self):
            return (
                GraphSourceSpec(
                    name="knowledge",
                    node_types=(
                        GraphNodeTypeSpec(
                            name="Document",
                            properties=tuple(
                                GraphPropertySpec(name=f"property_{index}")
                                for index in range(3)
                            ),
                        ),
                    ),
                ),
            )

        def traverse(self, **_kwargs):
            return []

    router = SchemaRouter()
    with pytest.raises(RegistrationError, match="property count"):
        router.add_graph_store(
            Backend(),
            database_name="graph",
            remote=False,
            discovery_limits=_limits(max_properties_per_type=2),
        )
    assert router.registry.keys() == ()


def test_record_discovery_bounds_fields_and_descriptor_bytes() -> None:
    class FieldBackend:
        def list_sources(self):
            return (
                RecordSourceSpec(
                    name="documents",
                    model="document",
                    fields=tuple(
                        RecordFieldSpec(name=f"field_{index}")
                        for index in range(3)
                    ),
                ),
            )

        def query(self, **_kwargs):
            return []

    router = SchemaRouter()
    with pytest.raises(RegistrationError, match="field count"):
        router.add_record_store(
            FieldBackend(),
            database_name="records",
            remote=False,
            discovery_limits=_limits(max_fields_per_source=2),
        )
    assert router.registry.keys() == ()

    class LargeDescriptorBackend:
        def list_sources(self):
            return (
                RecordSourceSpec(
                    name="documents",
                    model="document",
                    description="x" * 512,
                    fields=(RecordFieldSpec(name="id"),),
                ),
            )

        def query(self, **_kwargs):
            return []

    with pytest.raises(RegistrationError, match="descriptor bytes"):
        SchemaRouter().add_record_store(
            LargeDescriptorBackend(),
            database_name="records",
            remote=False,
            discovery_limits=_limits(max_descriptor_bytes=128),
        )


def test_sqlite_allowlist_short_circuits_catalog_budget() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        for name in ("wanted", "unrelated_a", "unrelated_b"):
            connection.execute(f'CREATE TABLE "{name}" (id INTEGER PRIMARY KEY, value TEXT)')

        router = SchemaRouter()
        keys = router.add_sqlite_database(
            connection,
            database_name="local",
            tables={"wanted"},
            discovery_limits=_limits(max_sources=1),
        )
        assert keys == ("local.wanted",)

        with pytest.raises(RegistrationError, match="relation count"):
            SchemaRouter().add_sqlite_database(
                connection,
                database_name="local",
                discovery_limits=_limits(max_sources=1),
            )
    finally:
        connection.close()


def test_sqlite_column_budget_fails_before_publish() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute(
            "CREATE TABLE wide (a INTEGER, b INTEGER, c INTEGER)"
        )
        router = SchemaRouter()
        with pytest.raises(RegistrationError, match="column count"):
            router.add_sqlite_database(
                connection,
                database_name="local",
                discovery_limits=_limits(max_fields_per_source=2),
            )
        assert router.registry.keys() == ()
    finally:
        connection.close()
