from __future__ import annotations

from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
    TrustedFilterBinding,
)
from schemarouter.adapters.discovery_limits import NativeDiscoveryLimits
from schemarouter.adapters.record_native import (
    DynamoDBRecordBackend,
    MongoRecordBackend,
)
from schemarouter.errors import RegistrationError


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    fields: list[str],
    arguments: dict[str, object] | None = None,
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("query")
    return ExecutionPlan(
        query=f"query {tool_key}",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=arguments or {},
                fields=fields,
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


class FakeMongoCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def sort(self, field: str, direction: int) -> FakeMongoCursor:
        assert direction == 1
        self._rows = sorted(self._rows, key=lambda row: str(row.get(field, "")))
        return self

    def max_time_ms(self, value: int) -> FakeMongoCursor:
        assert value > 0
        return self

    def limit(self, value: int) -> FakeMongoCursor:
        self._rows = self._rows[:value]
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeMongoCollection:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], dict[str, int]]] = []
        self.row = {
            "_id": "doc-1",
            "title": "Routing",
            "department": "engineering",
            "body": "typed capability retrieval",
        }

    def find_one(self, query: dict[str, Any]) -> dict[str, Any]:
        assert query == {}
        return dict(self.row)

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> FakeMongoCursor:
        if projection is None:
            assert query == {}
            return FakeMongoCursor([dict(self.row)])
        self.calls.append((dict(query), dict(projection)))
        row = {
            key: value
            for key, value in self.row.items()
            if projection.get(key) == 1
        }
        return FakeMongoCursor([row])


class FakeMongoDatabase:
    def __init__(self) -> None:
        self.collections = {"documents": FakeMongoCollection()}

    def list_collection_names(self) -> list[str]:
        return ["documents"]

    def __getitem__(self, name: str) -> FakeMongoCollection:
        return self.collections[name]


@pytest.mark.asyncio
async def test_mongodb_native_adapter_discovers_and_executes_bounded_find() -> None:
    database = FakeMongoDatabase()
    router = SchemaRouter()
    keys = await router.aadd_mongodb_record_store(
        database,
        database_name="mongo",
        text_search_collections=["documents"],
        remote=False,
    )
    assert keys == ("mongo.documents",)

    endpoint = router.registry.get("mongo.documents").endpoint("query")
    assert endpoint.metadata["record_model"] == "document"
    assert {field.name for field in endpoint.output_fields} >= {
        "_id",
        "title",
        "department",
    }

    result = await router.execute(
        _plan(
            router,
            "mongo.documents",
            fields=["_id", "title"],
            arguments={
                "query": "routing",
                "filter__department": "engineering",
                "limit": 5,
            },
        )
    )
    assert result[0].data == [{"_id": "doc-1", "title": "Routing"}]
    query, projection = database.collections["documents"].calls[-1]
    assert query == {
        "department": "engineering",
        "$text": {"$search": "routing"},
    }
    assert projection == {"_id": 1, "title": 1}


class FakeIndices:
    def get_mapping(self, index: str | None = None) -> dict[str, Any]:
        assert index in {None, "logs"}
        return {
            "logs": {
                "mappings": {
                    "properties": {
                        "@timestamp": {"type": "date"},
                        "message": {"type": "text"},
                        "service": {"type": "keyword"},
                        "status": {"type": "integer"},
                    }
                }
            }
        }


class FakeElasticClient:
    def __init__(self) -> None:
        self.indices = FakeIndices()
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        return {
            "hits": {
                "hits": [
                    {
                        "_id": "log-1",
                        "_source": {
                            "@timestamp": "2026-10-04T00:00:00Z",
                            "message": "router healthy",
                            "service": "router",
                            "status": 200,
                        },
                    }
                ]
            }
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "database_name", "vendor"),
    [
        ("aadd_elasticsearch_record_store", "elastic", "elasticsearch"),
        ("aadd_opensearch_record_store", "opensearch", "opensearch"),
    ],
)
async def test_elastic_and_opensearch_native_mapping_and_query(
    method: str,
    database_name: str,
    vendor: str,
) -> None:
    client = FakeElasticClient()
    router = SchemaRouter()
    register = getattr(router, method)
    keys = await register(
        client,
        database_name=database_name,
        indices=["logs"],
        remote=False,
    )
    assert keys == (f"{database_name}.logs",)
    endpoint = router.registry.get(f"{database_name}.logs").endpoint("query")
    assert endpoint.metadata["public_metadata"]["vendor"] == vendor

    result = await router.execute(
        _plan(
            router,
            f"{database_name}.logs",
            fields=["_id", "message", "status"],
            arguments={
                "query": "healthy",
                "filter__service": "router",
                "start_time": "2026-10-03T00:00:00Z",
                "end_time": "2026-10-05T00:00:00Z",
                "limit": 3,
            },
        )
    )
    assert result[0].data == [
        {"_id": "log-1", "message": "router healthy", "status": 200}
    ]
    call = client.calls[-1]
    assert call["index"] == "logs"
    assert call["size"] == 3
    assert call["source"] == ["message", "status"]
    query = call["query"]
    assert query["bool"]["must"][0]["multi_match"]["query"] == "healthy"
    assert {"term": {"service": "router"}} in query["bool"]["filter"]
    assert any("range" in item for item in query["bool"]["filter"])


class FakeDynamoClient:
    def __init__(self) -> None:
        self.scan_calls: list[dict[str, Any]] = []

    def list_tables(self, **kwargs: Any) -> dict[str, Any]:
        assert kwargs == {}
        return {"TableNames": ["documents"]}

    def describe_table(self, *, TableName: str) -> dict[str, Any]:
        assert TableName == "documents"
        return {
            "Table": {
                "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
                "AttributeDefinitions": [
                    {"AttributeName": "id", "AttributeType": "S"}
                ],
            }
        }

    def scan(self, **kwargs: Any) -> dict[str, Any]:
        self.scan_calls.append(dict(kwargs))
        if kwargs == {"TableName": "documents", "Limit": 1}:
            return {
                "Items": [
                    {
                        "id": {"S": "doc-1"},
                        "department": {"S": "engineering"},
                        "title": {"S": "Router design"},
                    }
                ]
            }
        return {
            "Items": [
                {
                    "id": {"S": "doc-1"},
                    "department": {"S": "engineering"},
                    "title": {"S": "Router design"},
                }
            ]
        }


@pytest.mark.asyncio
async def test_dynamodb_native_adapter_builds_only_parameterized_scan_expressions() -> None:
    client = FakeDynamoClient()
    router = SchemaRouter()
    keys = await router.aadd_dynamodb_record_store(
        client,
        database_name="ddb",
        tables=["documents"],
        remote=False,
    )
    assert keys == ("ddb.documents",)

    result = await router.execute(
        _plan(
            router,
            "ddb.documents",
            fields=["id", "title"],
            arguments={
                "filter__department": "engineering",
                "limit": 7,
            },
        )
    )
    assert result[0].data == [{"id": "doc-1", "title": "Router design"}]
    call = client.scan_calls[-1]
    assert call["TableName"] == "documents"
    assert call["Limit"] == 7
    assert "FilterExpression" in call
    assert "ProjectionExpression" in call
    assert call["ExpressionAttributeValues"] == {":v0": {"S": "engineering"}}


@pytest.mark.asyncio
async def test_native_record_backend_receives_hidden_principal_filter() -> None:
    database = FakeMongoDatabase()
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="mongo.documents.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="mongo.documents.*",
                roles_any=("employee",),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="department",
                        principal_value="department",
                    ),
                ),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_mongodb_record_store(
        database,
        database_name="mongo",
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        departments=("engineering",),
    )

    result = await router.execute(
        _plan(
            router,
            "mongo.documents",
            fields=["_id", "title"],
        ),
        config=RunConfig(principal=principal),
    )
    assert result[0].data == [{"_id": "doc-1", "title": "Routing"}]
    query, _projection = database.collections["documents"].calls[-1]
    assert query["department"] == {"$in": ["engineering"]}

class FakeHeterogeneousMongoCollection(FakeMongoCollection):
    def __init__(self) -> None:
        super().__init__()
        self.rows = [
            {"_id": "doc-1", "kind": "primary", "value": 1},
            {"_id": "doc-2", "kind": "secondary", "value": "mixed", "extra": True},
        ]

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> FakeMongoCursor:
        if projection is not None:
            return super().find(query, projection)
        assert query == {}
        return FakeMongoCursor([dict(row) for row in self.rows])


@pytest.mark.asyncio
async def test_mongodb_schema_discovery_merges_bounded_heterogeneous_samples() -> None:
    database = FakeMongoDatabase()
    collection = FakeHeterogeneousMongoCollection()
    database.collections["documents"] = collection
    router = SchemaRouter()

    await router.aadd_mongodb_record_store(
        database,
        database_name="mongo_heterogeneous",
        remote=False,
    )

    endpoint = router.registry.get("mongo_heterogeneous.documents").endpoint("query")
    fields = {field.name: field for field in endpoint.output_fields}
    assert set(fields) >= {"_id", "kind", "value", "extra"}
    assert fields["value"].json_schema == {}
    assert fields["extra"].json_schema == {}
    discovery = endpoint.metadata["public_metadata"]["schema_discovery"]
    assert discovery["mode"] == "bounded_sample"
    assert discovery["partial"] is True
    assert discovery["row_limit"] == 16


class FakeHeterogeneousDynamoClient(FakeDynamoClient):
    def scan(self, **kwargs: Any) -> dict[str, Any]:
        self.scan_calls.append(dict(kwargs))
        if kwargs == {"TableName": "documents", "Limit": 16}:
            return {
                "Items": [
                    {
                        "id": {"S": "doc-1"},
                        "value": {"N": "1"},
                    },
                    {
                        "id": {"S": "doc-2"},
                        "value": {"S": "mixed"},
                        "extra": {"BOOL": True},
                    },
                ]
            }
        return {
            "Items": [
                {
                    "id": {"S": "doc-1"},
                    "value": {"N": "1"},
                }
            ]
        }


@pytest.mark.asyncio
async def test_dynamodb_schema_discovery_merges_samples_and_only_trusts_metadata_types() -> None:
    client = FakeHeterogeneousDynamoClient()
    router = SchemaRouter()

    await router.aadd_dynamodb_record_store(
        client,
        database_name="ddb_heterogeneous",
        tables=["documents"],
        remote=False,
    )

    endpoint = router.registry.get("ddb_heterogeneous.documents").endpoint("query")
    fields = {field.name: field for field in endpoint.output_fields}
    assert set(fields) >= {"id", "value", "extra"}
    assert fields["id"].json_schema == {"type": "string"}
    assert fields["value"].json_schema == {}
    assert fields["extra"].json_schema == {}
    discovery = endpoint.metadata["public_metadata"]["schema_discovery"]
    assert discovery["partial"] is True
    assert client.scan_calls[0] == {"TableName": "documents", "Limit": 16}



class _CatalogForbiddenMongoDatabase(FakeMongoDatabase):
    def list_collection_names(self) -> list[str]:
        raise AssertionError("explicit collection selection must bypass full catalog discovery")


def test_mongodb_explicit_selection_bypasses_catalog_enumeration() -> None:
    database = _CatalogForbiddenMongoDatabase()
    backend = MongoRecordBackend(
        database,
        collections=["documents"],
        discovery_limits=NativeDiscoveryLimits(max_sources=1),
    )

    sources = backend.list_sources()

    assert [source.name for source in sources] == ["documents"]


class _PagedDynamoDiscoveryClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def list_tables(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        assert kwargs["Limit"] == 2
        return {
            "TableNames": ["one", "two"],
            "LastEvaluatedTableName": "two",
        }


def test_dynamodb_catalog_budget_requests_only_limit_plus_one() -> None:
    client = _PagedDynamoDiscoveryClient()
    backend = DynamoDBRecordBackend(
        client,
        discovery_limits=NativeDiscoveryLimits(max_sources=1),
    )

    with pytest.raises(RegistrationError, match="DynamoDB table count"):
        backend.list_sources()

    assert client.calls == [{"Limit": 2}]
