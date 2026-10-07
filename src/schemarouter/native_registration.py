from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from threading import RLock
from typing import Any

from .errors import RegistrationError

NativeVectorBackendFactory = Callable[..., Any]


class NativeVectorBackendRegistry:
    """Thread-safe registry for trusted native vector backend constructors.

    The runtime owns the generic registration lifecycle. Vendor-specific backend
    construction lives behind this registry so adding a backend does not require
    editing the SchemaRouter facade.
    """

    def __init__(self) -> None:
        self._factories: dict[str, NativeVectorBackendFactory] = {}
        self._lock = RLock()

    @staticmethod
    def _normalize(name: str) -> str:
        normalized = name.strip().casefold()
        if not normalized:
            raise ValueError("native vector backend name must be non-empty")
        return normalized

    def register(
        self,
        name: str,
        factory: NativeVectorBackendFactory,
        *,
        replace: bool = False,
    ) -> None:
        key = self._normalize(name)
        if not callable(factory):
            raise TypeError("native vector backend factory must be callable")
        with self._lock:
            if key in self._factories and not replace:
                raise ValueError(f"native vector backend {key!r} is already registered")
            self._factories[key] = factory

    def build(self, name: str, resource: Any, **options: Any) -> Any:
        key = self._normalize(name)
        with self._lock:
            factory = self._factories.get(key)
            available = tuple(sorted(self._factories))
        if factory is None:
            supported = ", ".join(available) if available else "<none>"
            raise RegistrationError(
                f"unknown native vector backend {key!r}; registered backends: {supported}"
            )
        return factory(resource, **options)

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._factories))


def _lazy_vector_factory(class_name: str) -> NativeVectorBackendFactory:
    def factory(resource: Any, **options: Any) -> Any:
        module = import_module(".adapters.vector_native", package="schemarouter")
        backend_type = getattr(module, class_name)
        return backend_type(resource, **options)

    return factory


NATIVE_VECTOR_BACKENDS = NativeVectorBackendRegistry()

for _name, _class_name in (
    ("qdrant", "QdrantVectorBackend"),
    ("milvus", "MilvusVectorBackend"),
    ("pinecone", "PineconeVectorBackend"),
    ("chroma", "ChromaVectorBackend"),
    ("weaviate", "WeaviateVectorBackend"),
    ("pgvector", "PgvectorVectorBackend"),
):
    NATIVE_VECTOR_BACKENDS.register(_name, _lazy_vector_factory(_class_name))


def register_native_vector_backend(
    name: str,
    factory: NativeVectorBackendFactory,
    *,
    replace: bool = False,
) -> None:
    """Register a trusted native vector backend constructor."""

    NATIVE_VECTOR_BACKENDS.register(name, factory, replace=replace)


def build_native_vector_backend(
    name: str,
    resource: Any,
    **options: Any,
) -> Any:
    """Construct a registered native vector backend."""

    return NATIVE_VECTOR_BACKENDS.build(name, resource, **options)
