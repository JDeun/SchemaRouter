from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

NativeBackendFactory = Callable[..., Any]

_NATIVE_BACKEND_FACTORIES: dict[tuple[str, str], NativeBackendFactory] = {}


def _normalize_key(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


def register_native_backend_factory(
    family: str,
    provider: str,
    factory: NativeBackendFactory,
    *,
    replace: bool = False,
) -> None:
    """Register a native backend constructor without coupling it to SchemaRouter."""

    key = (
        _normalize_key(family, label="family"),
        _normalize_key(provider, label="provider"),
    )
    if key in _NATIVE_BACKEND_FACTORIES and not replace:
        raise ValueError(
            "native backend factory already registered for "
            f"{key[0]!r}/{key[1]!r}"
        )
    _NATIVE_BACKEND_FACTORIES[key] = factory


def registered_native_backend_factories(
    family: str | None = None,
) -> tuple[tuple[str, str], ...]:
    """Return registered family/provider pairs in deterministic order."""

    if family is None:
        return tuple(sorted(_NATIVE_BACKEND_FACTORIES))
    normalized = _normalize_key(family, label="family")
    return tuple(
        key
        for key in sorted(_NATIVE_BACKEND_FACTORIES)
        if key[0] == normalized
    )


def build_native_backend(
    family: str,
    provider: str,
    resource: Any,
    **options: Any,
) -> Any:
    """Construct one native backend from the registered family/provider factory."""

    key = (
        _normalize_key(family, label="family"),
        _normalize_key(provider, label="provider"),
    )
    factory = _NATIVE_BACKEND_FACTORIES.get(key)
    if factory is None:
        raise LookupError(
            f"no native backend factory registered for {key[0]!r}/{key[1]!r}"
        )
    return factory(resource, **options)


def _sorted_names(
    values: set[str] | tuple[str, ...] | list[str] | None,
) -> tuple[str, ...] | None:
    if values is None:
        return None
    return tuple(sorted(values))


def _build_qdrant(
    client: Any,
    *,
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    vector_name_by_collection: Mapping[str, str] | None = None,
    metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
    filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
    max_discovery_sources: int,
    max_fields_per_collection: int,
) -> Any:
    from .adapters.vector_native import QdrantVectorBackend

    return QdrantVectorBackend(
        client,
        vector_name_by_collection=vector_name_by_collection,
        metadata_fields_by_collection=metadata_fields_by_collection,
        filter_builder=filter_builder,
        collections=_sorted_names(collections),
        max_discovery_sources=max_discovery_sources,
        max_fields_per_collection=max_fields_per_collection,
    )


def _build_milvus(
    client: Any,
    *,
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    vector_field_by_collection: Mapping[str, str] | None = None,
    metric_by_collection: Mapping[str, str] | None = None,
    max_discovery_sources: int,
    max_fields_per_collection: int,
) -> Any:
    from .adapters.vector_native import MilvusVectorBackend

    return MilvusVectorBackend(
        client,
        vector_field_by_collection=vector_field_by_collection,
        metric_by_collection=metric_by_collection,
        collections=_sorted_names(collections),
        max_discovery_sources=max_discovery_sources,
        max_fields_per_collection=max_fields_per_collection,
    )


def _build_pinecone(
    client: Any,
    *,
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    metadata_fields_by_index: Mapping[str, Sequence[Any]] | None = None,
    max_discovery_sources: int,
    max_fields_per_collection: int,
) -> Any:
    from .adapters.vector_native import PineconeVectorBackend

    return PineconeVectorBackend(
        client,
        metadata_fields_by_index=metadata_fields_by_index,
        collections=_sorted_names(collections),
        max_discovery_sources=max_discovery_sources,
        max_fields_per_collection=max_fields_per_collection,
    )


def _build_chroma(
    client: Any,
    *,
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    dimension_by_collection: Mapping[str, int] | None = None,
    metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
    metric_by_collection: Mapping[str, str] | None = None,
    max_discovery_sources: int,
    max_fields_per_collection: int,
) -> Any:
    from .adapters.vector_native import ChromaVectorBackend

    return ChromaVectorBackend(
        client,
        dimension_by_collection=dimension_by_collection,
        metadata_fields_by_collection=metadata_fields_by_collection,
        metric_by_collection=metric_by_collection,
        collections=_sorted_names(collections),
        max_discovery_sources=max_discovery_sources,
        max_fields_per_collection=max_fields_per_collection,
    )


def _build_weaviate(
    client: Any,
    *,
    dimension_by_collection: Mapping[str, int],
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    vector_name_by_collection: Mapping[str, str] | None = None,
    metric_by_collection: Mapping[str, str] | None = None,
    filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
    max_discovery_sources: int,
    max_fields_per_collection: int,
) -> Any:
    from .adapters.vector_native import WeaviateVectorBackend

    return WeaviateVectorBackend(
        client,
        dimension_by_collection=dimension_by_collection,
        vector_name_by_collection=vector_name_by_collection,
        metric_by_collection=metric_by_collection,
        filter_builder=filter_builder,
        collections=_sorted_names(collections),
        max_discovery_sources=max_discovery_sources,
        max_fields_per_collection=max_fields_per_collection,
    )


def _build_pgvector(
    engine: Any,
    *,
    collections: set[str] | tuple[str, ...] | list[str] | None = None,
    tables: Sequence[str] | None = None,
    vector_field_by_table: Mapping[str, str] | None = None,
    metric_by_table: Mapping[str, str] | None = None,
    schema: str | None = None,
    max_discovery_sources: int,
    max_fields_per_collection: int,
) -> Any:
    from .adapters.vector_native import PgvectorVectorBackend

    resolved_tables: Sequence[str] | None
    if tables is not None:
        resolved_tables = tables
    else:
        resolved_tables = _sorted_names(collections)

    return PgvectorVectorBackend(
        engine,
        tables=resolved_tables,
        vector_field_by_table=vector_field_by_table,
        metric_by_table=metric_by_table,
        schema=schema,
        max_discovery_sources=max_discovery_sources,
        max_fields_per_collection=max_fields_per_collection,
    )


for _provider, _factory in {
    "qdrant": _build_qdrant,
    "milvus": _build_milvus,
    "pinecone": _build_pinecone,
    "chroma": _build_chroma,
    "weaviate": _build_weaviate,
    "pgvector": _build_pgvector,
}.items():
    register_native_backend_factory("vector", _provider, _factory)
