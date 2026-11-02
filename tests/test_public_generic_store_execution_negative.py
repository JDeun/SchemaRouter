"""Real generic-store public executor denial and recovery regressions.

Each test binds a genuine registered adapter to the existing deterministic
Graph/Vector/Record backend fixture, never monkeypatches the executor and
verifies that blocked operations generate zero provider/backend calls.
This is local DEV-only, not a live external provider or independent E2.
"""
from __future__ import annotations

import pytest
from test_graph_store_adapter import FakeGraphBackend
from test_graph_store_adapter import _plan as _graph_plan
from test_record_store_adapter import FakeRecordBackend
from test_record_store_adapter import _plan as _record_plan
from test_vector_store_adapter import FakeVectorBackend
from test_vector_store_adapter import _plan as _vector_plan

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    PlanValidationError,
    PolicyViolationError,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
)
from schemarouter.errors import SchemaRouterError


async def _registered(kind: str):
    key: str
    operation: str
    router: SchemaRouter
    if kind == "graph":
        key, operation = "knowledge.org", "traverse"
    elif kind == "vector":
        key, operation = "vectors.public_docs", "search"
    elif kind == "record":
        key, operation = "nosql.documents", "query"
    else:
        raise ValueError("Unknown source fixture")
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        rules=(AuthorizationRule(
            effect="allow", operation=f"{key}.{operation}",
            roles_any=("reader",),
        ),),
        default_effect="deny",
    ))
    if kind == "graph":
        backend = FakeGraphBackend()
        await router.aadd_graph_store(
            backend, database_name="knowledge", graphs={"org"}, remote=False,
        )
        plan = _graph_plan(
            router, key, start_id="person-1",
            fields=["source_id", "target_id", "relationship"],
        )
        calls = backend.calls
    elif kind == "vector":
        backend = FakeVectorBackend()
        await router.aadd_vector_store(
            backend, lambda query: [0.1, 0.2, 0.3],
            database_name="vectors", collections={"public_docs"}, remote=False,
        )
        plan = _vector_plan(
            router, key, query="schema routing", fields=["id", "score", "title"],
        )
        calls = backend.search_calls
    else:
        backend = FakeRecordBackend()
        await router.aadd_record_store(
            backend, database_name="nosql", sources={"documents"}, remote=False,
        )
        plan = _record_plan(
            router, key, fields=["id", "title"], arguments={"query": "routing"},
        )
        calls = backend.calls
    tool = router.registry.get(key)
    assert tool.endpoints
    assert all(x.read_only is True and x.destructive is False for x in tool.endpoints)
    allowed = RunConfig(principal=PrincipalContext(
        subject="reader", roles=("reader",),
    ))
    denied = RunConfig(principal=PrincipalContext(
        subject="guest", roles=("guest",),
    ))
    return router, plan, calls, key, operation, allowed, denied


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ("graph", "vector", "record"))
async def test_registered_generic_store_fail_closed_and_recovers(kind: str) -> None:
    router, plan, calls, key, operation, allowed, denied = await _registered(kind)
    assert calls == []

    with pytest.raises(PolicyViolationError, match="authorization denied"):
        await router.execute(plan, config=denied)
    assert calls == [], "Guest must not reach native source I/O"

    malformed = plan.model_copy(deep=True)
    malformed.calls[0].arguments = {"undeclared_provider_payload": {"delete": True}}
    with pytest.raises(PlanValidationError):
        await router.execute(malformed, config=allowed)
    assert calls == [], "Invalid input must fail before any native backend call"

    router.mark_access_unavailable(key, operation, cooldown_seconds=120)
    with pytest.raises(SchemaRouterError):
        await router.execute(plan, config=allowed)
    assert calls == [], "Temporarily unavailable source must not execute"

    router.mark_access_available(key, operation)
    result = await router.execute(plan, config=allowed)
    assert len(result) == 1
    assert result[0].data
    assert len(calls) == 1, "Recovery must dispatch exactly once"

    await router.aremove_tool(key)
    with pytest.raises(SchemaRouterError):
        await router.execute(plan, config=allowed)
    assert len(calls) == 1, "Removed source must not replay stale plan"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ("graph", "vector", "record"))
async def test_registered_generic_store_revoked_policy_never_calls_backend(kind: str) -> None:
    router, plan, calls, _, _, allowed, _ = await _registered(kind)
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    with pytest.raises(PolicyViolationError):
        await router.execute(plan, config=allowed)
    assert calls == [], "Revoked permission must fail before any native I/O"
