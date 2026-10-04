from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from schemarouter import SchemaRouter, VectorMetadataField
from schemarouter.adapters.vector_native import (
    MilvusVectorBackend,
    PineconeVectorBackend,
    QdrantVectorBackend,
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


class _PineconeIndex:
    def __init__(self) -> None:
        self.query_kwargs: dict[str, Any] = {}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.query_kwargs = dict(kwargs)
        return {
            "matches": [
                {
                    "id": "pc-1",
                    "score": 0.95,
                    "metadata": {
                        "title": "Pinecone",
                        "tenant": "tenant-a",
                    },
                }
            ]
        }


class _PineconeIndexList:
    def names(self) -> list[str]:
        return ["docs"]


class FakePineconeClient:
    def __init__(self) -> None:
        self.index = _PineconeIndex()
        self.index_args: list[dict[str, Any]] = []

    def list_indexes(self) -> _PineconeIndexList:
        return _PineconeIndexList()

    def describe_index(self, *, name: str) -> dict[str, Any]:
        assert name == "docs"
        return {
            "name": "docs",
            "dimension": 3,
            "metric": "cosine",
            "vector_type": "dense",
            "host": "docs.example.svc.pinecone.io",
        }

    def Index(self, **kwargs: Any) -> _PineconeIndex:  # noqa: N802
        self.index_args.append(dict(kwargs))
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
        namespace_by_index={"docs": "production"},
    )

    collections = backend.list_collections()
    assert len(collections) == 1
    spec = collections[0]
    assert spec.name == "docs"
    assert spec.dimension == 3
    assert spec.metric == "cosine"
    assert spec.public_metadata == {"namespace": "production"}

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=4,
        include_fields=("title",),
        filters={"tenant": "tenant-a"},
    )
    assert rows == [
        {
            "id": "pc-1",
            "score": 0.95,
            "title": "Pinecone",
        }
    ]
    assert client.index_args == [{"host": "docs.example.svc.pinecone.io"}]
    assert client.index.query_kwargs == {
        "vector": [0.1, 0.2, 0.3],
        "top_k": 4,
        "include_metadata": True,
        "include_values": False,
        "namespace": "production",
        "filter": {"tenant": "tenant-a"},
    }


def test_pinecone_requires_explicit_metadata_contract() -> None:
    client = FakePineconeClient()
    backend = PineconeVectorBackend(client)

    with pytest.raises(Exception, match="undeclared metadata fields"):
        backend.search(
            collection="docs",
            vector=[0.1, 0.2, 0.3],
            top_k=2,
            include_fields=("title",),
        )


def test_router_pinecone_convenience_registration_uses_native_backend() -> None:
    client = FakePineconeClient()
    router = SchemaRouter()

    keys = router.add_pinecone_vector_store(
        client,
        lambda query: [0.1, 0.2, 0.3],
        database_name="pinecone",
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

    assert keys == ("pinecone.docs",)
    endpoint = router.registry.get("pinecone.docs").endpoint("search")
    assert endpoint.execution_metadata["dimension"] == 3
    assert endpoint.execution_metadata["metric"] == "cosine"


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
