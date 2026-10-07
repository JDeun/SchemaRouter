from __future__ import annotations

import ast
from pathlib import Path

import pytest

from schemarouter.errors import RegistrationError
from schemarouter.native_registration import (
    NATIVE_GRAPH_BACKENDS,
    NATIVE_RECORD_BACKENDS,
    NATIVE_VECTOR_BACKENDS,
    NativeGraphBackendRegistry,
    NativeRecordBackendRegistry,
    NativeVectorBackendRegistry,
)


def test_native_vector_registry_builds_registered_factory() -> None:
    registry = NativeVectorBackendRegistry()
    resource = object()

    registry.register(
        "custom",
        lambda value, **options: (value, options),
    )

    built_resource, options = registry.build(
        "CUSTOM",
        resource,
        namespace="tenant-a",
    )

    assert built_resource is resource
    assert options == {"namespace": "tenant-a"}
    assert registry.names() == ("custom",)


def test_native_vector_registry_fails_closed_for_unknown_backend() -> None:
    registry = NativeVectorBackendRegistry()

    with pytest.raises(RegistrationError, match="unknown native vector backend"):
        registry.build("missing", object())


def test_native_vector_registry_rejects_accidental_replacement() -> None:
    registry = NativeVectorBackendRegistry()
    registry.register("custom", lambda resource, **options: resource)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("custom", lambda resource, **options: resource)


def test_builtin_native_vector_backends_are_registered() -> None:
    assert {
        "qdrant",
        "milvus",
        "pinecone",
        "chroma",
        "weaviate",
        "pgvector",
    } <= set(NATIVE_VECTOR_BACKENDS.names())


def test_runtime_does_not_own_native_vector_vendor_classes() -> None:
    runtime = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "schemarouter"
        / "runtime.py"
    ).read_text(encoding="utf-8")

    for class_name in (
        "QdrantVectorBackend",
        "MilvusVectorBackend",
        "PineconeVectorBackend",
        "ChromaVectorBackend",
        "WeaviateVectorBackend",
        "PgvectorVectorBackend",
    ):
        assert class_name not in runtime


def test_native_graph_registry_builds_registered_factory() -> None:
    registry = NativeGraphBackendRegistry()
    resource = object()

    registry.register(
        "custom",
        lambda value, **options: (value, options),
    )

    built_resource, options = registry.build(
        "CUSTOM",
        resource,
        database="graph-db",
    )

    assert built_resource is resource
    assert options == {"database": "graph-db"}
    assert registry.names() == ("custom",)


def test_native_graph_registry_fails_closed_for_unknown_backend() -> None:
    registry = NativeGraphBackendRegistry()

    with pytest.raises(RegistrationError, match="unknown native graph backend"):
        registry.build("missing", object())


def test_builtin_native_graph_backends_are_registered() -> None:
    assert {
        "neo4j",
        "falkordb",
        "neptune",
        "arangodb",
        "sparql",
    } <= set(NATIVE_GRAPH_BACKENDS.names())


def test_runtime_does_not_own_native_graph_vendor_classes() -> None:
    runtime = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "schemarouter"
        / "runtime.py"
    ).read_text(encoding="utf-8")

    for class_name in (
        "Neo4jGraphBackend",
        "FalkorGraphBackend",
        "NeptuneOpenCypherBackend",
        "ArangoGraphBackend",
        "SparqlGraphBackend",
    ):
        assert class_name not in runtime



def test_native_record_registry_builds_registered_factory() -> None:
    registry = NativeRecordBackendRegistry()
    resource = object()

    registry.register(
        "custom",
        lambda value, **options: (value, options),
    )

    built_resource, options = registry.build(
        "CUSTOM",
        resource,
        sources=("items",),
    )

    assert built_resource is resource
    assert options == {"sources": ("items",)}
    assert registry.names() == ("custom",)


def test_native_record_registry_fails_closed_for_unknown_backend() -> None:
    registry = NativeRecordBackendRegistry()

    with pytest.raises(RegistrationError, match="unknown native record backend"):
        registry.build("missing", object())


def test_builtin_native_record_backends_are_registered() -> None:
    assert {
        "mongodb",
        "elasticsearch",
        "opensearch",
        "dynamodb",
        "cosmos",
        "couchbase",
        "clickhouse",
        "influxdb",
    } <= set(NATIVE_RECORD_BACKENDS.names())


def test_runtime_does_not_own_native_record_vendor_classes() -> None:
    runtime = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "schemarouter"
        / "runtime.py"
    ).read_text(encoding="utf-8")

    for class_name in (
        "MongoRecordBackend",
        "ElasticRecordBackend",
        "DynamoDBRecordBackend",
        "CosmosRecordBackend",
        "CouchbaseRecordBackend",
        "ClickHouseRecordBackend",
        "InfluxRecordBackend",
    ):
        assert class_name not in runtime

def test_adapter_modules_do_not_depend_on_runtime_facade() -> None:
    adapters_root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "schemarouter"
        / "adapters"
    )
    violations: list[str] = []

    for path in sorted(adapters_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "schemarouter.runtime" or alias.name.startswith(
                        "schemarouter.runtime."
                    ):
                        violations.append(
                            f"{path.relative_to(adapters_root)}:{node.lineno}: "
                            f"import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                absolute_runtime = (
                    node.level == 0
                    and node.module is not None
                    and (
                        node.module == "schemarouter.runtime"
                        or node.module.startswith("schemarouter.runtime.")
                    )
                )
                relative_runtime = node.level >= 2 and node.module == "runtime"
                if absolute_runtime or relative_runtime:
                    violations.append(
                        f"{path.relative_to(adapters_root)}:{node.lineno}: "
                        "runtime façade import"
                    )

    assert violations == [], (
        "adapter modules must depend on core contracts, not runtime.py: "
        + "; ".join(violations)
    )

