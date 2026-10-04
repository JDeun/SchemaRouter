from __future__ import annotations

from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
)


class FakeFalkorResult:
    def __init__(self, rows: list[list[Any]]) -> None:
        self.result_set = rows


class FakeFalkorGraph:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def ro_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> FakeFalkorResult:
        self.calls.append((query, dict(params or {})))
        if "UNWIND labels(n) AS label" in query:
            return FakeFalkorResult([["Person"], ["Team"]])
        if "DISTINCT type(r) AS relationshipType" in query:
            return FakeFalkorResult([["MEMBER_OF"]])
        if "MATCH (n:`Person`)" in query and "keys(n)" in query:
            return FakeFalkorResult([["department"], ["name"]])
        if "MATCH (n:`Team`)" in query and "keys(n)" in query:
            return FakeFalkorResult([["name"]])
        if (
            "MATCH (source)-[r:`MEMBER_OF`]->(target)" in query
            and "sourceType" in query
        ):
            return FakeFalkorResult([["Person", "Team"]])
        if "MATCH ()-[r:`MEMBER_OF`]->()" in query and "keys(r)" in query:
            return FakeFalkorResult([["since"]])
        if "MATCH p=" in query:
            return FakeFalkorResult(
                [["1", "2", "MEMBER_OF", 1, "Person", "Team"]]
            )
        raise AssertionError(f"unexpected FalkorDB query: {query}")


class FakeFalkorDB:
    def __init__(self) -> None:
        self.graph = FakeFalkorGraph("social")
        self.list_calls = 0
        self.select_calls: list[str] = []

    def list_graphs(self) -> list[str]:
        self.list_calls += 1
        return ["social"]

    def select_graph(self, name: str) -> FakeFalkorGraph:
        self.select_calls.append(name)
        assert name == "social"
        return self.graph


def _plan(
    router: SchemaRouter,
    *,
    relationship_types: list[str],
    max_hops: int = 1,
) -> ExecutionPlan:
    tool = router.registry.get("falkordb.social")
    endpoint = tool.endpoint("traverse")
    return ExecutionPlan(
        query="walk social graph",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={
                    "start_id": "1",
                    "relationship_types": relationship_types,
                    "direction": "out",
                    "max_hops": max_hops,
                    "limit": 5,
                },
                fields=[
                    "source_id",
                    "target_id",
                    "relationship",
                    "depth",
                    "source_type",
                    "target_type",
                ],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


@pytest.mark.asyncio
async def test_falkordb_discovers_schema_and_uses_read_only_bounded_traversal() -> None:
    client = FakeFalkorDB()
    router = SchemaRouter()

    keys = await router.aadd_falkordb_graph(
        client,
        graphs={"social"},
        remote=False,
    )
    assert keys == ("falkordb.social",)

    endpoint = router.registry.get("falkordb.social").endpoint("traverse")
    assert endpoint.metadata["public_metadata"]["vendor"] == "falkordb"
    node_types = {
        item["name"]: item for item in endpoint.metadata["node_types"]
    }
    assert [prop["name"] for prop in node_types["Person"]["properties"]] == [
        "department",
        "name",
    ]
    relationship = endpoint.metadata["relationship_types"][0]
    assert relationship["name"] == "MEMBER_OF"
    assert relationship["source_types"] == ["Person"]
    assert relationship["target_types"] == ["Team"]
    assert [prop["name"] for prop in relationship["properties"]] == ["since"]

    result = await router.execute(
        _plan(router, relationship_types=["MEMBER_OF"])
    )
    assert result[0].data == [
        {
            "source_id": "1",
            "target_id": "2",
            "relationship": "MEMBER_OF",
            "depth": 1,
            "source_type": "Person",
            "target_type": "Team",
        }
    ]

    query, params = client.graph.calls[-1]
    assert "MATCH p=(start)-[rels:`MEMBER_OF`*1..1]->(target)" in query
    assert "toString(id(start)) = $start_id" in query
    assert "LIMIT $limit" in query
    assert params == {"start_id": "1", "limit": 5}


@pytest.mark.asyncio
async def test_falkordb_respects_relationship_scope_before_traversal_call() -> None:
    client = FakeFalkorDB()
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="falkordb.social.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="falkordb.social.*",
                roles_any=("employee",),
                allowed_relationships=("MEMBER_OF",),
                max_hops=1,
            ),
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_falkordb_graph(client, graphs={"social"}, remote=False)

    principal = PrincipalContext(subject="alice", roles=("employee",))
    before = len(client.graph.calls)
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            _plan(router, relationship_types=["MEMBER_OF"], max_hops=2),
            config=RunConfig(principal=principal),
        )
    assert len(client.graph.calls) == before
