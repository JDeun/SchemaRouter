from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from schemarouter import (
    BindingReconciliationError,
    EndpointSpec,
    RegistrationError,
    SchemaRouter,
    SQLiteRegistry,
    ToolSpec,
    TrustedBindingConfig,
)
from schemarouter.adapters.python import tool_from_callable
from schemarouter.integrations.langchain import tool_from_langchain
from schemarouter.integrations.llamaindex import tool_from_llamaindex


def _tool(
    name: str,
    adapter: str,
    *,
    execution_metadata: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    endpoint_execution_metadata: dict[str, Any] | None = None,
) -> ToolSpec:
    exec_meta = {"adapter": adapter, **(execution_metadata or {})}
    descriptive = {"adapter": adapter, **(metadata or {})}
    return ToolSpec(
        name=name,
        remote=adapter not in {"python"},
        execution_metadata=exec_meta,
        metadata=descriptive,
        endpoints=[
            EndpointSpec(
                name="invoke" if adapter in {"langchain_tool", "llamaindex_tool"} else "read",
                method="GET",
                path="/items",
                read_only=True,
                execution_metadata=dict(endpoint_execution_metadata or {}),
                output_schema={"type": "object"},
            )
        ],
    )


class _LangChainFixture:
    name = "langchain"
    description = ""

    def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return dict(arguments)


class _LlamaIndexFixture:
    metadata = SimpleNamespace(
        name="llamaindex",
        description="",
    )

    def call(self, **arguments: Any) -> dict[str, Any]:
        return dict(arguments)


class _BoundMCPFactory:
    @asynccontextmanager
    async def __call__(self, *, timeout: float = 20.0):
        del timeout
        yield SimpleNamespace(call_tool=lambda endpoint, arguments: None)


def _python_fixture() -> dict[str, str]:
    return {"ok": "yes"}


def _persisted_tools() -> list[ToolSpec]:
    return [
        _tool(
            "openapi",
            "openapi",
            execution_metadata={"approved_base_url": "https://api.example.test"},
            metadata={"source_url": "https://docs.example.test/openapi.json"},
        ),
        _tool(
            "graphql",
            "graphql",
            execution_metadata={"approved_endpoint_url": "https://gql.example.test/graphql"},
            metadata={"source_url": "https://gql.example.test/graphql"},
        ),
        _tool(
            "odata",
            "odata",
            execution_metadata={"approved_base_url": "https://odata.example.test"},
            metadata={
                "source_url": "https://odata.example.test/$metadata",
                "service_url": "https://odata.example.test",
            },
        ),
        _tool(
            "openrpc",
            "openrpc",
            execution_metadata={"approved_base_url": "https://rpc.example.test/rpc"},
            metadata={"source_url": "https://rpc.example.test/openrpc.json"},
        ),
        _tool(
            "optimade",
            "optimade",
            execution_metadata={"versioned_base_url": "https://optimade.example.test/v1"},
            metadata={"versioned_base_url": "https://optimade.example.test/v1"},
        ),
        _tool(
            "http_json",
            "http_json",
            execution_metadata={"approved_base_url": "https://json.example.test"},
            metadata={"approved_base_url": "https://json.example.test"},
        ),
        _tool(
            "mcp_http",
            "mcp",
            execution_metadata={
                "transport": "streamable_http",
                "source_url": "https://mcp.example.test/mcp",
                "authenticated_transport": True,
            },
            metadata={
                "transport": "streamable_http",
                "source_url": "https://mcp.example.test/mcp",
                "authenticated_transport": True,
            },
        ),
        _tool(
            "mcp_bound",
            "mcp",
            execution_metadata={
                "transport": "custom",
                "transport_fingerprint": "bound-transport-v1",
            },
            metadata={
                "transport": "custom",
                "transport_fingerprint": "bound-transport-v1",
            },
        ),
        _tool(
            "mcp_stdio",
            "mcp",
            execution_metadata={
                "transport": "stdio",
                "transport_fingerprint": "stdio-transport-v1",
            },
            metadata={
                "transport": "stdio",
                "transport_fingerprint": "stdio-transport-v1",
            },
        ),
        tool_from_callable(
            _python_fixture,
            name="python",
            read_only=True,
        ),
        tool_from_langchain(
            _LangChainFixture(),
            name="langchain",
            read_only=True,
        ),
        tool_from_llamaindex(
            _LlamaIndexFixture(),
            name="llamaindex",
            read_only=True,
        ),
        _tool("private_sdk", "private_sdk"),
    ]


def test_sqlite_restart_rehydrates_all_builtin_binding_families(tmp_path) -> None:
    path = tmp_path / "registry.sqlite3"
    tools = _persisted_tools()
    with SQLiteRegistry(path) as registry:
        registry.update_many(tools)
        persisted_version = registry.version

    secret = "runtime-only-secret"
    bound_factory = _BoundMCPFactory()
    langchain_tool = _LangChainFixture()
    llamaindex_tool = _LlamaIndexFixture()

    def generic_invoker(endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return {"endpoint": endpoint, **arguments}

    configs = {
        "openapi": TrustedBindingConfig(),
        "graphql": TrustedBindingConfig(),
        "odata": TrustedBindingConfig(),
        "openrpc": TrustedBindingConfig(),
        "optimade": TrustedBindingConfig(),
        "http_json": TrustedBindingConfig(),
        "mcp_http": TrustedBindingConfig(
            trusted_headers={"Authorization": f"Bearer {secret}"},
        ),
        "mcp_bound": TrustedBindingConfig(
            mcp_bound_factory=bound_factory,
            mcp_transport_fingerprint="bound-transport-v1",
        ),
        "mcp_stdio": TrustedBindingConfig(
            mcp_bound_factory=bound_factory,
            mcp_transport_fingerprint="stdio-transport-v1",
        ),
        "python": TrustedBindingConfig(python_callable=_python_fixture),
        "langchain": TrustedBindingConfig(langchain_tool=langchain_tool),
        "llamaindex": TrustedBindingConfig(llamaindex_tool=llamaindex_tool),
        "private_sdk": TrustedBindingConfig(invoker=generic_invoker),
    }

    with SQLiteRegistry(path) as registry:
        router = SchemaRouter(registry=registry)
        before_documents = {
            tool.key: tool.model_dump_json()
            for tool in registry.tools()
        }

        report = router.rehydrate_bindings(
            lambda tool: configs[tool.key],
            strict=True,
        )

        assert registry.version == persisted_version
        assert set(report.ready) == set(configs)
        assert report.unready == ()
        for tool in registry.tools():
            assert router.executor.binding_status_for_contract(
                tool.key,
                tool.fingerprint,
            ) == "ready"
            assert tool.model_dump_json() == before_documents[tool.key]
            assert secret not in tool.model_dump_json()


def test_bind_existing_intentionally_unbound_clears_old_process_binding() -> None:
    router = SchemaRouter()
    tool = _tool("sdk", "private_sdk")
    router.add_tool(tool)

    router.executor.bind(
        tool.key,
        lambda endpoint, arguments: arguments,
        expected_fingerprint=tool.fingerprint,
    )
    assert router.executor.binding_status_for_contract(tool.key, tool.fingerprint) == "ready"

    item = router.bind_existing(
        tool.key,
        TrustedBindingConfig(intentionally_unbound=True),
    )

    assert item.status == "intentionally_unbound"
    assert router.executor.binding_status_for_contract(tool.key, tool.fingerprint) == "unbound"


def test_rehydrate_reports_missing_config_and_strict_mode_fails() -> None:
    router = SchemaRouter()
    first = _tool("first", "private_sdk")
    second = _tool("second", "private_sdk")
    router.add_tool(first)
    router.add_tool(second)

    report = router.rehydrate_bindings(
        lambda tool: (
            TrustedBindingConfig(
                invoker=lambda endpoint, arguments: arguments,
            )
            if tool.key == "first"
            else None
        )
    )

    statuses = {item.tool: item.status for item in report.items}
    assert statuses == {
        "first": "ready",
        "second": "missing_trusted_config",
    }

    with pytest.raises(RegistrationError, match="second=missing_trusted_config"):
        router.rehydrate_bindings(
            lambda tool: (
                TrustedBindingConfig(
                    invoker=lambda endpoint, arguments: arguments,
                )
                if tool.key == "first"
                else None
            ),
            required_tools=["first", "second"],
            strict=True,
        )


def test_rehydrate_required_tools_rejects_unknown_registry_key() -> None:
    router = SchemaRouter()
    router.add_tool(_tool("known", "private_sdk"))

    with pytest.raises(RegistrationError, match="absent"):
        router.rehydrate_bindings(
            lambda tool: TrustedBindingConfig(intentionally_unbound=True),
            required_tools=["known", "absent"],
            strict=True,
        )


def test_mcp_bound_transport_fingerprint_mismatch_is_incompatible() -> None:
    router = SchemaRouter()
    tool = _tool(
        "mcp_bound",
        "mcp",
        execution_metadata={
            "transport": "custom",
            "transport_fingerprint": "expected-v1",
        },
        metadata={
            "transport": "custom",
            "transport_fingerprint": "expected-v1",
        },
    )
    router.add_tool(tool)

    item = router.bind_existing(
        tool.key,
        TrustedBindingConfig(
            mcp_bound_factory=_BoundMCPFactory(),
            mcp_transport_fingerprint="wrong-v2",
        ),
    )

    assert item.status == "incompatible"
    assert item.error_type == "ValueError"
    assert router.executor.binding_status_for_contract(tool.key, tool.fingerprint) == "unbound"


def test_mcp_http_custom_factory_requirement_survives_restart() -> None:
    router = SchemaRouter()
    tool = _tool(
        "mcp_http_custom",
        "mcp",
        execution_metadata={
            "transport": "streamable_http",
            "source_url": "https://mcp.example.test/mcp",
            "custom_client_factory_required": True,
        },
        metadata={
            "transport": "streamable_http",
            "source_url": "https://mcp.example.test/mcp",
            "custom_client_factory_required": True,
        },
    )
    router.add_tool(tool)

    missing = router.bind_existing(tool.key, TrustedBindingConfig())

    assert missing.status == "missing_trusted_config"

    ready = router.bind_existing(
        tool.key,
        TrustedBindingConfig(
            mcp_http_client_factory=lambda *args, **kwargs: None,
        ),
    )

    assert ready.status == "ready"


def test_authenticated_mcp_http_requires_runtime_headers_after_restart() -> None:
    router = SchemaRouter()
    tool = _tool(
        "mcp_http",
        "mcp",
        execution_metadata={
            "transport": "streamable_http",
            "source_url": "https://mcp.example.test/mcp",
            "authenticated_transport": True,
        },
        metadata={
            "transport": "streamable_http",
            "source_url": "https://mcp.example.test/mcp",
            "authenticated_transport": True,
        },
    )
    router.add_tool(tool)

    item = router.bind_existing(tool.key, TrustedBindingConfig())

    assert item.status == "missing_trusted_config"
    assert router.executor.binding_status_for_contract(tool.key, tool.fingerprint) == "unbound"


def test_openrpc_without_approved_or_supplied_base_url_is_missing_config() -> None:
    router = SchemaRouter()
    tool = _tool(
        "rpc",
        "openrpc",
        metadata={"source_url": "https://rpc.example.test/openrpc.json"},
    )
    router.add_tool(tool)

    item = router.bind_existing(tool.key, TrustedBindingConfig())

    assert item.status == "missing_trusted_config"

    ready = router.bind_existing(
        tool.key,
        TrustedBindingConfig(base_url="https://rpc.example.test/rpc"),
    )
    assert ready.status == "ready"


def test_bind_existing_detects_registry_drift_before_storing_invoker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    tool = _tool("sdk", "private_sdk")
    router.add_tool(tool)

    def build(current: ToolSpec, config: TrustedBindingConfig):
        del config
        replacement = current.model_copy(deep=True)
        replacement.description = "concurrent change"
        router.registry.register(replacement, replace=True)
        return lambda endpoint, arguments: arguments

    monkeypatch.setattr(router, "_build_existing_invoker", build)

    item = router.bind_existing(
        tool.key,
        TrustedBindingConfig(invoker=lambda endpoint, arguments: arguments),
    )

    assert item.status == "incompatible"
    assert item.error_type == "BindingDriftError"
    assert router.executor.binding_status_for_contract(
        tool.key,
        router.registry.get(tool.key).fingerprint,
    ) == "unbound"


def test_resolver_receives_detached_tool_snapshot() -> None:
    router = SchemaRouter()
    tool = _tool("sdk", "private_sdk")
    router.add_tool(tool)

    def resolver(snapshot: ToolSpec) -> TrustedBindingConfig:
        snapshot.description = "mutated resolver copy"
        return TrustedBindingConfig(
            invoker=lambda endpoint, arguments: arguments,
        )

    report = router.rehydrate_bindings(resolver)

    assert report.ready == ("sdk",)
    assert router.registry.get(tool.key).description == ""


def test_resolver_failure_is_reported_without_leaking_exception_text() -> None:
    router = SchemaRouter()
    tool = _tool("sdk", "private_sdk")
    router.add_tool(tool)

    def resolver(snapshot: ToolSpec):
        del snapshot
        raise RuntimeError("sensitive resolver detail")

    report = router.rehydrate_bindings(resolver)

    assert report.items[0].status == "failed"
    assert report.items[0].error_type == "RuntimeError"
    assert "sensitive resolver detail" not in report.model_dump_json()


def test_wrong_framework_object_identity_is_incompatible() -> None:
    router = SchemaRouter()
    tool = _tool(
        "langchain",
        "langchain_tool",
        metadata={
            "foreign_tool_module": "expected.module",
            "foreign_tool_class": "ExpectedClass",
        },
    )
    router.add_tool(tool)

    item = router.bind_existing(
        tool.key,
        TrustedBindingConfig(langchain_tool=_LangChainFixture()),
    )

    assert item.status == "incompatible"
    assert item.error_type == "ValueError"


def test_builtin_adapter_cannot_bypass_rebinding_checks_with_generic_invoker() -> None:
    router = SchemaRouter()
    tool = _tool(
        "openapi_bypass",
        "openapi",
        execution_metadata={"approved_base_url": "https://api.example.test"},
    )
    router.add_tool(tool)

    item = router.bind_existing(
        tool.key,
        TrustedBindingConfig(
            invoker=lambda endpoint, arguments: arguments,
        ),
    )

    assert item.status == "incompatible"
    assert item.error_type == "ValueError"
    assert (
        router.executor.binding_status_for_contract(
            tool.key,
            tool.fingerprint,
        )
        == "unbound"
    )


def test_intentionally_unbound_does_not_delete_stale_binding() -> None:
    router = SchemaRouter()
    tool = _tool("private", "private_sdk")
    router.add_tool(tool)
    router.executor.bind(
        tool.key,
        lambda endpoint, arguments: arguments,
        expected_fingerprint=tool.fingerprint,
    )

    replacement = tool.model_copy(deep=True)
    replacement.description = "concurrent replacement"
    router.registry.register(replacement, replace=True)

    item = router.bind_existing(
        tool.key,
        TrustedBindingConfig(intentionally_unbound=True),
    )

    assert item.status == "incompatible"
    assert item.error_type == "BindingDriftError"
    assert (
        router.executor.binding_status_for_contract(
            tool.key,
            tool.fingerprint,
        )
        == "ready"
    )


def test_rehydrate_skips_resolver_for_already_ready_contract() -> None:
    router = SchemaRouter()
    tool = _tool("private", "private_sdk")
    router.add_tool(tool)
    router.executor.bind(
        tool.key,
        lambda endpoint, arguments: arguments,
        expected_fingerprint=tool.fingerprint,
    )

    calls = 0

    def resolver(snapshot: ToolSpec):
        nonlocal calls
        del snapshot
        calls += 1
        raise AssertionError("ready binding must not be rebuilt")

    report = router.rehydrate_bindings(resolver)

    assert calls == 0
    assert report.ready == (tool.key,)


def test_openapi_rebinding_reuses_router_injected_http_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import schemarouter.runtime as runtime_module

    sentinel_client = object()
    captured: dict[str, object] = {}

    def build_invoker(
        tool,
        base_url,
        *,
        trusted_headers=None,
        timeout=20.0,
        max_response_bytes=10 * 1024 * 1024,
        http_client=None,
    ):
        del tool, base_url, trusted_headers, timeout, max_response_bytes
        captured["http_client"] = http_client
        return lambda endpoint, arguments: arguments

    monkeypatch.setattr(runtime_module, "OpenAPIRemoteInvoker", build_invoker)

    router = SchemaRouter(http_client=sentinel_client)  # type: ignore[arg-type]
    tool = _tool(
        "openapi_client",
        "openapi",
        execution_metadata={"approved_base_url": "https://api.example.test"},
    )
    router.add_tool(tool)

    item = router.bind_existing(tool.key, TrustedBindingConfig())

    assert item.status == "ready"
    assert captured["http_client"] is sentinel_client


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout": True},
        {"timeout": float("inf")},
        {"max_response_bytes": True},
    ],
)
def test_trusted_binding_config_rejects_non_numeric_runtime_limits(
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        TrustedBindingConfig(**kwargs)  # type: ignore[arg-type]


def test_trusted_binding_config_rejects_ambiguous_generic_invoker() -> None:
    with pytest.raises(ValueError, match="generic invoker"):
        TrustedBindingConfig(
            invoker=lambda endpoint, arguments: arguments,
            base_url="https://api.example.test",
        )



def test_trusted_binding_config_repr_redacts_secrets_and_live_objects() -> None:
    secret = "binding-super-secret"
    live = object()
    config = TrustedBindingConfig(
        trusted_headers={"Authorization": f"Bearer {secret}"},
        mcp_http_client_factory=live,
    )

    rendered = repr(config)

    assert secret not in rendered
    assert "Authorization" not in rendered
    assert hex(id(live)) not in rendered


def test_strict_reconciliation_error_retains_safe_report() -> None:
    router = SchemaRouter()
    tool = _tool("required", "private_sdk")
    router.add_tool(tool)

    with pytest.raises(BindingReconciliationError) as excinfo:
        router.rehydrate_bindings(
            lambda snapshot: None,
            required_tools=[tool.key],
            strict=True,
        )

    report = excinfo.value.report
    assert report.items[0].tool == tool.key
    assert report.items[0].status == "missing_trusted_config"
    assert "required=missing_trusted_config" in str(excinfo.value)



def test_python_rebinding_rejects_same_identity_with_changed_schema() -> None:
    router = SchemaRouter()
    persisted = tool_from_callable(
        _python_fixture,
        name="python_changed",
        read_only=True,
    )
    router.add_tool(persisted)

    def changed(extra: str) -> dict[str, str]:
        return {"extra": extra}

    changed.__module__ = _python_fixture.__module__
    changed.__qualname__ = _python_fixture.__qualname__

    item = router.bind_existing(
        persisted.key,
        TrustedBindingConfig(python_callable=changed),
    )

    assert item.status == "incompatible"
    assert item.error_type == "ValueError"
    assert (
        router.executor.binding_status_for_contract(
            persisted.key,
            persisted.fingerprint,
        )
        == "unbound"
    )


def test_python_rebinding_accepts_trusted_amendment_overlay() -> None:
    router = SchemaRouter()
    key = router.add_callable(
        _python_fixture,
        name="python_amended",
        read_only=True,
    )
    current = router.registry.get(key)
    endpoint = current.endpoints[0]
    amended = current.model_copy(
        update={
            "endpoints": [
                endpoint.model_copy(
                    update={"description": "trusted local annotation"}
                )
            ]
        }
    )
    router.amend_capability(key, amended)
    effective = router.registry.get(key)
    router.executor.unbind(key)

    item = router.bind_existing(
        key,
        TrustedBindingConfig(python_callable=_python_fixture),
    )

    assert item.status == "ready"
    assert router.registry.get(key).fingerprint == effective.fingerprint
    assert router.executor.is_binding_ready_for_contract(
        key,
        effective.fingerprint,
    )


@pytest.mark.parametrize("framework", ["langchain", "llamaindex"])
def test_framework_rebinding_rejects_live_schema_mismatch(
    framework: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    if framework == "langchain":
        live = _LangChainFixture()
        persisted = tool_from_langchain(
            live,
            name="framework",
            read_only=True,
        )
        import schemarouter.integrations.langchain as integration
        config = TrustedBindingConfig(langchain_tool=live)
    else:
        live = _LlamaIndexFixture()
        persisted = tool_from_llamaindex(
            live,
            name="framework",
            read_only=True,
        )
        import schemarouter.integrations.llamaindex as integration
        config = TrustedBindingConfig(llamaindex_tool=live)

    router.add_tool(persisted)
    original_compiler = (
        integration.tool_from_langchain
        if framework == "langchain"
        else integration.tool_from_llamaindex
    )

    def mismatched(*args, **kwargs):
        rebuilt = original_compiler(*args, **kwargs)
        rebuilt.description = "changed live schema identity"
        return rebuilt

    compiler_name = (
        "tool_from_langchain"
        if framework == "langchain"
        else "tool_from_llamaindex"
    )
    monkeypatch.setattr(integration, compiler_name, mismatched)

    item = router.bind_existing(persisted.key, config)

    assert item.status == "incompatible"
    assert item.error_type == "ValueError"



def test_rehydrate_refuses_config_created_for_concurrently_replaced_snapshot() -> None:
    router = SchemaRouter()
    original = _tool("private_race", "private_sdk")
    router.add_tool(original)

    def resolver(snapshot: ToolSpec) -> TrustedBindingConfig:
        assert snapshot.fingerprint == original.fingerprint
        replacement = snapshot.model_copy(deep=True)
        replacement.description = "concurrent replacement"
        router.registry.register(replacement, replace=True)
        return TrustedBindingConfig(
            invoker=lambda endpoint, arguments: arguments,
        )

    report = router.rehydrate_bindings(resolver)

    assert report.items[0].status == "incompatible"
    assert report.items[0].error_type == "BindingDriftError"
    current = router.registry.get(original.key)
    assert current.fingerprint != original.fingerprint
    assert (
        router.executor.binding_status_for_contract(
            current.key,
            current.fingerprint,
        )
        == "unbound"
    )


def test_bind_existing_can_pin_caller_reviewed_fingerprint() -> None:
    router = SchemaRouter()
    original = _tool("private_pin", "private_sdk")
    router.add_tool(original)
    replacement = original.model_copy(deep=True)
    replacement.description = "replacement"
    router.registry.register(replacement, replace=True)

    item = router.bind_existing(
        original.key,
        TrustedBindingConfig(
            invoker=lambda endpoint, arguments: arguments,
        ),
        expected_fingerprint=original.fingerprint,
    )

    assert item.status == "incompatible"
    assert item.error_type == "BindingDriftError"
