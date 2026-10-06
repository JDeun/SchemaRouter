from __future__ import annotations

import json
from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    NeptuneOpenCypherBackend,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
    TrustedFilterBinding,
)
from schemarouter.adapters.graph_native import (
    ArangoGraphBackend,
    Neo4jGraphBackend,
    SparqlGraphBackend,
)
from schemarouter.errors import RegistrationError


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    start_id: str,
    relationship_types: list[str],
    fields: list[str] | None = None,
    max_hops: int = 1,
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("traverse")
    return ExecutionPlan(
        query=f"traverse {tool_key}",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={
                    "start_id": start_id,
                    "relationship_types": relationship_types,
                    "max_hops": max_hops,
                    "limit": 10,
                },
                fields=fields
                or ["source_id", "target_id", "relationship", "depth"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


class FakeNeo4jDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_query(self, query: str, **kwargs: Any):
        self.calls.append((query, dict(kwargs)))
        if "CALL db.labels()" in query:
            return ([{"label": "Person"}, {"label": "Team"}], None, ["label"])
        if "CALL db.relationshipTypes()" in query:
            return (
                [
                    {"relationshipType": "MEMBER_OF"},
                    {"relationshipType": "REPORTS_TO"},
                ],
                None,
                ["relationshipType"],
            )
        return (
            [
                {
                    "source_id": "person-1",
                    "target_id": "team-1",
                    "relationship": "MEMBER_OF",
                    "depth": 1,
                    "source_type": "Person",
                    "target_type": "Team",
                }
            ],
            None,
            [],
        )


@pytest.mark.asyncio
async def test_neo4j_native_adapter_discovers_and_executes_parameterized_traversal() -> None:
    driver = FakeNeo4jDriver()
    router = SchemaRouter()
    keys = await router.aadd_neo4j_graph(
        driver,
        database="neo4j",
        graph_name="org",
        remote=False,
    )

    assert keys == ("neo4j.org",)
    tool = router.registry.get("neo4j.org")
    endpoint = tool.endpoint("traverse")
    assert endpoint.metadata["graph_model"] == "property_graph"
    assert {item.name for item in tool.endpoint("traverse").output_fields} >= {
        "source_id",
        "target_id",
        "relationship",
    }

    result = await router.execute(
        _plan(
            router,
            "neo4j.org",
            start_id="person-1",
            relationship_types=["MEMBER_OF"],
        )
    )
    assert result[0].data[0]["target_id"] == "team-1"

    traversal_query, kwargs = driver.calls[-1]
    assert "elementId(start) = $start_id" in traversal_query
    assert "MEMBER_OF" in traversal_query
    assert kwargs["parameters_"] == {"start_id": "person-1", "limit": 10}
    assert kwargs["database_"] == "neo4j"


class FakeNeptuneDataClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def execute_open_cypher_query(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        query = kwargs["openCypherQuery"]
        if "UNWIND labels" in query:
            return {"results": [{"label": "Person"}]}
        if "DISTINCT type(r)" in query:
            return {"results": [{"relationshipType": "KNOWS"}]}
        return {
            "results": [
                {
                    "source_id": "p1",
                    "target_id": "p2",
                    "relationship": "KNOWS",
                    "depth": 1,
                    "source_type": "Person",
                    "target_type": "Person",
                }
            ]
        }


@pytest.mark.asyncio
async def test_neptune_database_adapter_uses_json_parameter_payload() -> None:
    client = FakeNeptuneDataClient()
    router = SchemaRouter()
    keys = await router.aadd_neptune_graph(
        client,
        graph_name="social",
        database_name="neptune",
        remote=False,
    )
    assert keys == ("neptune.social",)

    result = await router.execute(
        _plan(
            router,
            "neptune.social",
            start_id="p1",
            relationship_types=["KNOWS"],
        )
    )
    assert result[0].data[0]["target_id"] == "p2"
    call = client.calls[-1]
    assert json.loads(call["parameters"]) == {"limit": 10, "start_id": "p1"}
    assert "id(start) = $start_id" in call["openCypherQuery"]


class _Payload:
    def __init__(self, value: dict[str, Any]) -> None:
        self._value = value

    def read(self) -> bytes:
        return json.dumps(self._value).encode("utf-8")


class FakeNeptuneAnalyticsClient:
    def execute_query(self, **kwargs: Any) -> dict[str, Any]:
        query = kwargs["queryString"]
        if "UNWIND labels" in query:
            result = {"results": [{"label": "Person"}]}
        elif "DISTINCT type(r)" in query:
            result = {"results": [{"relationshipType": "KNOWS"}]}
        else:
            result = {"results": []}
        assert kwargs["language"] == "OPEN_CYPHER"
        assert kwargs["graphIdentifier"] == "g-0123456789"
        return {"payload": _Payload(result)}


def test_neptune_analytics_client_shape_is_supported() -> None:
    backend = NeptuneOpenCypherBackend(
        FakeNeptuneAnalyticsClient(),
        graph_name="analytics",
        graph_identifier="g-0123456789",
    )
    graph = backend.list_graphs()[0]
    assert graph.name == "analytics"
    assert [value.name for value in graph.node_types] == ["Person"]
    assert [value.name for value in graph.relationship_types] == ["KNOWS"]


class FakeAQL:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, query: str, *, bind_vars: dict[str, Any]):
        self.calls.append((query, dict(bind_vars)))
        return [
            {
                "source_id": "people/alice",
                "target_id": "teams/platform",
                "relationship": "member_of",
                "depth": 1,
                "source_type": "people",
                "target_type": "teams",
            }
        ]


class FakeArangoDatabase:
    def __init__(self) -> None:
        self.aql = FakeAQL()

    def graphs(self):
        return [
            {
                "name": "org",
                "edge_definitions": [
                    {
                        "edge_collection": "member_of",
                        "from_vertex_collections": ["people"],
                        "to_vertex_collections": ["teams"],
                    }
                ],
                "orphan_collections": [],
            }
        ]


@pytest.mark.asyncio
async def test_arangodb_native_adapter_uses_bind_vars_and_edge_definitions() -> None:
    database = FakeArangoDatabase()
    router = SchemaRouter()
    keys = await router.aadd_arango_graph(
        database,
        database_name="arango",
        remote=False,
    )
    assert keys == ("arango.org",)

    result = await router.execute(
        _plan(
            router,
            "arango.org",
            start_id="people/alice",
            relationship_types=["member_of"],
        )
    )
    assert result[0].data[0]["target_id"] == "teams/platform"
    query, bind_vars = database.aql.calls[-1]
    assert "GRAPH @graph" in query
    assert bind_vars["graph"] == "org"
    assert bind_vars["relationship_types"] == ["member_of"]


class FakeSparqlResponse:
    def __init__(self, bindings: list[dict[str, Any]]) -> None:
        self._bindings = bindings

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"results": {"bindings": self._bindings}}


class FakeSparqlClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def post(self, url: str, *, content: bytes, headers: dict[str, str]):
        query = content.decode("utf-8")
        self.queries.append(query)
        assert url == "https://example.test/sparql"
        assert headers["Content-Type"] == "application/sparql-query"
        if "SELECT DISTINCT ?class" in query:
            return FakeSparqlResponse(
                [{"class": {"type": "uri", "value": "https://example.test/Person"}}]
            )
        if "SELECT DISTINCT ?predicate" in query:
            return FakeSparqlResponse(
                [
                    {
                        "predicate": {
                            "type": "uri",
                            "value": "https://example.test/knows",
                        }
                    }
                ]
            )
        return FakeSparqlResponse(
            [
                {
                    "target": {
                        "type": "uri",
                        "value": "https://example.test/bob",
                    },
                    "relationship": {
                        "type": "uri",
                        "value": "https://example.test/knows",
                    },
                    "targetType": {
                        "type": "uri",
                        "value": "https://example.test/Person",
                    },
                }
            ]
        )


@pytest.mark.asyncio
async def test_sparql_native_adapter_is_read_only_and_iri_bounded() -> None:
    client = FakeSparqlClient()
    router = SchemaRouter()
    keys = await router.aadd_sparql_graph(
        client,
        endpoint="https://example.test/sparql",
        graph_name="rdf",
        database_name="rdf",
        remote=False,
    )
    assert keys == ("rdf.rdf",)

    result = await router.execute(
        _plan(
            router,
            "rdf.rdf",
            start_id="https://example.test/alice",
            relationship_types=["https://example.test/knows"],
        )
    )
    assert result[0].data[0]["target_id"] == "https://example.test/bob"
    traversal = client.queries[-1]
    assert "SELECT" in traversal
    assert "UPDATE" not in traversal
    assert "<https://example.test/alice>" in traversal


@pytest.mark.asyncio
async def test_neo4j_trusted_filter_scope_fails_before_vendor_traversal() -> None:
    driver = FakeNeo4jDriver()
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="neo4j.org.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="neo4j.org.*",
                roles_any=("employee",),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_neo4j_graph(
        driver,
        database="neo4j",
        graph_name="org",
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )
    discovery_calls = len(driver.calls)

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            _plan(
                router,
                "neo4j.org",
                start_id="person-1",
                relationship_types=["MEMBER_OF"],
            ),
            config=RunConfig(principal=principal),
        )

    assert len(driver.calls) == discovery_calls


@pytest.mark.asyncio
async def test_sparql_trusted_filter_scope_fails_before_vendor_traversal() -> None:
    client = FakeSparqlClient()
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="rdf.rdf.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="rdf.rdf.*",
                roles_any=("employee",),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_sparql_graph(
        client,
        endpoint="https://example.test/sparql",
        graph_name="rdf",
        database_name="rdf",
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )
    discovery_queries = len(client.queries)

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            _plan(
                router,
                "rdf.rdf",
                start_id="https://example.test/alice",
                relationship_types=["https://example.test/knows"],
            ),
            config=RunConfig(principal=principal),
        )

    assert len(client.queries) == discovery_queries


@pytest.mark.asyncio
async def test_native_graph_respects_relationship_data_scope_before_vendor_call() -> None:
    driver = FakeNeo4jDriver()
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="neo4j.org.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="neo4j.org.*",
                roles_any=("employee",),
                allowed_relationships=("MEMBER_OF",),
                max_hops=1,
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_neo4j_graph(
        driver,
        database="neo4j",
        graph_name="org",
        remote=False,
    )
    principal = PrincipalContext(subject="alice", roles=("employee",))
    initial_calls = len(driver.calls)

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            _plan(
                router,
                "neo4j.org",
                start_id="person-1",
                relationship_types=["REPORTS_TO"],
            ),
            config=RunConfig(principal=principal),
        )

    assert len(driver.calls) == initial_calls

def test_neo4j_schema_discovery_pushes_down_limit_and_rejects_overflow() -> None:
    driver = FakeNeo4jDriver()
    backend = Neo4jGraphBackend(
        driver,
        database="neo4j",
        graph_name="org",
        max_schema_items=1,
    )

    with pytest.raises(RegistrationError, match="Neo4j labels exceeded limit=1"):
        backend.list_graphs()

    assert "LIMIT 2" in driver.calls[0][0]


def test_arangodb_explicit_graph_selection_stops_before_unrelated_descriptor() -> None:
    class SelectedDatabase(FakeArangoDatabase):
        def graphs(self):
            return [
                {
                    "name": "org",
                    "edge_definitions": [
                        {
                            "edge_collection": "member_of",
                            "from_vertex_collections": ["people"],
                            "to_vertex_collections": ["teams"],
                        }
                    ],
                },
                "malformed-unrelated-descriptor",
            ]

    backend = ArangoGraphBackend(
        SelectedDatabase(),
        graphs=("org",),
        max_discovery_sources=2,
    )

    graphs = backend.list_graphs()
    assert [graph.name for graph in graphs] == ["org"]


def test_sparql_schema_discovery_pushes_down_limit() -> None:
    client = FakeSparqlClient()
    backend = SparqlGraphBackend(
        client,
        endpoint="https://example.test/sparql",
        graph_name="rdf",
        max_schema_items=1,
    )

    graph = backend.list_graphs()[0]
    assert graph.name == "rdf"
    assert "LIMIT 2" in client.queries[0]
    assert "LIMIT 2" in client.queries[1]

