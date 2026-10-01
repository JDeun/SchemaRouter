from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    InMemoryRegistry,
    RegistrationError,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
)


def _local_tool(*, description: str = "") -> ToolSpec:
    return ToolSpec(
        name="local",
        endpoints=[
            EndpointSpec(
                name="read",
                description=description,
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )


async def _invoker(endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
    del endpoint, arguments
    return {"ok": True}


def _openapi_document() -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Removal API", "version": "1.0.0"},
        "servers": [{"url": "https://api.example.test"}],
        "paths": {
            "/items": {
                "get": {
                    "operationId": "read",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_remove_tool_purges_all_router_owned_runtime_state() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_openapi_document(),
            headers={"ETag": '"v1"'},
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://api.example.test/openapi.json",
            kind="openapi",
            name="removal_api",
        )
        router.register_schema_watch(tool.key, interval_seconds=60)
        router.register_health_probe(tool.key, "read", lambda: True)
        router.mark_access_unavailable(tool.key, "read", cooldown_seconds=60)

        assert tool.key in router.executor.bound_keys()
        assert router.schema_watch_snapshots()
        assert router.health_snapshots()
        assert router.unavailable_access_paths() == ((tool.key, "read"),)
        assert router.loader.schema_http_validators_for(tool.key, tool) == {
            "etag": '"v1"',
        }

        removed = await router.aremove_tool(tool.key)

    assert removed.fingerprint == tool.fingerprint
    with pytest.raises(KeyError):
        router.registry.get(tool.key)
    assert tool.key not in router.executor.bound_keys()
    assert router.schema_watch_snapshots() == ()
    assert router.health_snapshots() == ()
    assert router.unavailable_access_paths() == ()
    assert router.loader.schema_http_validators_for(tool.key) == {}


def test_remove_tool_sync_wrapper() -> None:
    router = SchemaRouter()
    tool = _local_tool()
    router.add_bound_tool(tool, _invoker)

    removed = router.remove_tool(tool.key)

    assert removed.key == tool.key
    assert router.registry.keys() == ()
    assert router.executor.bound_keys() == ()


@pytest.mark.asyncio
async def test_remove_tool_fails_closed_for_registry_without_atomic_removal() -> None:
    class NonMutableRegistry:
        def __init__(self) -> None:
            self.inner = InMemoryRegistry()

        @property
        def version(self) -> int:
            return self.inner.version

        def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
            return self.inner.register(tool, replace=replace)

        def get(self, key: str) -> ToolSpec:
            return self.inner.get(key)

        def tools(self) -> tuple[ToolSpec, ...]:
            return self.inner.tools()

        def keys(self) -> tuple[str, ...]:
            return self.inner.keys()

        def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
            return self.inner.endpoint(tool_key, endpoint_name)

    registry = NonMutableRegistry()
    router = SchemaRouter(registry=registry)
    tool = _local_tool()
    router.add_bound_tool(tool, _invoker)
    router.register_health_probe(tool.key, "read", lambda: True)

    with pytest.raises(
        RegistrationError,
        match="MutableToolRegistry",
    ):
        await router.aremove_tool(tool.key)

    assert registry.get(tool.key).fingerprint == tool.fingerprint
    assert router.executor.bound_keys() == (tool.key,)
    assert len(router.health_snapshots()) == 1


@pytest.mark.asyncio
async def test_remove_tool_rejects_concurrent_registry_change_without_cleanup() -> None:
    class ConcurrentMutationRegistry(InMemoryRegistry):
        def unregister_if_fingerprint(
            self,
            key: str,
            *,
            expected_fingerprint: str,
            expected_version: int,
        ) -> None:
            current = self.get(key)
            changed = current.model_copy(deep=True)
            changed.endpoints[0].description = "concurrent change"
            self.register(changed, replace=True)
            super().unregister_if_fingerprint(
                key,
                expected_fingerprint=expected_fingerprint,
                expected_version=expected_version,
            )

    registry = ConcurrentMutationRegistry()
    router = SchemaRouter(registry=registry)
    tool = _local_tool()
    router.add_bound_tool(tool, _invoker)
    router.register_health_probe(tool.key, "read", lambda: True)

    with pytest.raises(RegistrationError, match="changed concurrently"):
        await router.aremove_tool(tool.key)

    assert router.registry.get(tool.key).endpoint("read").description == "concurrent change"
    assert router.executor.bound_keys() == (tool.key,)
    assert len(router.health_snapshots()) == 1


@pytest.mark.asyncio
async def test_remove_tool_waits_for_inflight_health_probe_before_deleting() -> None:
    router = SchemaRouter()
    tool = _local_tool()
    router.add_bound_tool(tool, _invoker)

    entered = asyncio.Event()
    release = asyncio.Event()

    async def probe() -> bool:
        entered.set()
        await release.wait()
        return True

    router.register_health_probe(tool.key, "read", probe)
    check_task = asyncio.create_task(router.check_health_once())
    await entered.wait()

    remove_task = asyncio.create_task(router.aremove_tool(tool.key))
    await asyncio.sleep(0)
    assert remove_task.done() is False

    release.set()
    await check_task
    removed = await remove_task

    assert removed.key == tool.key
    assert router.registry.keys() == ()
    assert router.health_snapshots() == ()


@pytest.mark.asyncio
async def test_remove_tool_waits_for_inflight_schema_watch_before_deleting() -> None:
    state = _openapi_document()
    entered = asyncio.Event()
    release = asyncio.Event()
    request_count = 0

    async def slow_handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count > 1:
            entered.set()
            await release.wait()
        return httpx.Response(200, json=state, request=request)

    class AsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(
            self,
            request: httpx.Request,
        ) -> httpx.Response:
            return await slow_handler(request)

    async with httpx.AsyncClient(transport=AsyncTransport()) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://api.example.test/openapi.json",
            kind="openapi",
            name="removal_api",
        )
        router.register_schema_watch(tool.key, interval_seconds=60)

        check_task = asyncio.create_task(router.check_schema_watches_once())
        await entered.wait()

        remove_task = asyncio.create_task(router.aremove_tool(tool.key))
        await asyncio.sleep(0)
        assert remove_task.done() is False

        release.set()
        await check_task
        removed = await remove_task

    assert removed.key == tool.key
    assert router.registry.keys() == ()
    assert router.schema_watch_snapshots() == ()


@pytest.mark.asyncio
async def test_remove_then_same_key_reregistration_has_no_orphan_state() -> None:
    router = SchemaRouter()
    old = _local_tool(description="old")
    router.add_bound_tool(old, _invoker)
    router.register_health_probe(old.key, "read", lambda: True)
    router.mark_access_unavailable(old.key, "read", cooldown_seconds=60)

    await router.aremove_tool(old.key)

    new = _local_tool(description="new")
    router.add_bound_tool(new, _invoker)

    assert router.registry.get(new.key).endpoint("read").description == "new"
    assert router.executor.binding_states()[new.key] == "ready"
    assert router.health_snapshots() == ()
    assert router.unavailable_access_paths() == ()


@pytest.mark.asyncio
async def test_sqlite_registry_removal_persists_across_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.sqlite3"
    registry = SQLiteRegistry(path)
    router = SchemaRouter(registry=registry)
    tool = _local_tool()

    router.add_tool(tool)
    await router.aremove_tool(tool.key)
    registry.close()

    reopened = SQLiteRegistry(path)
    try:
        assert reopened.keys() == ()
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_remove_unknown_tool_is_actionable() -> None:
    router = SchemaRouter()

    with pytest.raises(RegistrationError, match="unknown tool"):
        await router.aremove_tool("missing")
