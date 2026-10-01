from __future__ import annotations

import asyncio

import httpx
import pytest

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec


def _openapi_document(
    *,
    summary: str | None = None,
    required_query: bool = False,
) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Health Transition API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "read",
                    "summary": summary,
                    "parameters": (
                        [
                            {
                                "name": "q",
                                "in": "query",
                                "required": true,
                                "schema": {"type": "string"},
                            }
                        ]
                        if required_query
                        else []
                    ),
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }


def _local_tool(
    *,
    description: str = "",
    read_only: bool = True,
    endpoint: str = "read",
) -> ToolSpec:
    return ToolSpec(
        name="local",
        endpoints=[
            EndpointSpec(
                name=endpoint,
                description=description,
                read_only=read_only,
                output_schema={"type": "object"},
            )
        ],
    )


@pytest.mark.asyncio
async def test_compatible_schema_refresh_restamps_existing_health_probe() -> None:
    state = {"document": _openapi_document()}
    probe_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    def probe() -> bool:
        nonlocal probe_calls
        probe_calls += 1
        return True

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="health_transition",
        )
        router.register_health_probe(tool.key, "read", probe)

        state["document"] = _openapi_document(summary="compatible update")
        result = await router.arefresh_schema(tool.key)
        snapshots = await router.check_health_once()

    assert result.action == "applied"
    assert result.compatibility == "compatible"
    assert probe_calls == 1
    assert snapshots[0].status == "healthy"
    assert snapshots[0].last_error_type is None


@pytest.mark.asyncio
async def test_trusted_amendment_restamps_existing_health_probe() -> None:
    router = SchemaRouter()
    tool = _local_tool()
    router.add_tool(tool)
    router.register_health_probe(tool.key, "read", lambda: true)

    amended = tool.model_copy(deep=True)
    amended.endpoints[0].description = "trusted annotation"

    router.amend_capability(tool.key, amended)
    snapshots = await router.check_health_once()

    assert snapshots[0].status == "healthy"
    assert snapshots[0].last_error_type is None


@pytest.mark.asyncio
async def test_pending_schema_drift_does_not_move_health_probe_pin() -> None:
    state = {"document": _openapi_document()}
    probe_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    def probe() -> bool:
        nonlocal probe_calls
        probe_calls += 1
        return True

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="health_pending",
        )
        router.register_health_probe(tool.key, "read", probe)

        state["document"] = _openapi_document(required_query=True)
        result = await router.arefresh_schema(tool.key)
        snapshots = await router.check_health_once()

    assert result.action == "pending_review"
    assert result.applied is False
    assert router.registry.get(tool.key).fingerprint == tool.fingerprint
    assert probe_calls == 1
    assert snapshots[0].status == "healthy"


def test_transition_marks_probe_stale_when_endpoint_is_removed() -> None:
    router = SchemaRouter()
    original = _local_tool()
    router.add_tool(original)
    router.register_health_probe(original.key, "read", lambda: true)

    replacement = _local_tool(endpoint="other")
    router.registry.register(replacement, replace=True)

    router.health_monitor.transition_tool_contract(
        original.key,
        expected_old_fingerprint=original.fingerprint,
        expected_new_fingerprint=replacement.fingerprint,
    )

    snapshot = router.health_snapshots()[0]
    assert snapshot.status == "stale"
    assert snapshot.last_error_type == "EndpointRemoved"


def test_transition_marks_probe_stale_when_endpoint_becomes_mutable() -> None:
    router = SchemaRouter()
    original = _local_tool()
    router.add_tool(original)
    router.register_health_probe(original.key, "read", lambda: true)

    replacement = _local_tool(read_only=False)
    router.registry.register(replacement, replace=True)

    router.health_monitor.transition_tool_contract(
        original.key,
        expected_old_fingerprint=original.fingerprint,
        expected_new_fingerprint=replacement.fingerprint,
    )

    snapshot = router.health_snapshots()[0]
    assert snapshot.status == "stale"
    assert snapshot.last_error_type == "EndpointNotReadOnly"


def test_transition_fails_closed_on_concurrent_contract_change() -> None:
    router = SchemaRouter()
    original = _local_tool()
    router.add_tool(original)
    router.register_health_probe(original.key, "read", lambda: true)

    accepted = _local_tool(description="accepted")
    concurrent = _local_tool(description="concurrent")
    router.registry.register(concurrent, replace=True)

    router.health_monitor.transition_tool_contract(
        original.key,
        expected_old_fingerprint=original.fingerprint,
        expected_new_fingerprint=accepted.fingerprint,
    )

    snapshot = router.health_snapshots()[0]
    assert snapshot.status == "stale"
    assert snapshot.last_error_type == "ConcurrentContractChange"


@pytest.mark.asyncio
async def test_inflight_probe_survives_trusted_amendment_transition() -> None:
    router = SchemaRouter()
    original = _local_tool()
    router.add_tool(original)

    started = asyncio.Event()
    release = asyncio.Event()

    async def probe() -> bool:
        started.set()
        await release.wait()
        return True

    router.register_health_probe(original.key, "read", probe)
    task = asyncio.create_task(router.check_health_once())
    await asyncio.wait_for(started.wait(), timeout=1)

    amended = original.model_copy(deep=True)
    amended.endpoints[0].description = "trusted annotation"
    router.amend_capability(original.key, amended)

    release.set()
    snapshots = await asyncio.wait_for(task, timeout=1)

    assert snapshots[0].status == "healthy"
    assert snapshots[0].last_error_type is None
