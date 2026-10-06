from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from .._http_headers import validate_trusted_headers
from ..errors import InvocationUnavailableError, SchemaSourceError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec
from ..network_policy import TRUSTED_INTERNAL_NETWORK_POLICY, NetworkPolicy
from ..schema_complexity import ensure_ref_hop_budget, validate_schema_complexity

_PROTECTED_MCP_HEADERS = {
    "accept",
    "connection",
    "content-length",
    "content-type",
    "host",
    "transfer-encoding",
}


def _schema_unit(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return None
    for key in ("x-ucum-unit", "x-unit", "unit"):
        value = schema.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "inapplicable":
            return value.strip()
    return None


class MCPClientFactory(Protocol):
    """Trusted factory for an authenticated MCP client lifecycle."""

    def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
    ) -> AbstractAsyncContextManager[Any]: ...


class MCPBoundClientFactory(Protocol):
    """Trusted transport-neutral MCP client lifecycle already bound to its transport."""

    def __call__(
        self,
        *,
        timeout: float = 20.0,
    ) -> AbstractAsyncContextManager[Any]: ...


def _validate_stdio_text(value: str, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise ValueError(f"{label} must not contain NUL or newline characters")
    return value


@dataclass(frozen=True)
class MCPStdioConfig:
    """Trusted local subprocess configuration for an MCP stdio server."""

    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] | None = None
    cwd: str | None = None
    allowed_commands: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        command = _validate_stdio_text(self.command, label="MCP stdio command")
        args = tuple(
            _validate_stdio_text(value, label="MCP stdio argument")
            for value in self.args
        )
        object.__setattr__(self, "command", command)
        object.__setattr__(self, "args", args)

        if self.cwd is not None:
            object.__setattr__(
                self,
                "cwd",
                _validate_stdio_text(self.cwd, label="MCP stdio cwd"),
            )

        if self.env is not None:
            clean_env: dict[str, str] = {}
            for key, value in self.env.items():
                clean_key = _validate_stdio_text(
                    key,
                    label="MCP stdio environment key",
                )
                clean_value = _validate_stdio_text(
                    value,
                    label=f"MCP stdio environment value for {clean_key!r}",
                )
                clean_env[clean_key] = clean_value
            object.__setattr__(self, "env", clean_env)

        allowed = tuple(
            _validate_stdio_text(value, label="MCP stdio allowed command")
            for value in self.allowed_commands
        )
        object.__setattr__(self, "allowed_commands", allowed)
        if allowed and command not in allowed:
            raise ValueError(
                f"MCP stdio command {command!r} is not in the trusted allowlist"
            )

    @property
    def transport_fingerprint(self) -> str:
        payload = {
            "transport": "stdio",
            "command": self.command,
            "args": list(self.args),
            "cwd": self.cwd,
            "env_keys": sorted((self.env or {}).keys()),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class MCPStdioClientFactory:
    """Build an official MCP v2 client over a trusted local stdio subprocess."""

    def __init__(self, config: MCPStdioConfig) -> None:
        self.config = config

    @asynccontextmanager
    async def __call__(self, *, timeout: float = 20.0):
        try:
            from mcp import Client, StdioServerParameters
        except ImportError as exc:
            raise SchemaSourceError(
                'MCP support requires the optional dependency: pip install "schemarouter[mcp]"'
            ) from exc

        params = StdioServerParameters(
            command=self.config.command,
            args=list(self.config.args),
            env=dict(self.config.env) if self.config.env is not None else None,
            cwd=Path(self.config.cwd) if self.config.cwd is not None else None,
        )
        try:
            from anyio import fail_after

            with fail_after(timeout):
                async with Client(
                    params,
                    read_timeout_seconds=timeout,
                ) as client:
                    yield client
        except TimeoutError as exc:
            raise InvocationUnavailableError(
                "MCP stdio lifecycle exceeded the configured timeout"
            ) from exc


class _BoundHTTPMCPClientFactory:
    def __init__(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        client_factory: MCPClientFactory,
        network_policy: NetworkPolicy = TRUSTED_INTERNAL_NETWORK_POLICY,
    ) -> None:
        self.url = url
        self.headers = headers
        self.client_factory = client_factory
        self.network_policy = network_policy

    def __call__(
        self,
        *,
        timeout: float = 20.0,
    ) -> AbstractAsyncContextManager[Any]:
        return self._open(timeout=timeout)

    @asynccontextmanager
    async def _open(self, *, timeout: float):
        await self.network_policy.authorize(self.url)
        async with self.client_factory(
            self.url,
            headers=self.headers,
            timeout=timeout,
        ) as client:
            yield client


def _validated_trusted_headers(
    headers: Mapping[str, str] | None,
) -> dict[str, str] | None:
    if headers is None:
        return None
    result = validate_trusted_headers(
        headers,
        label="MCP trusted_headers",
    )
    for name in result:
        normalized = name.casefold()
        if normalized in _PROTECTED_MCP_HEADERS or normalized.startswith("mcp-"):
            raise ValueError(
                f"MCP protocol header {name!r} is controlled by the SDK and cannot be overridden"
            )
    return result


class DefaultMCPClientFactory:
    """Build the official Streamable HTTP transport with caller-owned HTTP auth."""

    @asynccontextmanager
    async def __call__(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
    ):
        try:
            import httpx2
            from mcp import Client
            from mcp.client.streamable_http import streamable_http_client
        except ImportError as exc:
            raise SchemaSourceError(
                'MCP support requires the optional dependency: pip install "schemarouter[mcp]"'
            ) from exc

        trusted_headers = _validated_trusted_headers(headers)
        async with httpx2.AsyncClient(
            headers=trusted_headers,
            timeout=httpx2.Timeout(timeout, read=timeout),
        ) as http_client:
            transport = streamable_http_client(url, http_client=http_client)
            async with Client(transport) as client:
                yield client


_DEFAULT_CLIENT_FACTORY = DefaultMCPClientFactory()


def _validate_mcp_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("MCP URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError(
            "MCP URL must not contain credentials; use trusted transport authentication"
        )
    if parsed.query or parsed.fragment:
        raise ValueError(
            "MCP URL must not contain query or fragment; use trusted transport authentication "
            "or a stable endpoint path"
        )


def _properties(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties", {})
    return props if isinstance(props, dict) else {}


_NESTED_OUTPUT_MAX_DEPTH = 8


def _local_ref_target(document: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    node: Any = document
    try:
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[part]
    except (KeyError, TypeError):
        return None
    return node if isinstance(node, dict) else None


def _resolve_output_schema(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    current = schema
    seen: set[str] = set()
    hops = 0
    while isinstance(current, dict):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            return current
        hops += 1
        ensure_ref_hop_budget(hops, source="MCP schema")
        seen.add(ref)
        target = _local_ref_target(document, ref)
        if target is None:
            return current
        merged = dict(target)
        merged.update({key: value for key, value in current.items() if key != "$ref"})
        current = merged
    return schema


def _schema_branches(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> list[dict[str, Any]]:
    branches: list[dict[str, Any]] = []
    for keyword in ("allOf", "oneOf", "anyOf"):
        raw = schema.get(keyword)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict):
                branches.append(_resolve_output_schema(document, item))
    return branches


def _merged_properties(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    resolved = _resolve_output_schema(document, schema)
    property_sets = [_properties(resolved)]
    property_sets.extend(
        _properties(branch)
        for branch in _schema_branches(document, resolved)
    )

    merged: dict[str, dict[str, Any]] = {}
    for properties in property_sets:
        for name, spec in properties.items():
            if not isinstance(spec, dict):
                continue
            existing = merged.get(name)
            if existing is None or existing == spec:
                merged[name] = spec
                continue
            options = (
                list(existing["anyOf"])
                if set(existing) == {"anyOf"}
                and isinstance(existing.get("anyOf"), list)
                else [existing]
            )
            if spec not in options:
                options.append(spec)
            merged[name] = {"anyOf": options}
    return merged


def _mcp_field_name_from_path(path: tuple[str, ...]) -> str:
    parts: list[str] = []
    for segment in path:
        if segment == "*":
            if not parts:
                raise ValueError("array wildcard cannot be the first named field segment")
            parts[-1] = parts[-1] + "[]"
            continue
        parts.append(segment)
    return ".".join(parts)


def _mcp_schema_is_array(schema: dict[str, Any]) -> bool:
    raw_type = schema.get("type")
    return raw_type == "array" or (
        isinstance(raw_type, list) and "array" in raw_type
    )


def _nested_output_fields(output_schema: dict[str, Any]) -> list[FieldSpec]:
    discovered: list[FieldSpec] = []
    seen_names = set(_merged_properties(output_schema, output_schema))

    def visit(
        schema: dict[str, Any],
        *,
        prefix: tuple[str, ...],
        depth: int,
        ancestors: frozenset[str],
    ) -> None:
        if depth >= _NESTED_OUTPUT_MAX_DEPTH:
            return
        resolved = _resolve_output_schema(output_schema, schema)
        signature = json.dumps(
            resolved,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        if signature in ancestors:
            return
        next_ancestors = ancestors | {signature}

        if _mcp_schema_is_array(resolved):
            items = resolved.get("items")
            if isinstance(items, dict):
                visit(
                    items,
                    prefix=(*prefix, "*") if prefix else prefix,
                    depth=depth + 1,
                    ancestors=next_ancestors,
                )
            return

        for name, spec in _merged_properties(output_schema, resolved).items():
            path = (*prefix, name)
            field_name = _mcp_field_name_from_path(path)
            if field_name not in seen_names:
                seen_names.add(field_name)
                resolved_spec = _resolve_output_schema(output_schema, spec)
                discovered.append(
                    FieldSpec(
                        name=field_name,
                        description=str(resolved_spec.get("description") or ""),
                        json_schema=resolved_spec,
                        path=list(path),
                        result_path=(
                            list(path)
                            if "*" in path
                            else [field_name]
                        ),
                        unit=_schema_unit(resolved_spec),
                        identifier=(
                            name in {"id", "uuid", "key"}
                            or name.endswith("_id")
                        ),
                        aliases=list(
                            dict.fromkeys(
                                [name, name.replace("_", " ")]
                            )
                        ),
                        source_type="mcp",
                    )
                )

            visit(
                spec,
                prefix=path,
                depth=depth + 1,
                ancestors=next_ancestors,
            )

    visit(output_schema, prefix=(), depth=0, ancestors=frozenset())
    return discovered


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_none=True)
    raise TypeError(f"cannot convert MCP value {type(value)!r} to dict")


def tool_from_mcp(
    server_name: str,
    tools_list_result: dict[str, Any] | list[dict[str, Any]],
    *,
    namespace: str | None = None,
) -> ToolSpec:
    """Convert an MCP tools/list result into a single server-scoped ToolSpec.

    Remote annotations are preserved as untrusted metadata only; they do not grant permissions.
    """
    raw_tools = (
        tools_list_result.get("tools", [])
        if isinstance(tools_list_result, dict)
        else tools_list_result
    )
    endpoints: list[EndpointSpec] = []
    for raw_item in raw_tools:
        item = _as_dict(raw_item)
        input_schema = item.get("inputSchema") or item.get("input_schema") or {}
        if isinstance(input_schema, dict):
            validate_schema_complexity(
                input_schema,
                source=f"MCP tool {item.get('name')!r} input schema",
            )
        required = (
            set(input_schema.get("required", []))
            if isinstance(input_schema, dict)
            else set()
        )
        parameters = [
            ParameterSpec(
                name=name,
                description=spec.get("description", "") if isinstance(spec, dict) else "",
                required=name in required,
                location="argument",
                json_schema=spec if isinstance(spec, dict) else {},
            )
            for name, spec in _properties(input_schema).items()
        ]

        output_schema = item.get("outputSchema") or item.get("output_schema") or {}
        if isinstance(output_schema, dict):
            validate_schema_complexity(
                output_schema,
                source=f"MCP tool {item.get('name')!r} output schema",
            )
        output_required = (
            set(output_schema.get("required", []))
            if isinstance(output_schema, dict)
            else set()
        )
        fields = [
            FieldSpec(
                name=name,
                description=spec.get("description", "") if isinstance(spec, dict) else "",
                json_schema=spec if isinstance(spec, dict) else {},
                unit=_schema_unit(spec),
                identifier=name in {"id", "uuid", "key"} or name.endswith("_id"),
                aliases=[name.replace("_", " ")],
                source_type="mcp",
            )
            for name, spec in _merged_properties(output_schema, output_schema).items()
        ]
        fields.extend(_nested_output_fields(output_schema))
        metadata = {
            "title": item.get("title"),
            "annotations": item.get("annotations"),
            "output_required": sorted(output_required),
            "remote_name": item.get("name"),
        }
        endpoints.append(
            EndpointSpec(
                name=item["name"],
                description=item.get("description", ""),
                parameters=parameters,
                output_fields=fields,
                input_schema=input_schema if isinstance(input_schema, dict) else {},
                output_schema=output_schema if isinstance(output_schema, dict) else {},
                metadata=metadata,
            )
        )

    return ToolSpec(
        name=server_name,
        namespace=namespace,
        description=f"MCP server: {server_name}",
        endpoints=endpoints,
        execution_metadata={"adapter": "mcp"},
        metadata={"adapter": "mcp", "remote_metadata_untrusted": True},
    )


async def inspect_mcp_client_factory(
    factory: MCPBoundClientFactory,
    *,
    server_name: str | None = None,
    namespace: str | None = None,
    timeout: float = 20.0,
    transport: str = "custom",
    transport_fingerprint: str | None = None,
) -> ToolSpec:
    """Inspect an MCP server through an already-bound trusted transport factory."""

    raw_tools: list[dict[str, Any]] = []
    try:
        async with factory(timeout=timeout) as client:
            cursor: str | None = None
            while True:
                page = await client.list_tools(cursor=cursor)
                raw_tools.extend(_as_dict(tool) for tool in page.tools)
                cursor = page.next_cursor
                if cursor is None:
                    break

            info = getattr(client, "server_info", None)
            discovered_name = getattr(info, "name", None)
            protocol_version = getattr(client, "protocol_version", None)
    except SchemaSourceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise SchemaSourceError(
            f"failed to inspect MCP server over {transport!r} transport"
        ) from exc

    name = server_name or discovered_name or "mcp_server"
    tool = tool_from_mcp(name, raw_tools, namespace=namespace)
    tool.remote = True
    tool.execution_metadata.update(
        {
            "transport": transport,
            "protocol_version": protocol_version,
            "transport_fingerprint": transport_fingerprint,
        }
    )
    tool.metadata.update(
        {
            "transport": transport,
            "protocol_version": protocol_version,
            "transport_fingerprint": transport_fingerprint,
            "remote_metadata_untrusted": True,
        }
    )
    return tool


async def inspect_mcp_stdio(
    config: MCPStdioConfig,
    *,
    server_name: str | None = None,
    namespace: str | None = None,
    timeout: float = 20.0,
) -> ToolSpec:
    """Spawn a trusted local MCP stdio server and import all advertised tools."""

    return await inspect_mcp_client_factory(
        MCPStdioClientFactory(config),
        server_name=server_name,
        namespace=namespace,
        timeout=timeout,
        transport="stdio",
        transport_fingerprint=config.transport_fingerprint,
    )


class MCPBoundInvoker:
    """Transport-neutral trusted MCP runtime binding."""

    def __init__(
        self,
        factory: MCPBoundClientFactory,
        *,
        timeout: float = 20.0,
    ) -> None:
        self.factory = factory
        self.timeout = timeout

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        async def invoke_bound() -> Any:
            async with self.factory(timeout=self.timeout) as client:
                return await client.call_tool(endpoint, arguments)

        try:
            result = await asyncio.wait_for(
                invoke_bound(),
                timeout=self.timeout,
            )
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise InvocationUnavailableError(
                "MCP access path is temporarily unavailable"
            ) from exc

        if getattr(result, "is_error", False):
            raise RuntimeError(f"MCP tool {endpoint!r} returned an error")

        structured = getattr(result, "structured_content", None)
        if structured is not None:
            return structured

        content = getattr(result, "content", None)
        if content is None:
            return None
        return [
            block.model_dump(mode="json", by_alias=True, exclude_none=True)
            if hasattr(block, "model_dump")
            else str(block)
            for block in content
        ]


async def inspect_mcp_url(
    url: str,
    *,
    server_name: str | None = None,
    namespace: str | None = None,
    trusted_headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
    client_factory: MCPClientFactory | None = None,
    network_policy: NetworkPolicy = TRUSTED_INTERNAL_NETWORK_POLICY,
) -> ToolSpec:
    """Connect to a Streamable HTTP MCP URL and import all advertised tools."""
    _validate_mcp_url(url)
    factory = client_factory or _DEFAULT_CLIENT_FACTORY
    headers = _validated_trusted_headers(trusted_headers)
    bound_factory = _BoundHTTPMCPClientFactory(
        url,
        headers=headers,
        client_factory=factory,
        network_policy=network_policy,
    )
    transport_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "transport": "streamable_http",
                "url": url,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    tool = await inspect_mcp_client_factory(
        bound_factory,
        server_name=server_name,
        namespace=namespace,
        timeout=timeout,
        transport="streamable_http",
        transport_fingerprint=transport_fingerprint,
    )
    custom_client_factory_required = client_factory is not None
    tool.execution_metadata.update(
        {
            "source_url": url,
            "authenticated_transport": bool(headers),
            "custom_client_factory_required": custom_client_factory_required,
        }
    )
    tool.metadata.update(
        {
            "source_url": url,
            "authenticated_transport": bool(headers),
            "custom_client_factory_required": custom_client_factory_required,
        }
    )
    return tool


class MCPRemoteInvoker(MCPBoundInvoker):
    """Backward-compatible Streamable HTTP MCP runtime binding."""

    def __init__(
        self,
        url: str,
        *,
        trusted_headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
        client_factory: MCPClientFactory | None = None,
        network_policy: NetworkPolicy = TRUSTED_INTERNAL_NETWORK_POLICY,
    ) -> None:
        _validate_mcp_url(url)
        headers = _validated_trusted_headers(trusted_headers)
        factory = client_factory or _DEFAULT_CLIENT_FACTORY
        super().__init__(
            _BoundHTTPMCPClientFactory(
                url,
                headers=headers,
                client_factory=factory,
                network_policy=network_policy,
            ),
            timeout=timeout,
        )
        self.url = url
        self._trusted_headers = headers
        self.client_factory = factory
