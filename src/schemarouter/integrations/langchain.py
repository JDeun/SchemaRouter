from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence
from typing import Any

from ..models import ToolCall
from ..runtime import SchemaRouter
from ..validation import effective_input_schema


def _langchain_name(tool_key: str, endpoint_name: str) -> str:
    raw = f"schemarouter__{tool_key}__{endpoint_name}"
    return re.sub(r"[^A-Za-z0-9_-]+", "_", raw)


def _sync_await(coroutine_factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine_factory())
    raise RuntimeError(
        "synchronous LangChain tool invocation cannot run inside an active event loop; "
        "use ainvoke() instead"
    )


def to_langchain_tool(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    *,
    name: str | None = None,
    description: str | None = None,
):
    """Expose one registered SchemaRouter endpoint as a LangChain StructuredTool."""
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise ImportError(
            'LangChain integration requires: pip install "schemarouter[langchain]"'
        ) from exc

    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(endpoint_name)
    fields = [field.name for field in endpoint.output_fields]

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

    return StructuredTool(
        name=name or _langchain_name(tool_key, endpoint_name),
        description=(
            description
            or endpoint.description
            or tool.description
            or f"SchemaRouter endpoint {tool_key}.{endpoint_name}"
        ),
        args_schema=effective_input_schema(endpoint),
        func=invoke_endpoint,
        coroutine=ainvoke_endpoint,
    )


def to_langchain_tools(
    router: SchemaRouter,
    *,
    tool_keys: Sequence[str] | None = None,
) -> list[Any]:
    """Expose all selected registered endpoints as LangChain StructuredTool objects."""
    selected = set(tool_keys) if tool_keys is not None else None
    tools = []
    for tool in router.registry.tools():
        if selected is not None and tool.key not in selected:
            continue
        for endpoint in tool.endpoints:
            tools.append(
                to_langchain_tool(
                    router,
                    tool.key,
                    endpoint.name,
                )
            )
    return tools
