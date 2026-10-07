from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from threading import RLock
from typing import Any

from .errors import RegistrationError

NativeBackendFactory = Callable[..., Any]
NativeVectorBackendFactory = NativeBackendFactory
NativeGraphBackendFactory = NativeBackendFactory
NativeRecordBackendFactory = NativeBackendFactory


class NativeBackendRegistry:
    """Thread-safe registry for one trusted native backend family."""

    def __init__(self, family: str) -> None:
        normalized = family.strip().casefold()
        if not normalized:
            raise ValueError("native backend family must be non-empty")
        self._family = normalized
        self._factories: dict[str, NativeBackendFactory] = {}
        self._lock = RLock()

    def _normalize(self, name: str) -> str:
        normalized = name.strip().casefold()
        if not normalized:
            raise ValueError(
                f"native {self._family} backend name must be non-empty"
            )
        return normalized

    def register(
        self,
        name: str,
        factory: NativeBackendFactory,
        *,
        replace: bool = False,
    ) -> None:
        key = self._normalize(name)
        if not callable(factory):
            raise TypeError(
                f"native {self._family} backend factory must be callable"
            )
        with self._lock:
            if key in self._factories and not replace:
                raise ValueError(
                    f"native {self._family} backend {key!r} is already registered"
                )
            self._factories[key] = factory

    def build(self, name: str, resource: Any, **options: Any) -> Any:
        key = self._normalize(name)
        with self._lock:
            factory = self._factories.get(key)
            available = tuple(sorted(self._factories))
        if factory is None:
            supported = ", ".join(available) if available else "<none>"
            raise RegistrationError(
                f"unknown native {self._family} backend {key!r}; "
                f"registered backends: {supported}"
            )
        return factory(resource, **options)

    def names(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._factories))


class NativeVectorBackendRegistry(NativeBackendRegistry):
    """Registry for trusted native vector backend constructors."""

    def __init__(self) -> None:
        super().__init__("vector")


class NativeGraphBackendRegistry(NativeBackendRegistry):
    """Registry for trusted native graph backend constructors."""

    def __init__(self) -> None:
        super().__init__("graph")


class NativeRecordBackendRegistry(NativeBackendRegistry):
    """Registry for trusted native record backend constructors."""

    def __init__(self) -> None:
        super().__init__("record")


def _lazy_backend_factory(
    module_name: str,
    class_name: str,
) -> NativeBackendFactory:
    def factory(resource: Any, **options: Any) -> Any:
        module = import_module(module_name, package="schemarouter")
        backend_type = getattr(module, class_name)
        return backend_type(resource, **options)

    return factory


def _lazy_vector_factory(class_name: str) -> NativeVectorBackendFactory:
    return _lazy_backend_factory(".adapters.vector_native", class_name)


def _lazy_graph_factory(class_name: str) -> NativeGraphBackendFactory:
    return _lazy_backend_factory(".adapters.graph_native", class_name)


def _lazy_record_factory(class_name: str) -> NativeRecordBackendFactory:
    return _lazy_backend_factory(".adapters.record_native", class_name)


NATIVE_VECTOR_BACKENDS = NativeVectorBackendRegistry()
NATIVE_GRAPH_BACKENDS = NativeGraphBackendRegistry()
NATIVE_RECORD_BACKENDS = NativeRecordBackendRegistry()

for _name, _class_name in (
    ("qdrant", "QdrantVectorBackend"),
    ("milvus", "MilvusVectorBackend"),
    ("pinecone", "PineconeVectorBackend"),
    ("chroma", "ChromaVectorBackend"),
    ("weaviate", "WeaviateVectorBackend"),
    ("pgvector", "PgvectorVectorBackend"),
):
    NATIVE_VECTOR_BACKENDS.register(_name, _lazy_vector_factory(_class_name))

for _name, _class_name in (
    ("neo4j", "Neo4jGraphBackend"),
    ("falkordb", "FalkorGraphBackend"),
    ("neptune", "NeptuneOpenCypherBackend"),
    ("arangodb", "ArangoGraphBackend"),
    ("sparql", "SparqlGraphBackend"),
):
    NATIVE_GRAPH_BACKENDS.register(_name, _lazy_graph_factory(_class_name))

for _name, _class_name in (
    ("mongodb", "MongoRecordBackend"),
    ("elasticsearch", "ElasticRecordBackend"),
    ("opensearch", "ElasticRecordBackend"),
    ("dynamodb", "DynamoDBRecordBackend"),
    ("cosmos", "CosmosRecordBackend"),
    ("couchbase", "CouchbaseRecordBackend"),
    ("clickhouse", "ClickHouseRecordBackend"),
    ("influxdb", "InfluxRecordBackend"),
):
    NATIVE_RECORD_BACKENDS.register(_name, _lazy_record_factory(_class_name))


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


def register_native_graph_backend(
    name: str,
    factory: NativeGraphBackendFactory,
    *,
    replace: bool = False,
) -> None:
    """Register a trusted native graph backend constructor."""

    NATIVE_GRAPH_BACKENDS.register(name, factory, replace=replace)


def build_native_graph_backend(
    name: str,
    resource: Any,
    **options: Any,
) -> Any:
    """Construct a registered native graph backend."""

    return NATIVE_GRAPH_BACKENDS.build(name, resource, **options)



def register_native_record_backend(
    name: str,
    factory: NativeRecordBackendFactory,
    *,
    replace: bool = False,
) -> None:
    """Register a trusted native record backend constructor."""

    NATIVE_RECORD_BACKENDS.register(name, factory, replace=replace)


def build_native_record_backend(
    name: str,
    resource: Any,
    **options: Any,
) -> Any:
    """Construct a registered native record backend."""

    return NATIVE_RECORD_BACKENDS.build(name, resource, **options)
