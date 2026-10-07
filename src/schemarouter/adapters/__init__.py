from importlib import import_module
from typing import TYPE_CHECKING, Any

from ..openapi_compatibility import (
    OpenAPICompatibilityIssue,
    OpenAPICompatibilityReport,
    analyze_openapi_compatibility,
)
from .base import AdapterContext, AdapterLoadResult, AdapterRegistry, SourceAdapter
from .graph_store import (
    GraphModel,
    GraphNodeTypeSpec,
    GraphPropertySpec,
    GraphRelationshipTypeSpec,
    GraphSourceBinding,
    GraphSourceInvoker,
    GraphSourceSpec,
    GraphStoreBackend,
    ScopedGraphStoreBackend,
    introspect_graph_backend,
)
from .graphql import (
    GraphQLRemoteInvoker,
    GraphQLSourceAdapter,
    tool_from_graphql_introspection,
)
from .http_json import (
    HTTPJSONRemoteInvoker,
    build_http_json_invoker,
    prepare_http_json_tool,
)
from .mcp import (
    DefaultMCPClientFactory,
    MCPBoundClientFactory,
    MCPBoundInvoker,
    MCPClientFactory,
    MCPDiscoveryLimits,
    MCPRemoteInvoker,
    MCPStdioClientFactory,
    MCPStdioConfig,
    inspect_mcp_client_factory,
    inspect_mcp_stdio,
    inspect_mcp_url,
    tool_from_mcp,
)
from .odata import ODataRemoteInvoker, ODataSourceAdapter, tool_from_odata_metadata
from .openapi import OpenAPIRemoteInvoker, resolve_openapi_base_url, tool_from_openapi
from .openrpc import OpenRPCRemoteInvoker, OpenRPCSourceAdapter, tool_from_openrpc
from .optimade import OPTIMADERemoteInvoker, OPTIMADESourceAdapter
from .plugins import (
    ADAPTER_ENTRY_POINT_GROUP,
    AdapterPluginInfo,
    discover_adapter_plugins,
    load_adapter_plugins,
)
from .python import (
    PythonCallableInvoker,
    callable_options,
    schema_tool,
    tool_from_callable,
)
from .record_store import (
    RecordFieldSpec,
    RecordModel,
    RecordSourceBinding,
    RecordSourceInvoker,
    RecordSourceSpec,
    RecordStoreBackend,
    introspect_record_backend,
)
from .sqlalchemy_database import (
    SQLAlchemyTableBinding,
    SQLAlchemyTableInvoker,
    introspect_sqlalchemy_engine,
)
from .sqlite_database import (
    SQLiteTableBinding,
    SQLiteTableInvoker,
    introspect_sqlite_database,
)
from .vector_store import (
    ScopedVectorStoreBackend,
    VectorCollectionBinding,
    VectorCollectionInvoker,
    VectorCollectionSpec,
    VectorMetadataField,
    VectorQueryEmbedder,
    VectorStoreBackend,
    introspect_vector_backend,
)

if TYPE_CHECKING:
    from .graph_native import (
        ArangoGraphBackend,
        FalkorGraphBackend,
        Neo4jGraphBackend,
        NeptuneOpenCypherBackend,
        SparqlGraphBackend,
    )
    from .record_native import (
        ClickHouseRecordBackend,
        CosmosRecordBackend,
        CouchbaseRecordBackend,
        DynamoDBRecordBackend,
        ElasticRecordBackend,
        InfluxRecordBackend,
        MongoRecordBackend,
    )
    from .vector_native import (
        ChromaVectorBackend,
        MilvusVectorBackend,
        PgvectorVectorBackend,
        PineconeVectorBackend,
        QdrantVectorBackend,
        WeaviateVectorBackend,
    )


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "ArangoGraphBackend": (".graph_native", "ArangoGraphBackend"),
    "FalkorGraphBackend": (".graph_native", "FalkorGraphBackend"),
    "Neo4jGraphBackend": (".graph_native", "Neo4jGraphBackend"),
    "NeptuneOpenCypherBackend": (".graph_native", "NeptuneOpenCypherBackend"),
    "SparqlGraphBackend": (".graph_native", "SparqlGraphBackend"),
    "ClickHouseRecordBackend": (".record_native", "ClickHouseRecordBackend"),
    "CosmosRecordBackend": (".record_native", "CosmosRecordBackend"),
    "CouchbaseRecordBackend": (".record_native", "CouchbaseRecordBackend"),
    "DynamoDBRecordBackend": (".record_native", "DynamoDBRecordBackend"),
    "ElasticRecordBackend": (".record_native", "ElasticRecordBackend"),
    "InfluxRecordBackend": (".record_native", "InfluxRecordBackend"),
    "MongoRecordBackend": (".record_native", "MongoRecordBackend"),
    "ChromaVectorBackend": (".vector_native", "ChromaVectorBackend"),
    "MilvusVectorBackend": (".vector_native", "MilvusVectorBackend"),
    "PgvectorVectorBackend": (".vector_native", "PgvectorVectorBackend"),
    "PineconeVectorBackend": (".vector_native", "PineconeVectorBackend"),
    "QdrantVectorBackend": (".vector_native", "QdrantVectorBackend"),
    "WeaviateVectorBackend": (".vector_native", "WeaviateVectorBackend"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_EXPORTS))


__all__ = [
    "AdapterContext",
    "ADAPTER_ENTRY_POINT_GROUP",
    "AdapterLoadResult",
    "AdapterPluginInfo",
    "AdapterRegistry",
    "DefaultMCPClientFactory",
    "HTTPJSONRemoteInvoker",
    "ArangoGraphBackend",
    "FalkorGraphBackend",
    "GraphModel",
    "GraphNodeTypeSpec",
    "GraphPropertySpec",
    "GraphRelationshipTypeSpec",
    "GraphSourceBinding",
    "GraphSourceInvoker",
    "GraphSourceSpec",
    "GraphStoreBackend",
    "ScopedGraphStoreBackend",
    "Neo4jGraphBackend",
    "NeptuneOpenCypherBackend",
    "SparqlGraphBackend",
    "GraphQLRemoteInvoker",
    "GraphQLSourceAdapter",
    "MCPBoundClientFactory",
    "MCPBoundInvoker",
    "MCPClientFactory",
    "MCPDiscoveryLimits",
    "MCPRemoteInvoker",
    "MCPStdioClientFactory",
    "MCPStdioConfig",
    "ODataRemoteInvoker",
    "ODataSourceAdapter",
    "OPTIMADERemoteInvoker",
    "OPTIMADESourceAdapter",
    "OpenAPICompatibilityIssue",
    "OpenAPICompatibilityReport",
    "OpenAPIRemoteInvoker",
    "OpenRPCRemoteInvoker",
    "OpenRPCSourceAdapter",
    "PythonCallableInvoker",
    "ClickHouseRecordBackend",
    "CosmosRecordBackend",
    "CouchbaseRecordBackend",
    "DynamoDBRecordBackend",
    "ElasticRecordBackend",
    "InfluxRecordBackend",
    "MongoRecordBackend",
    "RecordFieldSpec",
    "RecordModel",
    "RecordSourceBinding",
    "RecordSourceInvoker",
    "RecordSourceSpec",
    "RecordStoreBackend",
    "ChromaVectorBackend",
    "MilvusVectorBackend",
    "PgvectorVectorBackend",
    "PineconeVectorBackend",
    "QdrantVectorBackend",
    "WeaviateVectorBackend",
    "SourceAdapter",
    "VectorCollectionBinding",
    "VectorCollectionInvoker",
    "VectorCollectionSpec",
    "VectorMetadataField",
    "ScopedVectorStoreBackend",
    "VectorQueryEmbedder",
    "VectorStoreBackend",
    "SQLiteTableBinding",
    "SQLiteTableInvoker",
    "SQLAlchemyTableBinding",
    "SQLAlchemyTableInvoker",
    "analyze_openapi_compatibility",
    "build_http_json_invoker",
    "callable_options",
    "discover_adapter_plugins",
    "inspect_mcp_client_factory",
    "inspect_mcp_stdio",
    "inspect_mcp_url",
    "introspect_sqlite_database",
    "introspect_vector_backend",
    "introspect_graph_backend",
    "introspect_record_backend",
    "introspect_sqlalchemy_engine",
    "load_adapter_plugins",
    "prepare_http_json_tool",
    "resolve_openapi_base_url",
    "schema_tool",
    "tool_from_callable",
    "tool_from_graphql_introspection",
    "tool_from_mcp",
    "tool_from_odata_metadata",
    "tool_from_openapi",
    "tool_from_openrpc",
]
