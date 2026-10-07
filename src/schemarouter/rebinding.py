from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from .adapters.mcp import MCPBoundInvoker, MCPRemoteInvoker
from .adapters.openapi import OpenAPIRemoteInvoker
from .adapters.python import PythonCallableInvoker, tool_from_callable
from .amendment_overlay import strip_amendment_overlay
from .binding_reconciliation import TrustedBindingConfig
from .executor import BoundEndpointInvoker
from .models import ToolSpec
from .network_policy import NetworkPolicy


@dataclass(frozen=True, slots=True)
class RebindingContext:
    """Runtime-owned dependencies available to trusted rebinding strategies."""

    http_client: httpx.AsyncClient | None
    network_policy: NetworkPolicy


RebindingStrategy = Callable[
    [ToolSpec, TrustedBindingConfig, RebindingContext],
    BoundEndpointInvoker,
]

_REBINDING_STRATEGIES: dict[str, RebindingStrategy] = {}


def persisted_adapter(tool: ToolSpec) -> str | None:
    """Return the normalized persisted adapter identity, if present."""

    adapter = tool.execution_metadata.get("adapter")
    if not isinstance(adapter, str):
        adapter = tool.metadata.get("adapter")
    if isinstance(adapter, str) and adapter.strip():
        return adapter.strip().lower()
    return None


def persisted_url(tool: ToolSpec, *keys: str) -> str | None:
    """Read a persisted URL-like value without treating it as runtime authority."""

    for key in keys:
        value = tool.execution_metadata.get(key)
        if isinstance(value, str) and value:
            return value
        value = tool.metadata.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def register_rebinding_strategy(
    adapter: str,
    strategy: RebindingStrategy,
    *,
    replace: bool = False,
) -> None:
    """Register one trusted persisted-adapter rebinding strategy."""

    normalized = adapter.strip().lower()
    if not normalized:
        raise ValueError("adapter must be non-empty")
    if normalized in _REBINDING_STRATEGIES and not replace:
        raise ValueError(f"rebinding strategy already registered for {normalized!r}")
    _REBINDING_STRATEGIES[normalized] = strategy


def registered_rebinding_adapters() -> tuple[str, ...]:
    return tuple(sorted(_REBINDING_STRATEGIES))


def build_existing_invoker(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    """Build a trusted live invoker for one persisted capability."""

    adapter = persisted_adapter(tool)
    strategy = _REBINDING_STRATEGIES.get(adapter or "")

    if config.invoker is not None:
        if strategy is not None:
            raise ValueError(
                "built-in persisted capabilities must use their adapter-specific "
                "trusted rebinding path"
            )
        return config.invoker

    if strategy is None:
        raise LookupError(
            f"adapter {adapter or '<unknown>'!r} requires an explicit trusted invoker"
        )
    return strategy(tool, config, context)


def _rebind_openapi(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    base_url = config.base_url or persisted_url(tool, "approved_base_url")
    if base_url is None:
        raise LookupError("OpenAPI binding requires a trusted base_url")
    return OpenAPIRemoteInvoker(
        tool,
        base_url,
        trusted_headers=dict(config.trusted_headers or {}),
        timeout=config.timeout,
        max_response_bytes=config.max_response_bytes,
        http_client=context.http_client,
        network_policy=context.network_policy,
    )


def _rebind_graphql(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    from .adapters.graphql import GraphQLRemoteInvoker

    endpoint_url = config.base_url or persisted_url(
        tool,
        "approved_endpoint_url",
        "source_url",
    )
    if endpoint_url is None:
        raise LookupError("GraphQL binding is missing its execution endpoint")
    return GraphQLRemoteInvoker(
        tool,
        endpoint_url,
        trusted_headers=dict(config.trusted_headers or {}),
        timeout=config.timeout,
        max_response_bytes=config.max_response_bytes,
        http_client=context.http_client,
        network_policy=context.network_policy,
    )


def _rebind_odata(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    from .adapters.odata import ODataRemoteInvoker

    service_url = config.base_url or persisted_url(
        tool,
        "approved_base_url",
        "service_url",
    )
    if service_url is None:
        raise LookupError("OData binding is missing its service URL")
    return ODataRemoteInvoker(
        tool,
        service_url,
        trusted_headers=dict(config.trusted_headers or {}),
        timeout=config.timeout,
        max_response_bytes=config.max_response_bytes,
        http_client=context.http_client,
        network_policy=context.network_policy,
    )


def _rebind_openrpc(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    from .adapters.openrpc import OpenRPCRemoteInvoker

    base_url = config.base_url or persisted_url(tool, "approved_base_url")
    if base_url is None:
        raise LookupError("OpenRPC binding requires a trusted base_url")
    return OpenRPCRemoteInvoker(
        tool,
        base_url,
        trusted_headers=dict(config.trusted_headers or {}),
        timeout=config.timeout,
        max_response_bytes=config.max_response_bytes,
        http_client=context.http_client,
        network_policy=context.network_policy,
    )


def _rebind_optimade(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    from .adapters.optimade import OPTIMADERemoteInvoker

    versioned_base_url = config.base_url or persisted_url(tool, "versioned_base_url")
    if versioned_base_url is None:
        raise LookupError("OPTIMADE binding is missing its versioned base URL")
    return OPTIMADERemoteInvoker(
        tool,
        versioned_base_url,
        trusted_headers=dict(config.trusted_headers or {}),
        timeout=config.timeout,
        http_client=context.http_client,
        network_policy=context.network_policy,
    )


def _rebind_http_json(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    from .adapters.http_json import build_http_json_invoker

    base_url = config.base_url or persisted_url(tool, "approved_base_url")
    if base_url is None:
        raise LookupError("HTTP/JSON binding requires a trusted base_url")
    return build_http_json_invoker(
        tool,
        base_url=base_url,
        trusted_headers=dict(config.trusted_headers or {}),
        timeout=config.timeout,
        max_response_bytes=config.max_response_bytes,
        http_client=context.http_client,
        network_policy=context.network_policy,
    )


def _rebind_mcp(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    transport = persisted_url(tool, "transport") or "custom"
    persisted_transport_fingerprint = persisted_url(tool, "transport_fingerprint")
    if transport == "streamable_http":
        source_url = config.base_url or persisted_url(tool, "source_url")
        if source_url is None:
            raise LookupError("MCP HTTP binding is missing its source URL")
        authenticated = bool(
            tool.execution_metadata.get("authenticated_transport")
            or tool.metadata.get("authenticated_transport")
        )
        headers = dict(config.trusted_headers or {})
        if authenticated and not headers:
            raise LookupError(
                "MCP HTTP binding requires trusted headers after restart"
            )
        custom_factory_required = bool(
            tool.execution_metadata.get("custom_client_factory_required")
            or tool.metadata.get("custom_client_factory_required")
        )
        if custom_factory_required and config.mcp_http_client_factory is None:
            raise LookupError(
                "MCP HTTP binding requires its caller-owned client factory "
                "after restart"
            )
        return MCPRemoteInvoker(
            source_url,
            trusted_headers=headers,
            timeout=config.timeout,
            client_factory=config.mcp_http_client_factory,
            network_policy=context.network_policy,
        )

    if config.mcp_bound_factory is None:
        raise LookupError(
            "MCP stdio/custom binding requires a caller-owned bound factory"
        )
    if persisted_transport_fingerprint is not None:
        if config.mcp_transport_fingerprint is None:
            raise LookupError(
                "MCP bound transport requires its trusted transport fingerprint"
            )
        if config.mcp_transport_fingerprint != persisted_transport_fingerprint:
            raise ValueError(
                "MCP bound transport fingerprint does not match persisted contract"
            )
    return MCPBoundInvoker(
        config.mcp_bound_factory,
        timeout=config.timeout,
    )


def _rebind_python(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    del context
    if config.python_callable is None:
        raise LookupError(
            "persisted Python capability requires its caller-owned callable"
        )
    raw_tool = strip_amendment_overlay(tool)
    if len(raw_tool.endpoints) != 1:
        raise ValueError(
            "persisted Python capability must contain exactly one callable endpoint"
        )
    endpoint = raw_tool.endpoints[0]
    expected_module = endpoint.execution_metadata.get("callable_module")
    expected_name = endpoint.execution_metadata.get("callable_name")
    if (
        isinstance(expected_module, str)
        and config.python_callable.__module__ != expected_module
    ):
        raise ValueError("Python callable module does not match persisted capability")
    if (
        isinstance(expected_name, str)
        and config.python_callable.__qualname__ != expected_name
    ):
        raise ValueError("Python callable identity does not match persisted capability")

    reconstructed = tool_from_callable(
        config.python_callable,
        name=raw_tool.name,
        namespace=raw_tool.namespace,
        provider=raw_tool.provider,
        access_mode=raw_tool.access_mode,
        description=raw_tool.description,
        read_only=endpoint.read_only,
        destructive=endpoint.destructive,
    )
    if reconstructed.fingerprint != raw_tool.fingerprint:
        raise ValueError("Python callable schema does not match persisted capability")
    return PythonCallableInvoker(config.python_callable)


def _rebind_langchain(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    del context
    if config.langchain_tool is None:
        raise LookupError(
            "persisted LangChain capability requires its caller-owned tool"
        )
    from .integrations.langchain import LangChainToolInvoker, tool_from_langchain

    raw_tool = strip_amendment_overlay(tool)
    expected_module = raw_tool.metadata.get("foreign_tool_module")
    expected_class = raw_tool.metadata.get("foreign_tool_class")
    if (
        isinstance(expected_module, str)
        and type(config.langchain_tool).__module__ != expected_module
    ) or (
        isinstance(expected_class, str)
        and type(config.langchain_tool).__qualname__ != expected_class
    ):
        raise ValueError("LangChain tool identity does not match persisted capability")
    if len(raw_tool.endpoints) != 1:
        raise ValueError(
            "persisted LangChain capability must contain exactly one invoke endpoint"
        )
    endpoint = raw_tool.endpoints[0]
    reconstructed = tool_from_langchain(
        config.langchain_tool,
        name=raw_tool.name,
        namespace=raw_tool.namespace,
        provider=raw_tool.provider,
        access_mode=raw_tool.access_mode,
        read_only=endpoint.read_only,
        destructive=endpoint.destructive,
        remote=raw_tool.remote,
    )
    if reconstructed.fingerprint != raw_tool.fingerprint:
        raise ValueError("LangChain tool schema does not match persisted capability")
    return LangChainToolInvoker(config.langchain_tool)


def _rebind_llamaindex(
    tool: ToolSpec,
    config: TrustedBindingConfig,
    context: RebindingContext,
) -> BoundEndpointInvoker:
    del context
    if config.llamaindex_tool is None:
        raise LookupError(
            "persisted LlamaIndex capability requires its caller-owned tool"
        )
    from .integrations.llamaindex import LlamaIndexToolInvoker, tool_from_llamaindex

    raw_tool = strip_amendment_overlay(tool)
    expected_module = raw_tool.metadata.get("foreign_tool_module")
    expected_class = raw_tool.metadata.get("foreign_tool_class")
    if (
        isinstance(expected_module, str)
        and type(config.llamaindex_tool).__module__ != expected_module
    ) or (
        isinstance(expected_class, str)
        and type(config.llamaindex_tool).__qualname__ != expected_class
    ):
        raise ValueError("LlamaIndex tool identity does not match persisted capability")
    if len(raw_tool.endpoints) != 1:
        raise ValueError(
            "persisted LlamaIndex capability must contain exactly one invoke endpoint"
        )
    endpoint = raw_tool.endpoints[0]
    reconstructed = tool_from_llamaindex(
        config.llamaindex_tool,
        name=raw_tool.name,
        namespace=raw_tool.namespace,
        provider=raw_tool.provider,
        access_mode=raw_tool.access_mode,
        read_only=endpoint.read_only,
        destructive=endpoint.destructive,
        remote=raw_tool.remote,
    )
    if reconstructed.fingerprint != raw_tool.fingerprint:
        raise ValueError("LlamaIndex tool schema does not match persisted capability")
    return LlamaIndexToolInvoker(config.llamaindex_tool)


for _adapter, _strategy in {
    "openapi": _rebind_openapi,
    "graphql": _rebind_graphql,
    "odata": _rebind_odata,
    "openrpc": _rebind_openrpc,
    "optimade": _rebind_optimade,
    "http_json": _rebind_http_json,
    "mcp": _rebind_mcp,
    "python": _rebind_python,
    "langchain_tool": _rebind_langchain,
    "llamaindex_tool": _rebind_llamaindex,
}.items():
    register_rebinding_strategy(_adapter, _strategy)
