from __future__ import annotations

import httpx
import pytest

from schemarouter import SchemaRouter
from schemarouter.adapters.base import AdapterLoadResult
from schemarouter.errors import SchemaSourceError


def _document(
    *,
    method: str = "get",
    required_query: bool = False,
    summary: str | None = None,
) -> dict:
    return {
        "openapi": "3.1.0",
        "info": {"title": "Review API", "version": "1.0.0"},
        "servers": [{"url": "https://example.test"}],
        "paths": {
            "/materials": {
                method: {
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
async def test_accept_pending_refetches_and_applies_exact_reviewed_candidate() -> None:
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
        accepted_fingerprint = tool.fingerprint
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(required_query=True)
        await router.check_schema_watches_once()
        pending = router.schema_watch_pending_review(tool.key)

        assert pending is not None
        assert pending.candidate_fingerprint is not None
        assert pending.reviewed_current_fingerprint == accepted_fingerprint
        assert pending.candidate_source_identity is not None

        result = await router.aaccept_schema_watch_pending(
            tool.key,
            expected_candidate_fingerprint=pending.candidate_fingerprint,
        )

    current = router.registry.get(tool.key)
    snapshot = router.schema_watch_snapshots()[0]
    assert result.action == "applied"
    assert result.compatibility == "breaking"
    assert current.fingerprint == pending.candidate_fingerprint
    assert current.endpoint("materials_search").parameters[0].required is True
    assert router.executor.binding_status_for_contract(
        tool.key,
        current.fingerprint,
    ) == "ready"
    assert snapshot.status == "applied"
    assert snapshot.pending_review is False
    assert snapshot.pending_candidate_fingerprint is None


@pytest.mark.asyncio
async def test_reject_pending_clears_only_the_reviewed_candidate() -> None:
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
        accepted_fingerprint = tool.fingerprint
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(required_query=True)
        await router.check_schema_watches_once()
        pending = router.schema_watch_pending_review(tool.key)
        assert pending is not None
        assert pending.candidate_fingerprint is not None

        rejected = await router.areject_schema_watch_pending(
            tool.key,
            expected_candidate_fingerprint=pending.candidate_fingerprint,
        )

    snapshot = router.schema_watch_snapshots()[0]
    assert rejected.candidate_fingerprint == pending.candidate_fingerprint
    assert router.registry.get(tool.key).fingerprint == accepted_fingerprint
    assert router.schema_watch_pending_review(tool.key) is None
    assert snapshot.status == "rejected"
    assert snapshot.pending_review is False


@pytest.mark.asyncio
async def test_accept_pending_fails_closed_after_registry_mutation() -> None:
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
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(required_query=True)
        await router.check_schema_watches_once()
        pending = router.schema_watch_pending_review(tool.key)
        assert pending is not None
        assert pending.candidate_fingerprint is not None

        concurrent = router.registry.get(tool.key).model_copy(deep=True)
        concurrent.description = "concurrent trusted writer"
        router.registry.register(concurrent, replace=True)

        with pytest.raises(SchemaSourceError, match="changed before pending schema approval"):
            await router.aaccept_schema_watch_pending(
                tool.key,
                expected_candidate_fingerprint=pending.candidate_fingerprint,
            )

    snapshot = router.schema_watch_snapshots()[0]
    assert snapshot.status == "stale_contract"
    assert snapshot.pending_review is False


@pytest.mark.asyncio
async def test_candidate_change_before_approval_returns_to_pending_review() -> None:
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
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(required_query=True)
        await router.check_schema_watches_once()
        first = router.schema_watch_pending_review(tool.key)
        assert first is not None
        assert first.candidate_fingerprint is not None

        state["document"] = _document(method="post")
        result = await router.aaccept_schema_watch_pending(
            tool.key,
            expected_candidate_fingerprint=first.candidate_fingerprint,
        )

    second = router.schema_watch_pending_review(tool.key)
    assert result.action == "pending_review"
    assert second is not None
    assert second.candidate_fingerprint is not None
    assert second.candidate_fingerprint != first.candidate_fingerprint
    assert any(
        change.kind == "candidate_changed_before_approval"
        for change in second.report.changes
    )
    assert router.registry.get(tool.key).fingerprint == tool.fingerprint


@pytest.mark.asyncio
async def test_accept_pending_refuses_same_contract_from_different_source_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(required_query=True)
        await router.check_schema_watches_once()
        pending = router.schema_watch_pending_review(tool.key)

        assert pending is not None
        assert pending.candidate_fingerprint is not None
        assert pending.candidate_source_identity is not None

        reviewed = await router.loader.inspect(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        relocated = reviewed.tool.model_copy(deep=True)
        relocated.metadata["source_url"] = "https://other.example/openapi.json"
        relocated.metadata["resolved_schema_url"] = (
            "https://other.example/openapi.json"
        )
        assert relocated.fingerprint == pending.candidate_fingerprint

        async def inspect_other(*args, **kwargs):
            del args, kwargs
            return AdapterLoadResult(
                tool=relocated,
                invoker=reviewed.invoker,
            )

        monkeypatch.setattr(router.loader, "inspect", inspect_other)

        result = await router.aaccept_schema_watch_pending(
            tool.key,
            expected_candidate_fingerprint=pending.candidate_fingerprint,
        )

    current = router.registry.get(tool.key)
    refreshed_pending = router.schema_watch_pending_review(tool.key)
    assert result.action == "pending_review"
    assert result.compatibility == "security_review"
    assert current.fingerprint == tool.fingerprint
    assert refreshed_pending is not None
    assert (
        refreshed_pending.candidate_fingerprint
        == pending.candidate_fingerprint
    )
    assert (
        refreshed_pending.candidate_source_identity
        != pending.candidate_source_identity
    )
    assert any(
        change.kind == "candidate_source_changed_before_approval"
        for change in result.report.changes
    )


@pytest.mark.asyncio
async def test_security_review_requires_explicit_acceptance() -> None:
    state = {"document": _document(method="get")}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=state["document"], request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        tool = await router.add_url(
            "https://example.test/openapi.json",
            kind="openapi",
            name="materials",
        )
        router.register_schema_watch(tool.key, interval_seconds=60)

        state["document"] = _document(method="post")
        snapshots = await router.check_schema_watches_once()
        pending = router.schema_watch_pending_review(tool.key)

        assert snapshots[0].last_compatibility == "security_review"
        assert pending is not None
        assert pending.candidate_fingerprint is not None
        assert router.registry.get(tool.key).endpoint("materials_search").method == "GET"

        result = await router.aaccept_schema_watch_pending(
            tool.key,
            expected_candidate_fingerprint=pending.candidate_fingerprint,
        )

    assert result.action == "applied"
    assert result.compatibility == "security_review"
    assert router.registry.get(tool.key).endpoint("materials_search").method == "POST"


@pytest.mark.asyncio
async def test_reject_refuses_wrong_candidate_fingerprint() -> None:
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
        router.register_schema_watch(tool.key, interval_seconds=60)
        state["document"] = _document(required_query=True)
        await router.check_schema_watches_once()

        with pytest.raises(SchemaSourceError, match="does not match"):
            await router.areject_schema_watch_pending(
                tool.key,
                expected_candidate_fingerprint="0" * 64,
            )

    assert router.schema_watch_pending_review(tool.key) is not None


def test_pending_snapshot_exposes_identity_without_transport_secrets() -> None:
    from schemarouter.ingestion import default_adapter_registry
    from schemarouter.models import EndpointSpec, ToolSpec
    from schemarouter.registry import InMemoryRegistry
    from schemarouter.schema_diff import SchemaDiffReport, SchemaRefreshResult
    from schemarouter.schema_watch import SchemaWatchManager

    registry = InMemoryRegistry()
    tool = ToolSpec(
        name="remote",
        remote=True,
        execution_metadata={"adapter": "openapi"},
        metadata={
            "adapter": "openapi",
            "source_url": "https://example.test/openapi.json",
        },
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )
    registry.register(tool)

    async def refresh(*args, **kwargs):
        del args, kwargs
        return SchemaRefreshResult(
            tool_key=tool.key,
            action="pending_review",
            applied=False,
            report=SchemaDiffReport(
                compatibility="breaking",
                old_fingerprint=tool.fingerprint,
                new_fingerprint="b" * 64,
                changes=[],
            ),
            reviewed_current_fingerprint=tool.fingerprint,
            candidate_fingerprint="b" * 64,
            candidate_source_identity="c" * 64,
        )

    watcher = SchemaWatchManager(registry, refresh, default_adapter_registry())
    watcher.register(
        tool.key,
        schema_headers={"Authorization": "Bearer schema-secret"},
        trusted_headers={"Authorization": "Bearer runtime-secret"},
    )

    # The safe identity fields are observable after a normal run, while
    # credential values remain private to the watch record.
    import asyncio

    asyncio.run(watcher.run_once())
    snapshot = watcher.snapshots()[0]
    rendered = repr(snapshot)

    assert snapshot.pending_candidate_fingerprint == "b" * 64
    assert snapshot.pending_candidate_source_identity == "c" * 64
    assert "schema-secret" not in rendered
    assert "runtime-secret" not in rendered
