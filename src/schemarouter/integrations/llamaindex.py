from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict

from ..models import ToolCall
from ..runtime import SchemaRouter
from ..validation import effective_input_schema


def _llamaindex_name(tool_key: str, endpoint_name: str) -> str:
    raw = f"schemarouter__{tool_key}__{endpoint_name}"
    return re.sub(r"[^A-Za-z0-9_-]+", "_", raw)


def _rewrite_openapi_component_refs(value: Any) -> Any:
    if isinstance(value, dict):
        rewritten = {
            key: _rewrite_openapi_component_refs(item)
            for key, item in value.items()
        }
        ref = rewritten.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            rewritten["$ref"] = "#/$defs/" + ref.removeprefix("#/components/schemas/")
        return rewritten
    if isinstance(value, list):
        return [_rewrite_openapi_component_refs(item) for item in value]
    return value


def _llamaindex_schema_model(
    schema: dict[str, Any],
    *,
    model_name: str,
) -> type[BaseModel]:
    """Build a Pydantic schema carrier for LlamaIndex tool metadata.

    LlamaIndex requires fn_schema to be a BaseModel class, while SchemaRouter
    stores JSON Schema as the source of truth. The generated model exposes the
    SchemaRouter schema to LlamaIndex; execution validation still happens inside
    SchemaRouter before the bound tool is invoked.
    """
    exported = deepcopy(schema)
    components = exported.pop("components", None)
    if isinstance(components, dict):
        component_schemas = components.get("schemas")
        if isinstance(component_schemas, dict):
            existing_defs = exported.get("$defs")
            defs = dict(existing_defs) if isinstance(existing_defs, dict) else {}
            for key, value in component_schemas.items():
                defs.setdefault(key, value)
            if defs:
                exported["$defs"] = defs

    exported = _rewrite_openapi_component_refs(exported)
    properties = exported.get("properties")
    property_names = list(properties) if isinstance(properties, dict) else []
    required_value = exported.get("required")
    required = set(required_value) if isinstance(required_value, list) else set()

    fields: dict[str, tuple[Any, Any]] = {
        field_name: (Any, ... if field_name in required else None)
        for field_name in property_names
    }
    extra_mode: Literal["forbid", "allow"] = (
        "forbid" if exported.get("additionalProperties") is False else "allow"
    )

    class SchemaCarrier(BaseModel):
        model_config = ConfigDict(extra=extra_mode)

        @classmethod
        def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
            del cls, args, kwargs
            return deepcopy(exported)

    safe_name = re.sub(r"[^A-Za-z0-9_]+", "_", model_name) or "SchemaRouterArgs"
    annotations = {field_name: annotation for field_name, (annotation, _) in fields.items()}
    namespace: dict[str, Any] = {
        "__module__": __name__,
        "__annotations__": annotations,
    }
    for field_name, (_, default) in fields.items():
        if default is not ...:
            namespace[field_name] = default

    return cast(type[BaseModel], type(safe_name, (SchemaCarrier,), namespace))


def _sync_await(coroutine_factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine_factory())
    raise RuntimeError(
        "synchronous LlamaIndex tool invocation cannot run inside an active event loop; "
        "use the async tool path instead"
    )


def to_llamaindex_tool(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    *,
    name: str | None = None,
    description: str | None = None,
):
    """Expose one registered endpoint as a LlamaIndex FunctionTool."""
    try:
        from llama_index.core.tools import FunctionTool
    except ImportError as exc:
        raise ImportError(
            'LlamaIndex integration requires: pip install "schemarouter[llamaindex]"'
        ) from exc

    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(endpoint_name)
    fields = [field.name for field in endpoint.output_fields]
    schema = effective_input_schema(endpoint)
    tool_name = name or _llamaindex_name(tool_key, endpoint_name)
    schema_model = _llamaindex_schema_model(
        schema,
        model_name=f"{tool_name}_Args",
    )

    async def ainvoke_endpoint(**arguments: Any) -> Any:
        call = ToolCall(
            tool=tool_key,
            endpoint=endpoint_name,
            arguments=arguments,
            fields=fields,
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        result = await router.executor.execute_call(call)
        return result.data

    def invoke_endpoint(**arguments: Any) -> Any:
        return _sync_await(lambda: ainvoke_endpoint(**arguments))

    return FunctionTool.from_defaults(
        fn=invoke_endpoint,
        async_fn=ainvoke_endpoint,
        name=tool_name,
        description=(
            description
            or endpoint.description
            or tool.description
            or f"SchemaRouter endpoint {tool_key}.{endpoint_name}"
        ),
        fn_schema=schema_model,
    )


def to_llamaindex_tools(
    router: SchemaRouter,
    *,
    tool_keys: Sequence[str] | None = None,
) -> list[Any]:
    """Expose all selected registered endpoints as LlamaIndex FunctionTool objects."""
    selected = set(tool_keys) if tool_keys is not None else None
    tools = []
    for tool in router.registry.tools():
        if selected is not None and tool.key not in selected:
            continue
        for endpoint in tool.endpoints:
            tools.append(to_llamaindex_tool(router, tool.key, endpoint.name))
    return tools
