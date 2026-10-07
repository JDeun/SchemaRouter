from __future__ import annotations

from pathlib import Path

import pytest

from schemarouter.errors import RegistrationError
from schemarouter.native_registration import (
    NATIVE_VECTOR_BACKENDS,
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
