from __future__ import annotations

from typing import Any

from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec


def _properties(schema: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties", {})
    return props if isinstance(props, dict) else {}


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
    for item in raw_tools:
        input_schema = item.get("inputSchema") or {}
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

        output_schema = item.get("outputSchema") or {}
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
