from __future__ import annotations

from typing import Any

from ..errors import SchemaSourceError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec


def _properties(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties", {})
    return props if isinstance(props, dict) else {}


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
                identifier=name in {"id", "uuid", "key"} or name.endswith("_id"),
                aliases=[name.replace("_", " ")],
            )
            for name, spec in _properties(output_schema).items()
        ]
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
                metadata=metadata,
            )
        )

    return ToolSpec(
        name=server_name,
        namespace=namespace,
        description=f"MCP server: {server_name}",
        endpoints=endpoints,
        metadata={"adapter": "mcp", "remote_metadata_untrusted": True},
    )


async def inspect_mcp_url(
    url: str,
    *,
    server_name: str | None = None,
    namespace: str | None = None,
) -> ToolSpec:
    """Connect to a Streamable HTTP MCP URL and import all advertised tools."""
    try:
        from mcp import Client
    except ImportError as exc:
        raise SchemaSourceError(
            'MCP support requires the optional dependency: pip install "schemarouter[mcp]"'
        ) from exc

    raw_tools: list[dict[str, Any]] = []
    try:
        async with Client(url) as client:
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
    except Exception as exc:  # noqa: BLE001
        raise SchemaSourceError(f"failed to inspect MCP server at {url!r}") from exc

    name = server_name or discovered_name or "mcp_server"
    tool = tool_from_mcp(name, raw_tools, namespace=namespace)
    tool.metadata.update(
        {
            "source_url": url,
            "protocol_version": protocol_version,
        }
    )
    return tool


class MCPRemoteInvoker:
    """Trusted runtime adapter for a remote MCP server.

    A fresh client lifecycle is used per invocation in v0.1. Connection pooling belongs in a
    later transport layer so the core executor remains stateless and easy to reason about.
    """

    def __init__(self, url: str) -> None:
        self.url = url

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        try:
            from mcp import Client
        except ImportError as exc:
            raise SchemaSourceError(
                'MCP execution requires: pip install "schemarouter[mcp]"'
            ) from exc

        async with Client(self.url) as client:
            result = await client.call_tool(endpoint, arguments)
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
