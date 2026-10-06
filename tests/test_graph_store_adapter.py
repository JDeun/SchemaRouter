from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    ExecutionPlan,
    GraphNodeTypeSpec,
    GraphRelationshipTypeSpec,
    GraphSourceSpec,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SchemaValidationError,
    ToolCall,
    TrustedFilterBinding,
)
from schemarouter.errors import RegistrationError


class FakeGraphBackend:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def list_graphs(self) -> tuple[GraphSourceSpec, ...]:
        return (
            GraphSourceSpec(
                name="org",
                model="property_graph",
                node_types=(
                    GraphNodeTypeSpec(name="Person"),
                    GraphNodeTypeSpec(name="Team"),
                ),
                relationship_types=(
                    GraphRelationshipTypeSpec(
                        name="MEMBER_OF",
                        source_types=("Person",),
                        target_types=("Team",),
                    ),
                ),
            ),
            GraphSourceSpec(
                name="executive",
                model="rdf",
                relationship_types=(
                    GraphRelationshipTypeSpec(name="reportsTo"),
                ),
            ),
        )

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        self.calls.append(
            {
                "graph": graph,
                "start_id": start_id,
                "relationship_types": relationship_types,
                "direction": direction,
                "max_hops": max_hops,
                "limit": limit,
                "include_fields": include_fields,
            }
        )
        if graph == "org":
            return [
                {
                    "source_id": "person-1",
                    "target_id": "team-1",
                    "relationship": "MEMBER_OF",
                    "depth": 1,
                    "source_type": "Person",
                    "target_type": "Team",
                }
            ]
        return [
            {
                "source_id": "ceo",
                "target_id": "board",
                "relationship": "reportsTo",
                "depth": 1,
                "source_type": "Executive",
                "target_type": "Board",
            }
        ]


def _plan(
    router: SchemaRouter,
    tool_key: str,
    *,
    start_id: str,
    fields: list[str],
    relationship_types: list[str] | None = None,
) -> ExecutionPlan:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("traverse")
    arguments: dict[str, object] = {"start_id": start_id}
    if relationship_types is not None:
        arguments["relationship_types"] = relationship_types
    return ExecutionPlan(
        query=f"traverse {tool_key}",
        registry_version=router.registry.version,
        calls=[
            ToolCall(
                tool=tool.key,
                endpoint=endpoint.name,
                arguments=arguments,
                fields=fields,
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=tool.fingerprint,
            )
        ],
    )


def test_graph_introspection_compiles_bounded_traversal_capabilities() -> None:
    router = SchemaRouter()
    keys = router.add_graph_store(
        FakeGraphBackend(),
        database_name="knowledge",
        remote=False,
    )

    assert keys == ("knowledge.org", "knowledge.executive")
    tool = router.registry.get("knowledge.org")
    endpoint = tool.endpoint("traverse")
    assert tool.source_type == "database"
    assert tool.access_mode == "graph"
    assert endpoint.read_only is True
    assert endpoint.destructive is False
    assert endpoint.execution_metadata["graph_model"] == "property_graph"
    assert {parameter.name for parameter in endpoint.parameters} == {
        "start_id",
        "relationship_types",
        "direction",
        "max_hops",
        "limit",
    }


@pytest.mark.asyncio
async def test_graph_traversal_is_bounded_and_projected() -> None:
    backend = FakeGraphBackend()
    router = SchemaRouter()
    await router.aadd_graph_store(
        backend,
        database_name="knowledge",
        graphs={"org"},
        default_limit=10,
        default_max_hops=1,
        remote=False,
    )

    result = await router.execute(
        _plan(
            router,
            "knowledge.org",
            start_id="person-1",
            fields=["source_id", "target_id", "relationship"],
            relationship_types=["MEMBER_OF"],
        )
    )

    assert result[0].data == [
        {
            "source_id": "person-1",
            "target_id": "team-1",
            "relationship": "MEMBER_OF",
        }
    ]
    assert backend.calls[0]["max_hops"] == 1
    assert backend.calls[0]["limit"] == 10


@pytest.mark.asyncio
async def test_graph_unknown_relationship_is_rejected_before_backend_call() -> None:
    backend = FakeGraphBackend()
    router = SchemaRouter()
    await router.aadd_graph_store(
        backend,
        database_name="knowledge",
        graphs={"org"},
        remote=False,
    )

    with pytest.raises(SchemaValidationError):
        await router.execute(
            _plan(
                router,
                "knowledge.org",
                start_id="person-1",
                fields=["source_id", "target_id"],
                relationship_types=["OWNS"],
            )
        )
    assert backend.calls == []


@pytest.mark.asyncio
async def test_graphs_compose_with_principal_authorization() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                name="org-graph",
                effect="allow",
                operation="knowledge.org.*",
                roles_any=("employee", "manager", "executive"),
            ),
            AuthorizationRule(
                name="executive-graph",
                effect="allow",
                operation="knowledge.executive.*",
                roles_any=("executive",),
            ),
        )
    )
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_graph_store(
        FakeGraphBackend(),
        database_name="knowledge",
        remote=False,
    )
    employee = PrincipalContext(subject="alice", roles=("employee",))
    executive = PrincipalContext(subject="ceo", roles=("executive",))

    employee_view = router.retrieve_authorized(
        "executive graph",
        principal=employee,
        k=5,
    )
    assert all(
        candidate.tool != "knowledge.executive"
        for candidate in employee_view.candidates
    )

    plan = _plan(
        router,
        "knowledge.executive",
        start_id="ceo",
        fields=["source_id", "target_id", "relationship"],
    )
    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(plan, config=RunConfig(principal=employee))

    result = await router.execute(
        plan,
        config=RunConfig(principal=executive),
    )
    assert result[0].data[0]["relationship"] == "reportsTo"


@pytest.mark.asyncio
async def test_graph_trusted_filters_fail_closed_before_unscoped_backend_io() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="knowledge.org.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="knowledge.org.*",
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
    backend = FakeGraphBackend()
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_graph_store(
        backend,
        database_name="knowledge",
        graphs={"org"},
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(
            _plan(
                router,
                "knowledge.org",
                start_id="person-1",
                fields=["source_id", "target_id", "relationship"],
                relationship_types=["MEMBER_OF"],
            ),
            config=RunConfig(principal=principal),
        )

    assert backend.calls == []


class ScopedFakeGraphBackend(FakeGraphBackend):
    supports_trusted_filters = True

    def __init__(self) -> None:
        super().__init__()
        self.trusted_filters: dict[str, Any] | None = None

    def traverse(
        self,
        *,
        graph: str,
        start_id: str,
        relationship_types: tuple[str, ...],
        direction: str,
        max_hops: int,
        limit: int,
        include_fields: tuple[str, ...],
        trusted_filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.trusted_filters = trusted_filters
        return super().traverse(
            graph=graph,
            start_id=start_id,
            relationship_types=relationship_types,
            direction=direction,
            max_hops=max_hops,
            limit=limit,
            include_fields=include_fields,
        )


@pytest.mark.asyncio
async def test_graph_scoped_backend_composes_filters_relationships_and_hops() -> None:
    policy = AuthorizationPolicy(
        rules=(
            AuthorizationRule(
                effect="allow",
                operation="knowledge.org.*",
                roles_any=("employee",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="knowledge.org.*",
                roles_any=("employee",),
                trusted_filters=(
                    TrustedFilterBinding(
                        field="tenant",
                        principal_value="attribute:tenant_id",
                    ),
                ),
                allowed_relationships=("MEMBER_OF",),
                max_hops=1,
            ),
        ),
    )
    backend = ScopedFakeGraphBackend()
    router = SchemaRouter(authorization_policy=policy)
    await router.aadd_graph_store(
        backend,
        database_name="knowledge",
        graphs={"org"},
        default_max_hops=3,
        remote=False,
    )
    principal = PrincipalContext(
        subject="alice",
        roles=("employee",),
        attributes={"tenant_id": "tenant-a"},
    )

    result = await router.execute(
        _plan(
            router,
            "knowledge.org",
            start_id="person-1",
            fields=["source_id", "target_id", "relationship"],
            relationship_types=["MEMBER_OF"],
        ),
        config=RunConfig(principal=principal),
    )

    assert result[0].data[0]["relationship"] == "MEMBER_OF"
    assert backend.trusted_filters == {"tenant": "tenant-a"}
    assert backend.calls[0]["max_hops"] == 1


def test_graph_registration_can_limit_graphs_before_exposure() -> None:
    router = SchemaRouter()
    keys = router.add_graph_store(
        FakeGraphBackend(),
        database_name="knowledge",
        graphs={"org"},
        remote=False,
    )

    assert keys == ("knowledge.org",)
    assert router.registry.keys() == ("knowledge.org",)


@pytest.mark.asyncio
async def test_remote_sync_graph_backend_does_not_block_event_loop() -> None:
    class BlockingBackend(FakeGraphBackend):
        def __init__(self) -> None:
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()

        def traverse(
            self,
            *,
            graph: str,
            start_id: str,
            relationship_types: tuple[str, ...],
            direction: str,
            max_hops: int,
            limit: int,
            include_fields: tuple[str, ...],
        ) -> list[dict[str, Any]]:
            self.started.set()
            self.release.wait(timeout=0.25)
            return super().traverse(
                graph=graph,
                start_id=start_id,
                relationship_types=relationship_types,
                direction=direction,
                max_hops=max_hops,
                limit=limit,
                include_fields=include_fields,
            )

    backend = BlockingBackend()
    router = SchemaRouter()
    await router.aadd_graph_store(
        backend,
        database_name="knowledge",
        graphs={"org"},
        remote=True,
    )

    timer = threading.Timer(0.2, backend.release.set)
    timer.start()
    observed = time.monotonic()
    task = asyncio.create_task(
        router.execute(
            _plan(
                router,
                "knowledge.org",
                start_id="person-1",
                fields=["source_id", "target_id", "relationship"],
                relationship_types=["MEMBER_OF"],
            )
        )
    )
    try:
        while not backend.started.is_set() and time.monotonic() - observed < 0.1:
            await asyncio.sleep(0.001)
        assert backend.started.is_set()
        assert time.monotonic() - observed < 0.1
        backend.release.set()
        result = await task
    finally:
        backend.release.set()
        timer.cancel()

    assert result[0].data[0]["relationship"] == "MEMBER_OF"

@pytest.mark.asyncio
async def test_native_graph_schema_refresh_reintrospects_current_contract() -> None:
    router = SchemaRouter()
    await router.aadd_graph_store(
        FakeGraphBackend(),
        database_name="knowledge",
        graphs={"org"},
        remote=False,
    )

    result = await router.arefresh_native_schema("knowledge.org")

    tool = router.registry.get("knowledge.org")
    assert result.action == "unchanged"
    assert router.executor.is_binding_ready_for_contract(tool.key, tool.fingerprint)



def test_graph_discovery_catalog_limit_stops_unbounded_iterable() -> None:
    consumed = 0

    class LargeCatalogBackend(FakeGraphBackend):
        def list_graphs(self):
            nonlocal consumed

            def generate():
                nonlocal consumed
                for index in range(100):
                    consumed += 1
                    yield GraphSourceSpec(name=f"graph_{index}")

            return generate()

    router = SchemaRouter()
    with pytest.raises(RegistrationError, match="max_discovery_sources=3"):
        router.add_graph_store(
            LargeCatalogBackend(),
            database_name="knowledge",
            max_discovery_sources=3,
            remote=False,
        )

    assert consumed == 4
    assert router.registry.keys() == ()


def test_graph_discovery_rejects_oversized_descriptor_before_registration() -> None:
    class WideGraphBackend(FakeGraphBackend):
        def list_graphs(self):
            return (
                GraphSourceSpec(
                    name="wide",
                    node_types=(
                        GraphNodeTypeSpec(name="A"),
                        GraphNodeTypeSpec(name="B"),
                        GraphNodeTypeSpec(name="C"),
                    ),
                ),
            )

    router = SchemaRouter()
    with pytest.raises(RegistrationError, match="node types"):
        router.add_graph_store(
            WideGraphBackend(),
            database_name="knowledge",
            max_schema_items_per_graph=2,
            remote=False,
        )

    assert router.registry.keys() == ()
