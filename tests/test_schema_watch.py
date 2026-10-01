from __future__ import annotations

import asyncio

import httpx
import pytest

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec
from schemarouter.ingestion import default_adapter_registry
from schemarouter.registry import InMemoryRegistry
from schemarouter.schema_diff import SchemaDiffReport, SchemaRefreshResult
from schemarouter.schema_watch import SchemaWatchManager


def _document(*, summary: str | None = None, required_query: bool = False) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Watch API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/materials": {
                "get": {
                    "operationId": "materials_search",
                    "summary": summary,
                    "parameters": (
                        [
                            {
                                "name": "q",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ]
                        if required_query
                        else []
                    ),
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }


@pytest.mark.asyncio
async def test_schema_watcher_applies_compatible_drift() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(summary="Search materials")
        snapshots = await router.check_schema_watches_once()

        assert snapshots[0].status == "applied"
        assert snapshots[0].last_compatibility == "compatible"
        assert snapshots[0].last_applied_at is not None
        assert router.registry.get(tool.key).fingerprint != old_fingerprint
        assert (
            router.registry.get(tool.key)
            .endpoint("materials_search")
            .description
            == "Search materials"
        )


@pytest.mark.asyncio
async def test_schema_watcher_quarantines_breaking_drift() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(required_query=True)
        snapshots = await router.check_schema_watches_once()
        pending = router.schema_watch_pending_review(tool.key)

        assert snapshots[0].status == "pending_review"
        assert snapshots[0].pending_review is True
        assert snapshots[0].pending_change_count > 0
        assert snapshots[0].last_compatibility == "breaking"
        assert pending is not None
        assert pending.action == "pending_review"
        assert router.registry.get(tool.key).fingerprint == old_fingerprint


@pytest.mark.asyncio
async def test_schema_watcher_respects_report_only_policy() -> None:
    state = {"document": _document()}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        old_fingerprint = tool.fingerprint
        router.register_schema_watch(
            tool.key,
            interval_seconds=60,
            apply_compatible=False,
        )

        state["document"] = _document(summary="Search materials")
        snapshots = await router.check_schema_watches_once()

        assert snapshots[0].status == "report_only"
        assert snapshots[0].last_compatibility == "compatible"
        assert router.registry.get(tool.key).fingerprint == old_fingerprint


def test_schema_watch_registration_does_not_require_running_loop() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="remote",
        remote=True,
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
        },
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )
    registry.register(tool)

    async def refresh(*args, **kwargs) -> SchemaRefreshResult:
        del args, kwargs
        return SchemaRefreshResult(
            tool_key=tool.key,
            action="unchanged",
            applied=False,
            report=SchemaDiffReport(
                compatibility="identical",
                old_fingerprint=tool.fingerprint,
                new_fingerprint=tool.fingerprint,
                changes=[],
            ),
        )

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(tool.key, interval_seconds=60)

    assert watcher.snapshots()[0].status == "idle"


@pytest.mark.asyncio
async def test_schema_watcher_bounds_concurrency_and_starts_stops_cleanly() -> None:
    registry = InMemoryRegistry()
    keys: list[str] = []
    for index in range(4):
        tool = ToolSpec(
            name=f"remote_{index}",
            remote=True,
            metadata={
                "adapter": "openapi",
                "source_url": f"https://example.test/{index}.json",
            },
            endpoints=[
                EndpointSpec(
                    name="read",
                    read_only=True,
                    output_schema={"type": "object"},
                )
            ],
        )
        registry.register(tool)
        keys.append(tool.key)

    active = 0
    peak = 0
    calls = 0

    async def refresh(tool_key: str, **kwargs) -> SchemaRefreshResult:
        nonlocal active, peak, calls
        del kwargs
        calls += 1
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        tool = registry.get(tool_key)
        return SchemaRefreshResult(
            tool_key=tool_key,
            action="unchanged",
            applied=False,
            report=SchemaDiffReport(
                compatibility="identical",
                old_fingerprint=tool.fingerprint,
                new_fingerprint=tool.fingerprint,
                changes=[],
            ),
        )

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    for key in keys:
        watcher.register(key, interval_seconds=0.03)

    await watcher.start(max_concurrency=2)
    await asyncio.sleep(0.06)
    await watcher.stop()

    assert watcher.running is False
    assert calls >= len(keys)
    assert peak <= 2


@pytest.mark.asyncio
async def test_schema_watcher_snapshots_never_expose_secret_headers() -> None:
    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="remote",
        remote=True,
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
        },
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )
    registry.register(tool)

    async def refresh(tool_key: str, **kwargs) -> SchemaRefreshResult:
        del kwargs
        current = registry.get(tool_key)
        return SchemaRefreshResult(
            tool_key=tool_key,
            action="unchanged",
            applied=False,
            report=SchemaDiffReport(
                compatibility="identical",
                old_fingerprint=current.fingerprint,
                new_fingerprint=current.fingerprint,
                changes=[],
            ),
        )

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(
        tool.key,
        interval_seconds=60,
        schema_headers={"Authorization": "Bearer schema-secret"},
        trusted_headers={"Authorization": "Bearer runtime-secret"},
    )

    snapshot_text = repr(watcher.snapshots())

    assert "schema-secret" not in snapshot_text
    assert "runtime-secret" not in snapshot_text
