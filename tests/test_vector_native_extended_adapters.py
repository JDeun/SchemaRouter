from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from schemarouter import (
    ChromaVectorBackend,
    PgVectorBackend,
    PineconeVectorBackend,
    SchemaRouter,
    VectorMetadataField,
    WeaviateVectorBackend,
)


@dataclass
class _PineconeDescription:
    dimension: int
    metric: str


@dataclass
class _PineconeMatch:
    id: str
    score: float
    metadata: dict[str, Any]


@dataclass
class _PineconeResult:
    matches: list[_PineconeMatch]


class _PineconeIndex:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def query(self, **kwargs: Any) -> _PineconeResult:
        self.kwargs = dict(kwargs)
        return _PineconeResult(
            [_PineconeMatch("p1", 0.93, {"tenant": "a", "title": "Router"})]
        )


class FakePineconeClient:
    def __init__(self) -> None:
        self.index = _PineconeIndex()

    def list_indexes(self) -> list[dict[str, str]]:
        return [{"name": "docs"}]

    def describe_index(self, name: str) -> _PineconeDescription:
        assert name == "docs"
        return _PineconeDescription(dimension=3, metric="cosine")

    def Index(self, name: str) -> _PineconeIndex:  # noqa: N802
        assert name == "docs"
        return self.index


def test_pinecone_adapter_discovers_and_bounds_query() -> None:
    client = FakePineconeClient()
    backend = PineconeVectorBackend(
        client,
        metadata_fields_by_index={
            "docs": (
                VectorMetadataField(
                    name="tenant",
                    json_schema={"type": "string"},
                    filterable=True,
                ),
                VectorMetadataField(name="title", json_schema={"type": "string"}),
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
        filters={"tenant": "a"},
    )
    assert rows == [{"id": "p1", "score": 0.93, "title": "Router"}]
    assert client.index.kwargs["filter"] == {"tenant": {"$eq": "a"}}
    assert client.index.kwargs["include_values"] is False


class _WeaviateQuery:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def near_vector(self, **kwargs: Any) -> Any:
        self.kwargs = dict(kwargs)
        return type(
            "Response",
            (),
            {
                "objects": [
                    type(
                        "Object",
                        (),
                        {
                            "uuid": "w1",
                            "properties": {"tenant": "a", "title": "Router"},
                            "metadata": type("Metadata", (), {"certainty": 0.91})(),
                        },
                    )()
                ]
            },
        )()


class _WeaviateCollection:
    def __init__(self) -> None:
        self.query = _WeaviateQuery()


class _WeaviateCollections:
    def __init__(self) -> None:
        self.collection = _WeaviateCollection()

    def list_all(self, *, simple: bool) -> dict[str, Any]:
        assert simple is False
        return {
            "docs": {
                "properties": [
                    {"name": "tenant", "data_type": "text"},
                    {"name": "title", "data_type": "text"},
                ]
            }
        }

    def get(self, name: str) -> _WeaviateCollection:
        assert name == "docs"
        return self.collection


class FakeWeaviateClient:
    def __init__(self) -> None:
        self.collections = _WeaviateCollections()


def test_weaviate_adapter_requires_explicit_dimension_and_uses_trusted_filter() -> None:
    client = FakeWeaviateClient()
    built: list[dict[str, Any]] = []
    backend = WeaviateVectorBackend(
        client,
        dimension_by_collection={"docs": 3},
        metric_by_collection={"docs": "cosine"},
        filter_builder=lambda values: built.append(dict(values)) or {"trusted": values},
        metadata_query_factory=lambda: "metadata",
    )

    spec = backend.list_collections()[0]
    assert spec.dimension == 3
    assert [field.name for field in spec.metadata_fields] == ["tenant", "title"]

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=2,
        include_fields=("title",),
        filters={"tenant": "a"},
    )
    assert rows == [{"id": "w1", "score": 0.91, "title": "Router"}]
    assert built == [{"tenant": "a"}]
    kwargs = client.collections.collection.query.kwargs
    assert kwargs["filters"] == {"trusted": {"tenant": "a"}}
    assert kwargs["return_metadata"] == "metadata"


class FakeChromaCollection:
    def __init__(self) -> None:
        self.name = "docs"
        self.metadata = {"dimension": 3, "hnsw:space": "cosine"}
        self.kwargs: dict[str, Any] = {}

    def peek(self, *, limit: int) -> dict[str, Any]:
        assert limit == 1
        return {"metadatas": [{"tenant": "a", "year": 2026}]}

    def query(self, **kwargs: Any) -> dict[str, Any]:
        self.kwargs = dict(kwargs)
        return {
            "ids": [["c1"]],
            "distances": [[0.08]],
            "metadatas": [[{"tenant": "a", "year": 2026}]],
        }


class FakeChromaClient:
    def __init__(self) -> None:
        self.collection = FakeChromaCollection()

    def list_collections(self) -> list[FakeChromaCollection]:
        return [self.collection]

    def get_collection(self, *, name: str) -> FakeChromaCollection:
        assert name == "docs"
        return self.collection


def test_chroma_adapter_infers_metadata_and_builds_bounded_where() -> None:
    client = FakeChromaClient()
    backend = ChromaVectorBackend(client)
    spec = backend.list_collections()[0]
    assert spec.dimension == 3
    assert spec.metric == "cosine"
    assert [field.name for field in spec.metadata_fields] == ["tenant", "year"]

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=3,
        include_fields=("year",),
        filters={"tenant": ("a", "b")},
    )
    assert rows == [{"id": "c1", "score": 0.08, "year": 2026}]
    assert client.collection.kwargs["where"] == {
        "tenant": {"$in": ["a", "b"]}
    }


class Vector:
    def __init__(self, dim: int) -> None:
        self.dim = dim


class TextType:
    python_type = str


class _Expr:
    def label(self, name: str) -> _Expr:
        assert name == "_schemarouter_score"
        return self


class _Column:
    def __init__(self, name: str, column_type: Any) -> None:
        self.name = name
        self.type = column_type

    def cosine_distance(self, vector: list[float]) -> _Expr:
        assert vector == [0.1, 0.2, 0.3]
        return _Expr()

    def __eq__(self, value: object) -> tuple[str, str, object]:  # type: ignore[override]
        return ("eq", self.name, value)

    def in_(self, values: list[object]) -> tuple[str, str, list[object]]:
        return ("in", self.name, values)


class _Columns:
    def __init__(self, columns: list[_Column]) -> None:
        self._columns = columns
        self._by_name = {column.name: column for column in columns}

    def __iter__(self):
        return iter(self._columns)

    def __getitem__(self, name: str) -> _Column:
        return self._by_name[name]

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._by_name

    def get(self, name: str) -> _Column | None:
        return self._by_name.get(name)


class _Table:
    def __init__(self) -> None:
        self.name = "docs"
        self.columns = _Columns(
            [
                _Column("id", TextType()),
                _Column("embedding", Vector(3)),
                _Column("tenant", TextType()),
                _Column("title", TextType()),
            ]
        )
        self.primary_key = type("PrimaryKey", (), {"columns": [self.columns["id"]]})()


class _Statement:
    def __init__(self) -> None:
        self.filters: list[Any] = []
        self.top_k: int | None = None

    def order_by(self, value: Any) -> _Statement:
        return self

    def limit(self, value: int) -> _Statement:
        self.top_k = value
        return self

    def where(self, value: Any) -> _Statement:
        self.filters.append(value)
        return self


class _Rows:
    def mappings(self) -> _Rows:
        return self

    def all(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "p1",
                "tenant": "a",
                "title": "Router",
                "_schemarouter_score": 0.04,
            }
        ]


class _Connection:
    def __init__(self, engine: FakePgEngine) -> None:
        self.engine = engine

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def execute(self, statement: _Statement) -> _Rows:
        self.engine.statement = statement
        return _Rows()


class FakePgEngine:
    def __init__(self) -> None:
        self.statement: _Statement | None = None

    def connect(self) -> _Connection:
        return _Connection(self)


class _Inspector:
    def get_table_names(self, *, schema: str | None) -> list[str]:
        assert schema is None
        return ["docs"]


class FakeSQLAlchemy:
    def __init__(self) -> None:
        self.table = _Table()

    def inspect(self, engine: Any) -> _Inspector:
        return _Inspector()

    def MetaData(self) -> object:  # noqa: N802
        return object()

    def Table(self, *args: Any, **kwargs: Any) -> _Table:  # noqa: N802
        return self.table

    def select(self, *columns: Any) -> _Statement:
        return _Statement()


def test_pgvector_adapter_reflects_dimension_and_uses_sqlalchemy_expressions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = FakePgEngine()
    backend = PgVectorBackend(engine)
    fake_sa = FakeSQLAlchemy()
    monkeypatch.setattr(backend, "_sqlalchemy", lambda: fake_sa)

    spec = backend.list_collections()[0]
    assert spec.name == "docs"
    assert spec.dimension == 3
    assert spec.metric == "cosine"
    assert [field.name for field in spec.metadata_fields] == ["tenant", "title"]

    rows = backend.search(
        collection="docs",
        vector=[0.1, 0.2, 0.3],
        top_k=5,
        include_fields=("title",),
        filters={"tenant": "a"},
    )
    assert rows == [{"id": "p1", "score": 0.04, "title": "Router"}]
    assert engine.statement is not None
    assert engine.statement.top_k == 5
    assert engine.statement.filters == [("eq", "tenant", "a")]


def test_router_extended_vector_helpers_register_capabilities() -> None:
    pinecone = FakePineconeClient()
    router = SchemaRouter()
    keys = router.add_pinecone_vector_store(
        pinecone,
        lambda query: [0.1, 0.2, 0.3],
        metadata_fields_by_index={
            "docs": (VectorMetadataField(name="title"),)
        },
        remote=False,
    )
    assert keys == ("pinecone.docs",)
