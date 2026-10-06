from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from schemarouter import NativeDiscoveryLimits, SchemaRouter, VectorMetadataField
from schemarouter.errors import RegistrationError
from schemarouter.adapters.vector_native import (
    ChromaVectorBackend,
    MilvusVectorBackend,
    PgvectorVectorBackend,
    PineconeVectorBackend,
    QdrantVectorBackend,
    WeaviateVectorBackend,
)


@dataclass
class _VectorParams:
    size: int
    distance: str


@dataclass
class _QdrantParams:
    vectors: Any


@dataclass
class _QdrantConfig:
    params: _QdrantParams


@dataclass
class _QdrantInfo:
    config: _QdrantConfig
    payload_schema: dict[str, Any]


@dataclass
class _QdrantCollection:
    name: str


@dataclass
class _QdrantCollections:
    collections: list[_QdrantCollection]


@dataclass
class _QdrantPoint:
    id: str
    score: float
    payload: dict[str, Any]


@dataclass
class _QdrantResult:
    points: list[_QdrantPoint]


class FakeQdrantClient:
    def __init__(self) -> None:
        self.query_kwargs: dict[str, Any] = {}

    def get_collections(self) -> _QdrantCollections:
        return _QdrantCollections([_QdrantCollection("docs")])

    def get_collection(self, *, collection_name: str) -> _QdrantInfo:
        assert collection_name == "docs"
        return _QdrantInfo(
            config=_QdrantConfig(
                params=_QdrantParams(
                    vectors=_VectorParams(size=3, distance="Cosine"),
                )
            ),
            payload_schema={
                "tenant": {"data_type": "keyword"},
                "year": {"data_type": "integer"},
            },
        )

    def query_points(self, **kwargs: Any) -> _QdrantResult:
        self.query_kwargs = dict(kwargs)
        return _QdrantResult(
            [
                _QdrantPoint(
                    id="p1",
                    score=0.98,
                    payload={
                        "title": "Router",
                        "tenant": "tenant-a",
                        "year": 2026,
                    },
                )
            ]
        )


def test_qdrant_selected_collections_skip_catalog_enumeration() -> None:
    class ScopedClient(FakeQdrantClient):
        def get_collections(self):
            raise AssertionError("catalog enumeration should be skipped")

    backend = QdrantVectorBackend(
        ScopedClient(),
        collections=("docs",),
        discovery_limits=NativeDiscoveryLimits(max_sources=1),
    )

    collections = backend.list_collections()
    assert [item.name for item in collections] == ["docs"]


def test_qdrant_catalog_respects_source_budget_before_describing() -> None:
    class OversizedClient(FakeQdrantClient):
        def get_collections(self) -> _QdrantCollections:
            return _QdrantCollections(
                [_QdrantCollection("docs"), _QdrantCollection("archive")]
            )

        def get_collection(self, *, collection_name: str) -> _QdrantInfo:
            raise AssertionError("oversized catalog must fail before per-source discovery")

    backend = QdrantVectorBackend(
        OversizedClient(),
        discovery_limits=NativeDiscoveryLimits(max_sources=1),
    )
    with pytest.raises(RegistrationError, match="Qdrant collection count"):
        backend.list_collections()


def test_qdrant_adapter_discovers_schema_and_normalizes_query() -> None:
    client = FakeQdrantClient()
    backend = QdrantVectorBackend(
        client,
        metadata_fields_by_collection={
            "docs": (
                VectorMetadataField(
                    name="title",
                    json_schema={"type": "string"},
                ),
            )
        },
    )

    collections = backend.list_collections()
    assert len(collections) == 1
    spec = collections[0]
    assert spec.name == "docs"
    assert spec.dimension == 3
    assert spec.metric == "cosine"
    assert [field.name for field in spec.metadata_fields] == [
        "tenant",
        "title",
        "year",
    ]
    assert next(field for field in spec.metadata_fields if field.name == "tenant").filterable

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=5,
        include_fields=("title", "year"),
    )
    assert rows == [
        {
            "id": "p1",
            "score": 0.98,
            "title": "Router",
            "year": 2026,
        }
    ]
    assert client.query_kwargs["collection_name"] == "docs"
    assert client.query_kwargs["query"] == [0.1, 0.2, 0.3]
    assert client.query_kwargs["limit"] == 5
    assert client.query_kwargs["with_payload"] == ["title", "year"]
    assert client.query_kwargs["with_vectors"] is False


def test_qdrant_adapter_uses_trusted_filter_builder() -> None:
    client = FakeQdrantClient()
    built: list[dict[str, Any]] = []

    def build(filters: dict[str, Any]) -> dict[str, Any]:
        built.append(dict(filters))
        return {"must": dict(filters)}

    backend = QdrantVectorBackend(client, filter_builder=build)
    backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=3,
        include_fields=("tenant",),
        filters={"tenant": "tenant-a"},
    )

    assert built == [{"tenant": "tenant-a"}]
    assert client.query_kwargs["query_filter"] == {
        "must": {"tenant": "tenant-a"}
    }


def test_qdrant_named_vector_requires_explicit_selection() -> None:
    client = FakeQdrantClient()

    def named_info(*, collection_name: str) -> _QdrantInfo:
        assert collection_name == "docs"
        return _QdrantInfo(
            config=_QdrantConfig(
                params=_QdrantParams(
                    vectors={
                        "text": _VectorParams(size=3, distance="Cosine"),
                        "image": _VectorParams(size=4, distance="Dot"),
                    }
                )
            ),
            payload_schema={},
        )

    client.get_collection = named_info  # type: ignore[method-assign]
    with pytest.raises(Exception, match="multiple named vectors"):
        QdrantVectorBackend(client).list_collections()

    backend = QdrantVectorBackend(
        client,
        vector_name_by_collection={"docs": "text"},
    )
    spec = backend.list_collections()[0]
    assert spec.dimension == 3
    assert spec.public_metadata == {"vector_name": "text"}


class FakeMilvusClient:
    def __init__(self) -> None:
        self.search_kwargs: dict[str, Any] = {}

    def list_collections(self) -> list[str]:
        return ["docs"]

    def describe_collection(self, *, collection_name: str) -> dict[str, Any]:
        assert collection_name == "docs"
        return {
            "collection_name": "docs",
            "fields": [
                {
                    "name": "id",
                    "type": "INT64",
                    "params": {},
                    "is_primary": True,
                },
                {
                    "name": "embedding",
                    "type": "FLOAT_VECTOR",
                    "params": {"dim": 3},
                    "is_primary": False,
                },
                {
                    "name": "tenant",
                    "type": "VARCHAR",
                    "params": {"max_length": 64},
                    "is_primary": False,
                },
                {
                    "name": "year",
                    "type": "INT64",
                    "params": {},
                    "is_primary": False,
                },
            ],
        }

    def search(self, **kwargs: Any) -> list[list[dict[str, Any]]]:
        self.search_kwargs = dict(kwargs)
        return [
            [
                {
                    "id": 7,
                    "distance": 0.87,
                    "entity": {
                        "tenant": "tenant-a",
                        "year": 2026,
                    },
                }
            ]
        ]


def test_milvus_adapter_discovers_schema_and_normalizes_search() -> None:
    client = FakeMilvusClient()
    backend = MilvusVectorBackend(
        client,
        metric_by_collection={"docs": "cosine"},
    )

    collections = backend.list_collections()
    assert len(collections) == 1
    spec = collections[0]
    assert spec.name == "docs"
    assert spec.dimension == 3
    assert spec.metric == "cosine"
    assert spec.public_metadata == {"vector_field": "embedding"}
    assert [field.name for field in spec.metadata_fields] == ["tenant", "year"]

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=4,
        include_fields=("tenant", "year"),
    )
    assert rows == [
        {
            "id": 7,
            "score": 0.87,
            "tenant": "tenant-a",
            "year": 2026,
        }
    ]
    assert client.search_kwargs["collection_name"] == "docs"
    assert client.search_kwargs["data"] == [[0.1, 0.2, 0.3]]
    assert client.search_kwargs["anns_field"] == "embedding"
    assert client.search_kwargs["limit"] == 4
    assert client.search_kwargs["output_fields"] == ["tenant", "year"]


def test_milvus_adapter_uses_filter_templates_not_value_interpolation() -> None:
    client = FakeMilvusClient()
    backend = MilvusVectorBackend(client)

    backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=2,
        include_fields=("tenant",),
        filters={
            "tenant": "x' OR true",
            "year": (2025, 2026),
        },
    )

    expression = client.search_kwargs["filter"]
    params = client.search_kwargs["filter_params"]
    assert "x' OR true" not in expression
    assert expression == "tenant == {p0} AND year IN {p1}"
    assert params == {
        "p0": "x' OR true",
        "p1": [2025, 2026],
    }


def test_router_qdrant_convenience_registration_uses_native_backend() -> None:
    client = FakeQdrantClient()
    router = SchemaRouter()

    keys = router.add_qdrant_vector_store(
        client,
        lambda query: [0.1, 0.2, 0.3],
        database_name="qdrant",
        metadata_fields_by_collection={
            "docs": (
                VectorMetadataField(
                    name="title",
                    json_schema={"type": "string"},
                ),
            )
        },
        remote=False,
    )

    assert keys == ("qdrant.docs",)
    endpoint = router.registry.get("qdrant.docs").endpoint("search")
    assert endpoint.execution_metadata["dimension"] == 3
    assert endpoint.execution_metadata["metric"] == "cosine"


def test_router_milvus_convenience_registration_uses_native_backend() -> None:
    client = FakeMilvusClient()
    router = SchemaRouter()

    keys = router.add_milvus_vector_store(
        client,
        lambda query: [0.1, 0.2, 0.3],
        database_name="milvus",
        metric_by_collection={"docs": "cosine"},
        remote=False,
    )

    assert keys == ("milvus.docs",)
    endpoint = router.registry.get("milvus.docs").endpoint("search")
    assert endpoint.execution_metadata["dimension"] == 3
    assert endpoint.execution_metadata["metric"] == "cosine"


def test_milvus_multiple_vector_fields_require_explicit_selection() -> None:
    client = FakeMilvusClient()

    def describe(*, collection_name: str) -> dict[str, Any]:
        assert collection_name == "docs"
        return {
            "fields": [
                {"name": "text_vec", "params": {"dim": 3}},
                {"name": "image_vec", "params": {"dim": 4}},
            ]
        }

    client.describe_collection = describe  # type: ignore[method-assign]
    with pytest.raises(Exception, match="multiple vector fields"):
        MilvusVectorBackend(client).list_collections()

    backend = MilvusVectorBackend(
        client,
        vector_field_by_collection={"docs": "image_vec"},
    )
    spec = backend.list_collections()[0]
    assert spec.dimension == 4
    assert spec.public_metadata == {"vector_field": "image_vec"}


class _PineconeIndexList:
    def names(self) -> list[str]:
        return ["docs"]


class _PineconeIndex:
    def __init__(self) -> None:
        self.query_kwargs: dict[str, Any] = {}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_kwargs = dict(kwargs)
        return {
            "matches": [
                {
                    "id": "p1",
                    "score": 0.97,
                    "metadata": {
                        "title": "Router",
                        "tenant": "tenant-a",
                    },
                }
            ]
        }


class FakePineconeClient:
    def __init__(self) -> None:
        self.index = _PineconeIndex()

    def list_indexes(self) -> _PineconeIndexList:
        return _PineconeIndexList()

    def describe_index(self, name: str) -> dict[str, Any]:
        assert name == "docs"
        return {"name": "docs", "dimension": 3, "metric": "cosine"}

    def Index(self, name: str) -> _PineconeIndex:  # noqa: N802
        assert name == "docs"
        return self.index


def test_pinecone_adapter_discovers_index_and_normalizes_query() -> None:
    client = FakePineconeClient()
    backend = PineconeVectorBackend(
        client,
        metadata_fields_by_index={
            "docs": (
                VectorMetadataField(
                    name="title",
                    json_schema={"type": "string"},
                ),
                VectorMetadataField(
                    name="tenant",
                    json_schema={"type": "string"},
                    filterable=True,
                ),
            )
        },
    )

    spec = backend.list_collections()[0]
    assert spec.name == "docs"
    assert spec.dimension == 3
    assert spec.metric == "cosine"

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=4,
        include_fields=("title",),
        filters={"tenant": ("tenant-a", "tenant-b")},
    )
    assert rows == [{"id": "p1", "score": 0.97, "title": "Router"}]
    assert client.index.query_kwargs["filter"] == {
        "tenant": {"$in": ["tenant-a", "tenant-b"]}
    }


@dataclass
class _ChromaCollection:
    name: str = "docs"
    metadata: dict[str, Any] | None = None

    def peek(self, *, limit: int) -> dict[str, Any]:
        assert limit == 1
        return {"embeddings": [[0.1, 0.2, 0.3]]}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["n_results"] == 2
        self.query_kwargs = dict(kwargs)
        return {
            "ids": [["c1"]],
            "distances": [[0.11]],
            "metadatas": [[{"title": "Router", "tenant": "tenant-a"}]],
            "documents": [["typed routing"]],
        }


class FakeChromaClient:
    def __init__(self) -> None:
        self.collection = _ChromaCollection(
            metadata={"hnsw:space": "cosine"}
        )

    def list_collections(self) -> list[_ChromaCollection]:
        return [self.collection]

    def get_collection(self, *, name: str) -> _ChromaCollection:
        assert name == "docs"
        return self.collection


def test_chroma_adapter_infers_dimension_and_normalizes_query() -> None:
    client = FakeChromaClient()
    backend = ChromaVectorBackend(
        client,
        metadata_fields_by_collection={
            "docs": (
                VectorMetadataField(
                    name="title",
                    json_schema={"type": "string"},
                ),
                VectorMetadataField(
                    name="tenant",
                    json_schema={"type": "string"},
                    filterable=True,
                ),
                VectorMetadataField(
                    name="document",
                    json_schema={"type": "string"},
                ),
            )
        },
    )
    spec = backend.list_collections()[0]
    assert spec.dimension == 3
    assert spec.metric == "cosine"

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=2,
        include_fields=("title", "document"),
        filters={
            "tenant": ("tenant-a", "tenant-b"),
            "year": 2026,
        },
    )
    assert rows == [
        {
            "id": "c1",
            "score": 0.11,
            "title": "Router",
            "document": "typed routing",
        }
    ]
    assert client.collection.query_kwargs["where"] == {
        "$and": [
            {"tenant": {"$in": ["tenant-a", "tenant-b"]}},
            {"year": 2026},
        ]
    }


@dataclass
class _WeaviateProperty:
    name: str
    data_type: list[str]


@dataclass
class _WeaviateConfig:
    properties: list[_WeaviateProperty]


@dataclass
class _WeaviateMetadata:
    distance: float


@dataclass
class _WeaviateObject:
    uuid: str
    properties: dict[str, Any]
    metadata: _WeaviateMetadata


@dataclass
class _WeaviateResponse:
    objects: list[_WeaviateObject]


class _WeaviateQuery:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def near_vector(self, **kwargs: Any) -> _WeaviateResponse:
        self.kwargs = dict(kwargs)
        return _WeaviateResponse(
            [
                _WeaviateObject(
                    uuid="w1",
                    properties={"title": "Router", "tenant": "tenant-a"},
                    metadata=_WeaviateMetadata(distance=0.08),
                )
            ]
        )


class _WeaviateCollection:
    def __init__(self) -> None:
        self.query = _WeaviateQuery()

        class _Config:
            @staticmethod
            def get() -> _WeaviateConfig:
                return _WeaviateConfig(
                    properties=[
                        _WeaviateProperty("title", ["text"]),
                        _WeaviateProperty("tenant", ["text"]),
                    ]
                )

        self.config = _Config()


class _WeaviateCollections:
    def __init__(self) -> None:
        self.collection = _WeaviateCollection()

    def list_all(self, *, simple: bool = False) -> dict[str, Any]:
        assert simple is False
        return {"Docs": {}}

    def get(self, name: str) -> _WeaviateCollection:
        assert name == "Docs"
        return self.collection


class FakeWeaviateClient:
    def __init__(self) -> None:
        self.collections = _WeaviateCollections()


def test_weaviate_adapter_discovers_properties_and_uses_target_vector() -> None:
    client = FakeWeaviateClient()
    backend = WeaviateVectorBackend(
        client,
        dimension_by_collection={"Docs": 3},
        vector_name_by_collection={"Docs": "title_vec"},
        metric_by_collection={"Docs": "cosine"},
        filter_builder=lambda filters: {"trusted": dict(filters)},
    )

    spec = backend.list_collections()[0]
    assert spec.dimension == 3
    assert spec.public_metadata == {"vector_name": "title_vec"}
    assert [field.name for field in spec.metadata_fields] == ["title", "tenant"]

    rows = backend.search(
        collection="Docs",
        vector=[0.1, 0.2, 0.3],
        top_k=3,
        include_fields=("title",),
        filters={"tenant": "tenant-a"},
    )
    assert rows == [{"id": "w1", "score": 0.08, "title": "Router"}]
    kwargs = client.collections.collection.query.kwargs
    assert kwargs["target_vector"] == "title_vec"
    assert kwargs["filters"] == {"trusted": {"tenant": "tenant-a"}}


def test_pgvector_dimension_contract_reads_reflected_type_dimension() -> None:
    class _Type:
        dim = 3

    class _Column:
        type = _Type()

    assert PgvectorVectorBackend._dimension(_Column()) == 3


def test_router_remaining_native_vector_registration_helpers() -> None:
    pinecone = SchemaRouter()
    pinecone_keys = pinecone.add_pinecone_vector_store(
        FakePineconeClient(),
        lambda _query: [0.1, 0.2, 0.3],
        metadata_fields_by_index={
            "docs": (
                VectorMetadataField(
                    name="title",
                    json_schema={"type": "string"},
                ),
            )
        },
        remote=False,
    )
    assert pinecone_keys == ("pinecone.docs",)

    chroma = SchemaRouter()
    chroma_keys = chroma.add_chroma_vector_store(
        FakeChromaClient(),
        lambda _query: [0.1, 0.2, 0.3],
        remote=False,
    )
    assert chroma_keys == ("chroma.docs",)

    weaviate = SchemaRouter()
    weaviate_keys = weaviate.add_weaviate_vector_store(
        FakeWeaviateClient(),
        lambda _query: [0.1, 0.2, 0.3],
        dimension_by_collection={"Docs": 3},
        remote=False,
    )
    assert weaviate_keys == ("weaviate.docs",)

