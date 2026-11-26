from __future__ import annotations

from typing import Any

import httpx
import pytest

from schemarouter import EndpointSpec, SchemaRouter, ToolSpec, compare_tool_specs
from schemarouter.ingestion import default_adapter_registry
from schemarouter.registry import InMemoryRegistry
from schemarouter.schema_diff import SchemaDiffReport, SchemaRefreshResult
from schemarouter.schema_watch import SchemaWatchManager


def _tool(
    *,
    adapter: str,
    source: str | None = None,
    transport: str | None = None,
    transport_fingerprint: str | None = None,
    description: str = "",
) -> ToolSpec:
    execution_metadata: dict[str, Any] = {"adapter": adapter}
    metadata: dict[str, Any] = {"adapter": adapter}

    if adapter == "optimade":
        if source is not None:
            execution_metadata["versioned_base_url"] = source
            metadata["versioned_base_url"] = source
    elif adapter == "mcp":
        if source is not None:
            execution_metadata["source_url"] = source
            metadata["source_url"] = source
        if transport is not None:
            execution_metadata["transport"] = transport
            metadata["transport"] = transport
        if transport_fingerprint is not None:
            execution_metadata["transport_fingerprint"] = transport_fingerprint
            metadata["transport_fingerprint"] = transport_fingerprint
    elif source is not None:
        metadata["source_url"] = source

    return ToolSpec(
        name="remote",
        remote=True,
        execution_metadata=execution_metadata,
        metadata=metadata,
        endpoints=[
            EndpointSpec(
                name="read",
                description=description,
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )


def _unchanged(tool: ToolSpec) -> SchemaRefreshResult:
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "adapter",
    ["openapi", "graphql", "odata", "openrpc", "optimade"],
)
async def test_same_key_different_source_never_calls_registered_refresh(
    adapter: str,
) -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter=adapter,
        source="https://source-a.example.test/schema",
    )
    registry.register(original)

    calls = 0

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        nonlocal calls
        del kwargs
        calls += 1
        return _unchanged(registry.get(tool_key))

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(
        original.key,
        interval_seconds=60,
        schema_headers={"Authorization": "Bearer schema-watch-value"},
        trusted_headers={"Authorization": "Bearer runtime-watch-value"},
    )

    replacement = _tool(
        adapter=adapter,
        source="https://source-b.example.test/schema",
    )
    registry.register(replacement, replace=True)

    snapshots = await watcher.run_once()

    assert calls == 0
    assert snapshots[0].status == "stale_source"
    assert snapshots[0].last_error_type == "SourceIdentityChanged"


@pytest.mark.asyncio
async def test_same_source_contract_replacement_is_stale_before_refresh() -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
    )
    registry.register(original)

    calls = 0

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        nonlocal calls
        del kwargs
        calls += 1
        return _unchanged(registry.get(tool_key))

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(original.key, interval_seconds=60)

    replacement = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
        description="externally replaced contract",
    )
    registry.register(replacement, replace=True)

    snapshots = await watcher.run_once()

    assert calls == 0
    assert snapshots[0].status == "stale_contract"
    assert snapshots[0].last_error_type == "ToolContractChanged"


@pytest.mark.asyncio
async def test_mcp_http_source_change_never_reuses_old_factory() -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter="mcp",
        source="https://mcp-a.example.test/mcp",
        transport="streamable_http",
        transport_fingerprint="transport-a",
    )
    registry.register(original)

    class Factory:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            del args, kwargs
            self.calls += 1
            raise AssertionError("stale MCP factory must not be called")

    factory = Factory()

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        del kwargs
        factory()
        return _unchanged(registry.get(tool_key))

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(
        original.key,
        interval_seconds=60,
        mcp_client_factory=factory,
    )

    replacement = _tool(
        adapter="mcp",
        source="https://mcp-b.example.test/mcp",
        transport="streamable_http",
        transport_fingerprint="transport-b",
    )
    registry.register(replacement, replace=True)

    snapshots = await watcher.run_once()

    assert factory.calls == 0
    assert snapshots[0].status == "stale_source"
    assert snapshots[0].last_error_type == "SourceIdentityChanged"


@pytest.mark.asyncio
async def test_mcp_bound_transport_fingerprint_change_is_stale_source() -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter="mcp",
        transport="custom",
        transport_fingerprint="factory-a",
    )
    registry.register(original)

    calls = 0

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        nonlocal calls
        del kwargs
        calls += 1
        return _unchanged(registry.get(tool_key))

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(original.key, interval_seconds=60)

    registry.register(
        _tool(
            adapter="mcp",
            transport="custom",
            transport_fingerprint="factory-b",
        ),
        replace=True,
    )

    snapshots = await watcher.run_once()

    assert calls == 0
    assert snapshots[0].status == "stale_source"
    assert snapshots[0].last_error_type == "SourceIdentityChanged"


@pytest.mark.asyncio
async def test_watch_driven_compatible_apply_advances_contract_pin() -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
    )
    registry.register(original)
    calls = 0

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        nonlocal calls
        calls += 1
        current = registry.get(tool_key)

        assert kwargs["_expected_fingerprint"] == current.fingerprint
        assert kwargs["_expected_source_identity"] is not None

        if calls == 1:
            updated = _tool(
                adapter="openapi",
                source="https://source.example.test/openapi.json",
                description="compatible update",
            )
            report = compare_tool_specs(current, updated)
            assert report.compatibility == "compatible"
            registry.register(updated, replace=True)
            return SchemaRefreshResult(
                tool_key=tool_key,
                action="applied",
                applied=True,
                report=report,
            )
        return _unchanged(current)

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(original.key, interval_seconds=60)

    first = await watcher.run_once()
    second = await watcher.run_once()

    assert first[0].status == "applied"
    assert second[0].status == "unchanged"
    assert calls == 2


@pytest.mark.asyncio
async def test_pending_review_does_not_advance_watch_pin() -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
    )
    registry.register(original)
    calls = 0

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        nonlocal calls
        calls += 1
        current = registry.get(tool_key)
        assert kwargs["_expected_fingerprint"] == original.fingerprint

        candidate = _tool(
            adapter="openapi",
            source="https://source.example.test/openapi.json",
            description="breaking candidate is not installed",
        )
        report = compare_tool_specs(current, candidate)
        return SchemaRefreshResult(
            tool_key=tool_key,
            action="pending_review",
            applied=False,
            report=report,
        )

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(original.key, interval_seconds=60)

    first = await watcher.run_once()
    second = await watcher.run_once()

    assert first[0].status == "pending_review"
    assert second[0].status == "pending_review"
    assert registry.get(original.key).fingerprint == original.fingerprint
    assert calls == 2


@pytest.mark.asyncio
async def test_trusted_local_amendment_makes_existing_watch_stale_contract() -> None:
    router = SchemaRouter()
    original = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
    )
    router.add_tool(original)
    router.register_schema_watch(original.key, interval_seconds=60)

    amended = original.model_copy(deep=True)
    amended.endpoints[0].description = "trusted local annotation"
    router.amend_capability(original.key, amended)

    snapshots = await router.check_schema_watches_once()

    assert snapshots[0].status == "stale_contract"
    assert snapshots[0].last_error_type == "ToolContractChanged"


@pytest.mark.asyncio
async def test_direct_tool_replacement_clears_native_schema_refresh_state() -> None:
    router = SchemaRouter()
    original = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
    )
    router.add_tool(original)

    calls = 0

    async def refresh() -> tuple[ToolSpec, Any, bool]:
        nonlocal calls
        calls += 1
        return original, object(), False

    router._remember_native_schema_refresh(original.key, refresh)
    router._native_schema_lifecycle._pending[original.key] = (original, object(), False)  # type: ignore[arg-type]

    replacement = original.model_copy(deep=True)
    replacement.endpoints[0].description = "unvalidated replacement contract"
    assert replacement.fingerprint != original.fingerprint

    router.add_tool(replacement, replace=True)

    assert original.key not in router._native_schema_lifecycle._refreshers
    assert original.key not in router._native_schema_lifecycle._pending
    assert await router.check_native_schema_watches_once() == ()
    assert calls == 0


@pytest.mark.asyncio
async def test_same_source_credential_rotation_requires_watch_reregistration() -> None:
    registry = InMemoryRegistry()
    original = _tool(
        adapter="openapi",
        source="https://source.example.test/openapi.json",
    )
    registry.register(original)
    seen: list[dict[str, str] | None] = []

    async def refresh(tool_key: str, **kwargs: Any) -> SchemaRefreshResult:
        seen.append(kwargs["trusted_headers"])
        return _unchanged(registry.get(tool_key))

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(
        original.key,
        interval_seconds=60,
        trusted_headers={"Authorization": "Bearer old-watch-value"},
    )
    watcher.register(
        original.key,
        interval_seconds=60,
        trusted_headers={"Authorization": "Bearer new-watch-value"},
    )

    snapshots = await watcher.run_once()

    assert snapshots[0].status == "unchanged"
    assert seen == [{"Authorization": "Bearer new-watch-value"}]


@pytest.mark.asyncio
async def test_openapi_replacement_origin_never_receives_old_watch_headers() -> None:
    documents = {
        "source-a.example.test": {
            "openapi": "3.1.0",
            "info": {"title": "Remote", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "read",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        },
        "source-b.example.test": {
            "openapi": "3.1.0",
            "info": {"title": "Remote", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "get": {
                        "operationId": "read",
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
        },
    }
    requests: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            (
                request.url.host or "",
                request.headers.get("Authorization"),
            )
        )
        return httpx.Response(
            200,
            json=documents[request.url.host or ""],
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        original = await router.add_url(
            "https://source-a.example.test/openapi.json",
            kind="openapi",
            name="remote",
        )
        router.register_schema_watch(
            original.key,
            interval_seconds=60,
            schema_headers={"Authorization": "Bearer old-schema-watch-value"},
            trusted_headers={"Authorization": "Bearer old-runtime-watch-value"},
        )

        await router.add_url(
            "https://source-b.example.test/openapi.json",
            kind="openapi",
            name="remote",
            replace=True,
        )
        before_check = len(requests)

        snapshots = await router.check_schema_watches_once()

    assert len(requests) == before_check
    assert all(
        authorization is None
        for host, authorization in requests
        if host == "source-b.example.test"
    )
    assert snapshots[0].status == "stale_source"
    assert snapshots[0].last_error_type == "SourceIdentityChanged"
