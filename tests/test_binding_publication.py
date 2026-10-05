from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)
from schemarouter.adapters.base import AdapterLoadResult
import schemarouter.runtime as runtime_module


def _tool(name: str = "atomic", *, revision: int = 1) -> ToolSpec:
    return ToolSpec(
        name=name,
        metadata={"revision": revision},
        endpoints=[EndpointSpec(name="run", read_only=True)],
    )


def _fail_bind_for_fingerprint(router: SchemaRouter, monkeypatch, fingerprint: str) -> None:
    original = router.executor.bind

    def guarded_bind(
        tool_key,
        invoker,
        *,
        expected_fingerprint=None,
        offload_sync=False,
    ):
        if expected_fingerprint == fingerprint:
            raise RuntimeError("injected bind failure")
        return original(
            tool_key,
            invoker,
            expected_fingerprint=expected_fingerprint,
            offload_sync=offload_sync,
        )

    monkeypatch.setattr(router.executor, "bind", guarded_bind)


def test_add_bound_tool_rolls_back_new_registration_on_bind_failure(monkeypatch) -> None:
    router = SchemaRouter()
    tool = _tool()
    _fail_bind_for_fingerprint(router, monkeypatch, tool.fingerprint)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        router.add_bound_tool(tool, lambda endpoint, arguments: {"ok": True})

    assert tool.key not in router.registry.keys()
    assert tool.key not in router.executor.bound_keys()


@pytest.mark.asyncio
async def test_add_bound_tool_restores_previous_contract_and_binding(monkeypatch) -> None:
    router = SchemaRouter()
    original = _tool(revision=1)
    replacement = _tool(revision=2)
    router.add_bound_tool(
        original,
        lambda endpoint, arguments: {"revision": 1},
    )
    _fail_bind_for_fingerprint(router, monkeypatch, replacement.fingerprint)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        router.add_bound_tool(
            replacement,
            lambda endpoint, arguments: {"revision": 2},
            replace=True,
        )

    restored = router.registry.get(original.key)
    assert restored.fingerprint == original.fingerprint
    assert router.executor.binding_status_for_contract(
        original.key,
        original.fingerprint,
    ) == "ready"
    endpoint = restored.endpoint("run")
    result = await router.executor.execute_call(
        ToolCall(
            tool=original.key,
            endpoint="run",
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=restored.fingerprint,
        )
    )
    assert result.data == {"revision": 1}


def test_loader_commit_rolls_back_and_does_not_publish_validators(monkeypatch) -> None:
    router = SchemaRouter()
    tool = _tool("loader_new")
    remembered: list[str] = []
    monkeypatch.setattr(
        router.loader,
        "remember_tool_schema_http_validators",
        lambda committed: remembered.append(committed.key),
    )
    _fail_bind_for_fingerprint(router, monkeypatch, tool.fingerprint)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        router.loader._commit(
            AdapterLoadResult(
                tool=tool,
                invoker=lambda endpoint, arguments: {"ok": True},
            ),
            replace=False,
        )

    assert tool.key not in router.registry.keys()
    assert remembered == []


def test_loader_compare_and_swap_restores_previous_binding(monkeypatch) -> None:
    router = SchemaRouter()
    original = _tool("loader_replace", revision=1)
    candidate = _tool("loader_replace", revision=2)
    router.add_bound_tool(
        original,
        lambda endpoint, arguments: {"revision": 1},
    )
    expected_version = router.registry.version
    _fail_bind_for_fingerprint(router, monkeypatch, candidate.fingerprint)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        router.loader.commit_candidate_if_current(
            AdapterLoadResult(
                tool=candidate,
                invoker=lambda endpoint, arguments: {"revision": 2},
            ),
            expected_fingerprint=original.fingerprint,
            expected_version=expected_version,
        )

    assert router.registry.get(original.key).fingerprint == original.fingerprint
    assert router.executor.binding_status_for_contract(
        original.key,
        original.fingerprint,
    ) == "ready"


@pytest.mark.asyncio
async def test_mcp_client_factory_rolls_back_registration_on_bind_failure(
    monkeypatch,
) -> None:
    router = SchemaRouter()
    tool = _tool("mcp_factory")

    async def inspect(*args, **kwargs):
        return tool.model_copy(deep=True)

    monkeypatch.setattr(runtime_module, "inspect_mcp_client_factory", inspect)
    _fail_bind_for_fingerprint(router, monkeypatch, tool.fingerprint)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        await router.add_mcp_client_factory(lambda: None, name="mcp_factory")

    assert tool.key not in router.registry.keys()


@pytest.mark.asyncio
async def test_mcp_stdio_rolls_back_registration_on_bind_failure(monkeypatch) -> None:
    router = SchemaRouter()
    tool = _tool("mcp_stdio")

    async def inspect(*args, **kwargs):
        return tool.model_copy(deep=True)

    monkeypatch.setattr(runtime_module, "inspect_mcp_stdio", inspect)
    _fail_bind_for_fingerprint(router, monkeypatch, tool.fingerprint)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        await router.add_mcp_stdio(
            "echo",
            allowed_commands=("echo",),
            name="mcp_stdio",
        )

    assert tool.key not in router.registry.keys()
