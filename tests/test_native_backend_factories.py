from __future__ import annotations

import subprocess
import sys

import pytest

from schemarouter.native_backend_factories import (
    build_native_backend,
    register_native_backend_factory,
    registered_native_backend_factories,
)


def test_builtin_vector_factories_are_registered() -> None:
    assert registered_native_backend_factories("vector") == (
        ("vector", "chroma"),
        ("vector", "milvus"),
        ("vector", "pgvector"),
        ("vector", "pinecone"),
        ("vector", "qdrant"),
        ("vector", "weaviate"),
    )


def test_custom_factory_extends_registry_without_runtime_switch() -> None:
    provider = "__test_custom_vector_factory__"
    sentinel = object()

    def factory(resource: object, **options: object) -> tuple[object, dict[str, object]]:
        return resource, dict(options)

    register_native_backend_factory("vector", provider, factory)

    backend = build_native_backend(
        "vector",
        provider,
        sentinel,
        option="value",
    )

    assert backend == (sentinel, {"option": "value"})


def test_duplicate_factory_registration_requires_explicit_replace() -> None:
    provider = "__test_duplicate_vector_factory__"

    def first(resource: object, **options: object) -> str:
        return "first"

    def second(resource: object, **options: object) -> str:
        return "second"

    register_native_backend_factory("vector", provider, first)
    with pytest.raises(ValueError, match="already registered"):
        register_native_backend_factory("vector", provider, second)

    register_native_backend_factory("vector", provider, second, replace=True)
    assert build_native_backend("vector", provider, object()) == "second"


def test_unknown_factory_fails_closed() -> None:
    with pytest.raises(LookupError, match="no native backend factory"):
        build_native_backend("vector", "__missing_provider__", object())


def test_factory_registry_preserves_lazy_native_adapter_imports() -> None:
    code = r"""
import sys

import schemarouter.native_backend_factories

assert "schemarouter.adapters.vector_native" not in sys.modules
assert "schemarouter.adapters.graph_native" not in sys.modules
assert "schemarouter.adapters.record_native" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)
