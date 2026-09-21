from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from typing import Any

from ..models import ToolCall
from ..runtime import SchemaRouter
from ..validation import effective_input_schema


def _llamaindex_name(tool_key: str, endpoint_name: str) -> str:
    raw = f"schemarouter__{tool_key}__{endpoint_name}"
    return re.sub(r"[^A-Za-z0-9_-]+", "_", raw)


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

    async def ainvoke_endpoint(**arguments: Any) -> Any:
        call = ToolCall(
            tool=tool_key,
            endpoint=endpoint_name,
            arguments=arguments,
            fields=fields,
            schema_fingerprint=endpoint.fingerprint,
        )
        result = await router.executor.execute_call(call)
        return result.data

    def invoke_endpoint(**arguments: Any) -> Any:
        return _sync_await(lambda: ainvoke_endpoint(**arguments))

    return FunctionTool.from_defaults(
        fn=invoke_endpoint,
        async_fn=ainvoke_endpoint,
        name=name or _llamaindex_name(tool_key, endpoint_name),
        description=(
            description
            or endpoint.description
            or tool.description
            or f"SchemaRouter endpoint {tool_key}.{endpoint_name}"
        ),
        fn_schema=schema,
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
