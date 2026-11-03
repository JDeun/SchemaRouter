"""Registered native Neo4j/MongoDB/Qdrant public executor fail-closed DEV proof.

Each case uses the original adapter and deterministic vendor-shaped client.
Source discovery is excluded from counts; no vendor-independent E2 claimed.
"""
from __future__ import annotations

from collections.abc import Callable

import pytest
from test_graph_native_adapters import FakeNeo4jDriver
from test_graph_native_adapters import _plan as graph_plan
from test_record_native_adapters import FakeMongoDatabase
from test_record_native_adapters import _plan as record_plan
from test_vector_native_adapters import FakeQdrantClient

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    ToolCall,
    VectorMetadataField,
)
from schemarouter.errors import SchemaRouterError


class CountingQdrantClient(FakeQdrantClient):
    def __init__(self) -> None:
        super().__init__()
        self.query_count = 0

    def query_points(self, **kwargs):
        self.query_count += 1
        return super().query_points(**kwargs)


async def _registered(kind: str) -> tuple[
    SchemaRouter, ExecutionPlan, Callable[[], int], str, str,
]:
    key: str
    operation: str
    if kind == "graph":
        key, operation = "neo4j.org", "traverse"
    elif kind == "record":
        key, operation = "mongo.documents", "query"
    elif kind == "vector":
        key, operation = "qdrant.docs", "search"
    else:
        raise ValueError(kind)
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            rules=(AuthorizationRule(
                effect="allow",
                operation=f"{key}.{operation}",
                roles_any=("reader",),
            ),),
            default_effect="deny",
        )
    )
    if kind == "graph":
        driver = FakeNeo4jDriver()
        (registered_key,) = await router.aadd_neo4j_graph(
            driver, database="neo4j", graph_name="org", remote=False,
        )
        plan = graph_plan(
            router, key, start_id="person-1", relationship_types=["MEMBER_OF"],
        )
        baseline = len(driver.calls)
        def count() -> int:
            return len(driver.calls) - baseline
    elif kind == "record":
        database = FakeMongoDatabase()
        (registered_key,) = await router.aadd_mongodb_record_store(
            database, database_name="mongo",
            text_search_collections=["documents"], remote=False,
        )
        plan = record_plan(
            router, key,
            fields=["_id", "title"],
            arguments={"query": "routing", "limit": 2},
        )
        collection = database.collections["documents"]
        def count() -> int:
            return len(collection.calls)
    else:
        client = CountingQdrantClient()
        (registered_key,) = await router.aadd_qdrant_vector_store(
            client,
            lambda _query: [0.1, 0.2, 0.3],
            database_name="qdrant",
            metadata_fields_by_collection={
                "docs": (
                    VectorMetadataField(
                        name="title", json_schema={"type": "string"},
                    ),
                ),
            },
            remote=False,
        )
        tool = router.registry.get(key)
        endpoint = tool.endpoint("search")
        plan = ExecutionPlan(
            query="search routing",
            registry_version=router.registry.version,
            calls=[ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments={"query": "routing", "top_k": 2},
                fields=["id", "score", "title"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )],
        )
        def count() -> int:
            return client.query_count
    assert registered_key == key
    endpoint = router.registry.get(key).endpoint(operation)
    assert endpoint.read_only is True
    assert endpoint.destructive is False
    return router, plan, count, key, operation


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ("graph", "record", "vector"))
async def test_registered_native_source_denies_unavailable_and_stale_without_io(
    kind: str,
) -> None:
    router, plan, count, key, operation = await _registered(kind)
    reader = RunConfig(
        principal=PrincipalContext(subject="owner", roles=("reader",))
    )
    guest = RunConfig(
        principal=PrincipalContext(subject="guest", roles=("guest",))
    )
    assert count() == 0

    with pytest.raises(PolicyViolationError):
        await router.execute(plan, config=guest)
    assert count() == 0

    malformed = plan.model_copy(deep=True)
    malformed.calls[0].arguments = {"undeclared_provider_mutation": "DELETE"}
    with pytest.raises(PlanValidationError):
        await router.execute(malformed, config=reader)
    assert count() == 0

    router.mark_access_unavailable(key, operation, cooldown_seconds=120)
    with pytest.raises(SchemaRouterError):
        await router.execute(plan, config=reader)
    assert count() == 0, "Unavailable native client must receive no data invocation"

    router.mark_access_available(key, operation)
    results = await router.execute(plan, config=reader)
    assert len(results) == 1
    assert results[0].data
    assert count() == 1, "Recovered native source must be invoked exactly once"

    await router.aremove_tool(key)
    with pytest.raises(SchemaRouterError):
        await router.execute(plan, config=reader)
    assert count() == 1, "Stale native plan must never re-execute"
