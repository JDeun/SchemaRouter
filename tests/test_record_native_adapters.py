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

    def limit(self, value: int) -> FakeMongoCursor:
        self._rows = self._rows[:value]
        return self

    def __iter__(self):
        return iter(self._rows)


class FakeMongoCollection:
    def __init__(self) -> None:
        self.calls: list[
            tuple[dict[str, Any], dict[str, int] | None]
        ] = []
        self.row = {
            "_id": "doc-1",
            "title": "Routing",
            "department": "engineering",
            "body": "typed capability retrieval",
        }
        self.rows = [self.row]

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> FakeMongoCursor:
        copied_projection = None if projection is None else dict(projection)
        self.calls.append((dict(query), copied_projection))
        if projection is None:
            return FakeMongoCursor([dict(row) for row in self.rows])
        rows = [
            {
                key: value
                for key, value in row.items()
                if projection.get(key) == 1
            }
            for row in self.rows
        ]
        return FakeMongoCursor(rows)


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


@pytest.mark.asyncio
async def test_mongodb_schema_discovery_merges_heterogeneous_bounded_samples() -> None:
    database = FakeMongoDatabase()
    database.collections["documents"].rows = [
        {
            "_id": "doc-1",
            "title": "Routing",
            "score": 1,
        },
        {
            "_id": "doc-2",
            "title": "Schemas",
            "department": "research",
            "score": "high",
        },
    ]
    router = SchemaRouter()
    await router.aadd_mongodb_record_store(
        database,
        database_name="mongo",
        remote=False,
    )

    endpoint = router.registry.get("mongo.documents").endpoint("query")
    fields = {field.name: field for field in endpoint.output_fields}
    assert set(fields) >= {"_id", "title", "department", "score"}
    assert fields["title"].json_schema == {"type": "string"}
    assert fields["department"].json_schema == {}
    assert fields["score"].json_schema == {}
    discovery = endpoint.metadata["public_metadata"]["schema_discovery"]
    assert discovery["complete"] is False
    assert discovery["sample_count"] == 2
    assert discovery["sample_limit"] == 16


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
        self.discovery_items = [
            {
                "id": {"S": "doc-1"},
                "department": {"S": "engineering"},
                "title": {"S": "Router design"},
            }
        ]

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
        if kwargs == {"TableName": "documents", "Limit": 16}:
            return {"Items": list(self.discovery_items)}
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
async def test_dynamodb_schema_discovery_merges_heterogeneous_bounded_samples() -> None:
    client = FakeDynamoClient()
    client.discovery_items = [
        {
            "id": {"S": "doc-1"},
            "title": {"S": "Router"},
            "score": {"N": "1"},
        },
        {
            "id": {"S": "doc-2"},
            "title": {"S": "Schemas"},
            "department": {"S": "research"},
            "score": {"S": "high"},
        },
    ]
    router = SchemaRouter()
    await router.aadd_dynamodb_record_store(
        client,
        database_name="ddb",
        tables=["documents"],
        remote=False,
    )

    endpoint = router.registry.get("ddb.documents").endpoint("query")
    fields = {field.name: field for field in endpoint.output_fields}
    assert set(fields) >= {"id", "title", "department", "score"}
    assert fields["id"].json_schema == {"type": "string"}
    assert fields["title"].json_schema == {"type": "string"}
    assert fields["department"].json_schema == {}
    assert fields["score"].json_schema == {}
    discovery = endpoint.metadata["public_metadata"]["schema_discovery"]
    assert discovery["complete"] is False
    assert discovery["sample_count"] == 2
    assert client.scan_calls[0] == {"TableName": "documents", "Limit": 16}


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
