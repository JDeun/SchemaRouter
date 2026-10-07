from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol, TypeVar, cast

from .runtime_defaults import RUNTIME_DEFAULTS

_T = TypeVar("_T")


class _NativeProviderHost(Protocol):
    async def aadd_native_vector_store(self, *args: Any, **kwargs: Any) -> tuple[str, ...]: ...

    async def aadd_native_graph_store(self, *args: Any, **kwargs: Any) -> tuple[str, ...]: ...

    async def aadd_native_record_store(self, *args: Any, **kwargs: Any) -> tuple[str, ...]: ...

    def _run_sync_call(self, factory: Callable[[], Awaitable[_T]]) -> _T: ...


class NativeProviderConvenienceMixin:
    """Compatibility facade for named native vector/graph/record providers.

    The implementation authority remains in the host generic native registration
    methods. This mixin only preserves stable provider-specific convenience signatures.
    """
    async def aadd_qdrant_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "qdrant",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Qdrant client through the vector capability contract."""

        return await cast(_NativeProviderHost, self).aadd_native_vector_store(
            "qdrant",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "vector_name_by_collection": vector_name_by_collection,
                "metadata_fields_by_collection": metadata_fields_by_collection,
                "filter_builder": filter_builder,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_qdrant_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "qdrant",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_qdrant_vector_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_qdrant_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                vector_name_by_collection=vector_name_by_collection,
                metadata_fields_by_collection=metadata_fields_by_collection,
                filter_builder=filter_builder,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_milvus_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "milvus",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_field_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned MilvusClient through the vector capability contract."""

        return await cast(_NativeProviderHost, self).aadd_native_vector_store(
            "milvus",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "vector_field_by_collection": vector_field_by_collection,
                "metric_by_collection": metric_by_collection,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_milvus_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "milvus",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_field_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_milvus_vector_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_milvus_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                vector_field_by_collection=vector_field_by_collection,
                metric_by_collection=metric_by_collection,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_pinecone_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "pinecone",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        metadata_fields_by_index: Mapping[str, Sequence[Any]] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Pinecone client."""

        return await cast(_NativeProviderHost, self).aadd_native_vector_store(
            "pinecone",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "metadata_fields_by_index": metadata_fields_by_index,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_pinecone_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "pinecone",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        metadata_fields_by_index: Mapping[str, Sequence[Any]] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_pinecone_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                metadata_fields_by_index=metadata_fields_by_index,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_chroma_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "chroma",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        dimension_by_collection: Mapping[str, int] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = False,
    ) -> tuple[str, ...]:
        """Register a caller-owned Chroma client."""

        return await cast(_NativeProviderHost, self).aadd_native_vector_store(
            "chroma",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "dimension_by_collection": dimension_by_collection,
                "metadata_fields_by_collection": metadata_fields_by_collection,
                "metric_by_collection": metric_by_collection,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_chroma_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        database_name: str = "chroma",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        dimension_by_collection: Mapping[str, int] | None = None,
        metadata_fields_by_collection: Mapping[str, Sequence[Any]] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = False,
    ) -> tuple[str, ...]:
        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_chroma_vector_store(
                client,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                dimension_by_collection=dimension_by_collection,
                metadata_fields_by_collection=metadata_fields_by_collection,
                metric_by_collection=metric_by_collection,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_weaviate_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        database_name: str = "weaviate",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Weaviate v4 client."""

        return await cast(_NativeProviderHost, self).aadd_native_vector_store(
            "weaviate",
            client,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "dimension_by_collection": dimension_by_collection,
                "vector_name_by_collection": vector_name_by_collection,
                "metric_by_collection": metric_by_collection,
                "filter_builder": filter_builder,
                "collections": (
                    None if collections is None else tuple(sorted(collections))
                ),
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_weaviate_vector_store(
        self,
        client: Any,
        embed_query: Any,
        *,
        dimension_by_collection: Mapping[str, int],
        database_name: str = "weaviate",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        vector_name_by_collection: Mapping[str, str] | None = None,
        metric_by_collection: Mapping[str, str] | None = None,
        filter_builder: Callable[[Mapping[str, Any]], Any] | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_weaviate_vector_store(
                client,
                embed_query,
                dimension_by_collection=dimension_by_collection,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                vector_name_by_collection=vector_name_by_collection,
                metric_by_collection=metric_by_collection,
                filter_builder=filter_builder,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )

    async def aadd_pgvector_store(
        self,
        engine: Any,
        embed_query: Any,
        *,
        database_name: str = "pgvector",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        tables: Sequence[str] | None = None,
        vector_field_by_table: Mapping[str, str] | None = None,
        metric_by_table: Mapping[str, str] | None = None,
        schema: str | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register caller-owned PostgreSQL/pgvector Engine."""

        return await cast(_NativeProviderHost, self).aadd_native_vector_store(
            "pgvector",
            engine,
            embed_query,
            database_name=database_name,
            namespace=namespace,
            collections=collections,
            backend_options={
                "tables": (
                    tables
                    if tables is not None
                    else (
                        None
                        if collections is None
                        else tuple(sorted(collections))
                    )
                ),
                "vector_field_by_table": vector_field_by_table,
                "metric_by_table": metric_by_table,
                "schema": schema,
                "max_discovery_sources": max_discovery_sources,
                "max_fields_per_collection": max_fields_per_collection,
            },
            default_top_k=default_top_k,
            remote=remote,
            max_discovery_sources=max_discovery_sources,
            max_fields_per_collection=max_fields_per_collection,
        )

    def add_pgvector_store(
        self,
        engine: Any,
        embed_query: Any,
        *,
        database_name: str = "pgvector",
        namespace: str | None = None,
        collections: set[str] | tuple[str, ...] | list[str] | None = None,
        tables: Sequence[str] | None = None,
        vector_field_by_table: Mapping[str, str] | None = None,
        metric_by_table: Mapping[str, str] | None = None,
        schema: str | None = None,
        default_top_k: int = RUNTIME_DEFAULTS.vector_top_k,
        max_discovery_sources: int = RUNTIME_DEFAULTS.max_discovery_sources,
        max_fields_per_collection: int = RUNTIME_DEFAULTS.max_fields_per_collection,
        remote: bool = True,
    ) -> tuple[str, ...]:
        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_pgvector_store(
                engine,
                embed_query,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                tables=tables,
                vector_field_by_table=vector_field_by_table,
                metric_by_table=metric_by_table,
                schema=schema,
                default_top_k=default_top_k,
                max_discovery_sources=max_discovery_sources,
                max_fields_per_collection=max_fields_per_collection,
                remote=remote,
            )
        )


    async def aadd_neo4j_graph(
        self,
        driver: Any,
        *,
        database: str,
        graph_name: str | None = None,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Neo4j driver through the bounded graph contract."""

        return await cast(_NativeProviderHost, self).aadd_native_graph_store(
            "neo4j",
            driver,
            database_name=database,
            namespace=namespace,
            graphs=graphs,
            backend_options={
                "database": database,
                "graph_name": graph_name,
            },
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_neo4j_graph(
        self,
        driver: Any,
        *,
        database: str,
        graph_name: str | None = None,
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_neo4j_graph`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_neo4j_graph(
                driver,
                database=database,
                graph_name=graph_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_falkordb_graph(
        self,
        client: Any,
        *,
        database_name: str = "falkordb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned FalkorDB client through the bounded graph contract."""

        graph_names = None if graphs is None else tuple(sorted(graphs))
        return await cast(_NativeProviderHost, self).aadd_native_graph_store(
            "falkordb",
            client,
            database_name=database_name,
            namespace=namespace,
            graphs=graphs,
            backend_options={"graphs": graph_names},
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_falkordb_graph(
        self,
        client: Any,
        *,
        database_name: str = "falkordb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_falkordb_graph`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_falkordb_graph(
                client,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_neptune_graph(
        self,
        client: Any,
        *,
        graph_name: str = "neptune",
        graph_identifier: str | None = None,
        database_name: str = "neptune",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Neptune Database/Analytics client."""

        return await cast(_NativeProviderHost, self).aadd_native_graph_store(
            "neptune",
            client,
            database_name=database_name,
            namespace=namespace,
            graphs={graph_name},
            backend_options={
                "graph_name": graph_name,
                "graph_identifier": graph_identifier,
            },
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_neptune_graph(
        self,
        client: Any,
        *,
        graph_name: str = "neptune",
        graph_identifier: str | None = None,
        database_name: str = "neptune",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_neptune_graph`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_neptune_graph(
                client,
                graph_name=graph_name,
                graph_identifier=graph_identifier,
                database_name=database_name,
                namespace=namespace,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_arango_graph(
        self,
        database: Any,
        *,
        database_name: str = "arangodb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned python-arango Database wrapper."""

        return await cast(_NativeProviderHost, self).aadd_native_graph_store(
            "arangodb",
            database,
            database_name=database_name,
            namespace=namespace,
            graphs=graphs,
            default_limit=default_limit,
            default_max_hops=default_max_hops,
            remote=remote,
        )

    def add_arango_graph(
        self,
        database: Any,
        *,
        database_name: str = "arangodb",
        namespace: str | None = None,
        graphs: set[str] | tuple[str, ...] | list[str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        default_max_hops: int = RUNTIME_DEFAULTS.graph_max_hops,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_arango_graph`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_arango_graph(
                database,
                database_name=database_name,
                namespace=namespace,
                graphs=graphs,
                default_limit=default_limit,
                default_max_hops=default_max_hops,
                remote=remote,
            )
        )

    async def aadd_sparql_graph(
        self,
        client: Any,
        *,
        endpoint: str,
        graph_name: str = "sparql",
        database_name: str = "sparql",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned HTTP client for a SPARQL 1.1 query endpoint."""

        return await cast(_NativeProviderHost, self).aadd_native_graph_store(
            "sparql",
            client,
            database_name=database_name,
            namespace=namespace,
            graphs={graph_name},
            backend_options={
                "endpoint": endpoint,
                "graph_name": graph_name,
            },
            default_limit=default_limit,
            default_max_hops=RUNTIME_DEFAULTS.graph_max_hops,
            remote=remote,
        )

    def add_sparql_graph(
        self,
        client: Any,
        *,
        endpoint: str,
        graph_name: str = "sparql",
        database_name: str = "sparql",
        namespace: str | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_sparql_graph`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_sparql_graph(
                client,
                endpoint=endpoint,
                graph_name=graph_name,
                database_name=database_name,
                namespace=namespace,
                default_limit=default_limit,
                remote=remote,
            )
        )


    async def aadd_mongodb_record_store(
        self,
        database: Any,
        *,
        database_name: str = "mongodb",
        namespace: str | None = None,
        collections: tuple[str, ...] | list[str] | None = None,
        text_search_collections: tuple[str, ...] | list[str] = (),
        time_field_by_collection: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned PyMongo Database through the bounded record contract."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "mongodb",
            database,
            database_name=database_name,
            namespace=namespace,
            sources=None if collections is None else set(collections),
            backend_options={
                "collections": collections,
                "text_search_collections": text_search_collections,
                "time_field_by_collection": time_field_by_collection,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_mongodb_record_store(
        self,
        database: Any,
        *,
        database_name: str = "mongodb",
        namespace: str | None = None,
        collections: tuple[str, ...] | list[str] | None = None,
        text_search_collections: tuple[str, ...] | list[str] = (),
        time_field_by_collection: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_mongodb_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_mongodb_record_store(
                database,
                database_name=database_name,
                namespace=namespace,
                collections=collections,
                text_search_collections=text_search_collections,
                time_field_by_collection=time_field_by_collection,
                default_limit=default_limit,
                remote=remote,
            )
        )

    async def aadd_elasticsearch_record_store(
        self,
        client: Any,
        *,
        database_name: str = "elasticsearch",
        namespace: str | None = None,
        indices: tuple[str, ...] | list[str] | None = None,
        time_field_by_index: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Elasticsearch client."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "elasticsearch",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if indices is None else set(indices),
            backend_options={
                "indices": indices,
                "time_field_by_index": time_field_by_index,
                "vendor": "elasticsearch",
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_elasticsearch_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_elasticsearch_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_elasticsearch_record_store(client, **kwargs)
        )

    async def aadd_opensearch_record_store(
        self,
        client: Any,
        *,
        database_name: str = "opensearch",
        namespace: str | None = None,
        indices: tuple[str, ...] | list[str] | None = None,
        time_field_by_index: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned OpenSearch client."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "opensearch",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if indices is None else set(indices),
            backend_options={
                "indices": indices,
                "time_field_by_index": time_field_by_index,
                "vendor": "opensearch",
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_opensearch_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_opensearch_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_opensearch_record_store(client, **kwargs)
        )

    async def aadd_dynamodb_record_store(
        self,
        client: Any,
        *,
        database_name: str = "dynamodb",
        namespace: str | None = None,
        tables: tuple[str, ...] | list[str] | None = None,
        time_field_by_table: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned low-level boto3 DynamoDB client."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "dynamodb",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if tables is None else set(tables),
            backend_options={
                "tables": tables,
                "time_field_by_table": time_field_by_table,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_dynamodb_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_dynamodb_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_dynamodb_record_store(client, **kwargs)
        )

    async def aadd_cosmos_record_store(
        self,
        database: Any,
        *,
        database_name: str = "cosmos",
        namespace: str | None = None,
        containers: tuple[str, ...] | list[str] | None = None,
        time_field_by_container: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Azure Cosmos DB DatabaseProxy."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "cosmos",
            database,
            database_name=database_name,
            namespace=namespace,
            sources=None if containers is None else set(containers),
            backend_options={
                "containers": containers,
                "time_field_by_container": time_field_by_container,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_cosmos_record_store(
        self,
        database: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_cosmos_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_cosmos_record_store(database, **kwargs)
        )

    async def aadd_couchbase_record_store(
        self,
        cluster: Any,
        *,
        database_name: str = "couchbase",
        namespace: str | None = None,
        keyspaces: tuple[str, ...] | list[str] | None = None,
        time_field_by_source: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned Couchbase Cluster."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "couchbase",
            cluster,
            database_name=database_name,
            namespace=namespace,
            sources=None if keyspaces is None else set(keyspaces),
            backend_options={
                "keyspaces": keyspaces,
                "time_field_by_source": time_field_by_source,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_couchbase_record_store(
        self,
        cluster: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_couchbase_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_couchbase_record_store(cluster, **kwargs)
        )

    async def aadd_clickhouse_record_store(
        self,
        client: Any,
        *,
        database_name: str = "clickhouse",
        namespace: str | None = None,
        tables: tuple[str, ...] | list[str] | None = None,
        time_field_by_table: Mapping[str, str] | None = None,
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned clickhouse-connect client."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "clickhouse",
            client,
            database_name=database_name,
            namespace=namespace,
            sources=None if tables is None else set(tables),
            backend_options={
                "tables": tables,
                "time_field_by_table": time_field_by_table,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_clickhouse_record_store(
        self,
        client: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_clickhouse_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_clickhouse_record_store(client, **kwargs)
        )

    async def aadd_influxdb_record_store(
        self,
        query_api: Any,
        *,
        bucket: str,
        org: str,
        database_name: str = "influxdb",
        namespace: str | None = None,
        measurements: tuple[str, ...] | list[str] | None = None,
        default_start: str = "-30d",
        default_limit: int = RUNTIME_DEFAULTS.collection_limit,
        remote: bool = True,
    ) -> tuple[str, ...]:
        """Register a caller-owned InfluxDB QueryApi."""

        return await cast(_NativeProviderHost, self).aadd_native_record_store(
            "influxdb",
            query_api,
            database_name=database_name,
            namespace=namespace,
            sources=None if measurements is None else set(measurements),
            backend_options={
                "bucket": bucket,
                "org": org,
                "measurements": measurements,
                "default_start": default_start,
            },
            default_limit=default_limit,
            remote=remote,
        )

    def add_influxdb_record_store(
        self,
        query_api: Any,
        **kwargs: Any,
    ) -> tuple[str, ...]:
        """Synchronous wrapper for :meth:`aadd_influxdb_record_store`."""

        return cast(_NativeProviderHost, self)._run_sync_call(
            lambda: self.aadd_influxdb_record_store(query_api, **kwargs)
        )

