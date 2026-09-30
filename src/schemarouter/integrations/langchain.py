from __future__ import annotations

import asyncio
import dataclasses
import inspect
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolCall, ToolSpec
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


def _model_json_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return deepcopy(value)
    model_json_schema = getattr(value, "model_json_schema", None)
    if callable(model_json_schema):
        schema = model_json_schema()
        return deepcopy(schema) if isinstance(schema, dict) else {}
    return {}


def _langchain_input_schema(tool: Any) -> dict[str, Any]:
    getter = getattr(tool, "get_input_jsonschema", None)
    if callable(getter):
        try:
            schema = getter()
        except Exception:  # noqa: BLE001
            schema = None
        if isinstance(schema, dict):
            return deepcopy(schema)

    args_schema = getattr(tool, "args_schema", None)
    schema = _model_json_schema(args_schema)
    if schema:
        return schema

    getter = getattr(tool, "get_input_schema", None)
    if callable(getter):
        try:
            model = getter()
        except Exception:  # noqa: BLE001
            model = None
        schema = _model_json_schema(model)
        if schema:
            return schema

    args = getattr(tool, "args", None)
    if isinstance(args, dict):
        return {
            "type": "object",
            "properties": deepcopy(args),
        }
    return {}


def _langchain_output_schema(tool: Any) -> dict[str, Any]:
    getter = getattr(tool, "get_output_jsonschema", None)
    if callable(getter):
        try:
            schema = getter()
        except Exception:  # noqa: BLE001
            schema = None
        if isinstance(schema, dict):
            return deepcopy(schema)

    getter = getattr(tool, "get_output_schema", None)
    if callable(getter):
        try:
            model = getter()
        except Exception:  # noqa: BLE001
            model = None
        schema = _model_json_schema(model)
        if schema:
            return schema
    return {}


def _schema_unit(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return None
    for key in ("x-ucum-unit", "x-unit", "unit"):
        value = schema.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "inapplicable":
            return value.strip()
    return None


def _schema_properties(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {
        str(name): value
        for name, value in properties.items()
        if isinstance(value, dict)
    }


def _parameters_from_schema(schema: dict[str, Any]) -> list[ParameterSpec]:
    required_value = schema.get("required")
    required = set(required_value) if isinstance(required_value, list) else set()
    return [
        ParameterSpec(
            name=name,
            description=str(spec.get("description") or ""),
            required=name in required,
            location="argument",
            json_schema=spec,
        )
        for name, spec in _schema_properties(schema).items()
    ]


def _fields_from_schema(schema: dict[str, Any]) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    seen: set[str] = set()

    def visit(
        value: dict[str, Any],
        *,
        prefix: tuple[str, ...],
        depth: int,
    ) -> None:
        if depth >= 8:
            return
        raw_type = value.get("type")
        if raw_type == "array" or (
            isinstance(raw_type, list) and "array" in raw_type
        ):
            return
        properties = _schema_properties(value)
        for name, child in properties.items():
            path = (*prefix, name)
            field_name = ".".join(path)
            if field_name not in seen:
                seen.add(field_name)
                fields.append(
                    FieldSpec(
                        name=field_name,
                        description=str(child.get("description") or ""),
                        json_schema=child,
                        aliases=[name.replace("_", " ")],
                        path=list(path) if prefix else [],
                        result_path=[field_name] if prefix else [],
                        unit=_schema_unit(child),
                        identifier=(
                            name in {"id", "uuid", "key"}
                            or name.endswith("_id")
                        ),
                        source_type="langchain",
                    )
                )
            visit(child, prefix=path, depth=depth + 1)

    visit(schema, prefix=(), depth=0)
    return fields


def tool_from_langchain(
    tool: Any,
    *,
    name: str | None = None,
    namespace: str | None = None,
    provider: str | None = None,
    access_mode: str | None = None,
    read_only: bool | None = None,
    destructive: bool | None = None,
    remote: bool = True,
) -> ToolSpec:
    """Compile a LangChain BaseTool-like object into SchemaRouter's canonical contract.

    Only declared schemas and explicit local classification arguments are trusted. Tool
    descriptions or remote metadata never grant read/write authority.
    """

    tool_name = name or getattr(tool, "name", None)
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise TypeError("LangChain tool must expose a non-empty name or receive name=")
    description = getattr(tool, "description", "")
    if not isinstance(description, str):
        description = str(description)

    input_schema = _langchain_input_schema(tool)
    output_schema = _langchain_output_schema(tool)
    endpoint = EndpointSpec(
        name="invoke",
        description=description,
        parameters=_parameters_from_schema(input_schema),
        input_schema=input_schema,
        output_fields=_fields_from_schema(output_schema),
        output_schema=output_schema,
        read_only=read_only,
        destructive=destructive,
        execution_metadata={
            "framework": "langchain",
            "foreign_tool_name": tool_name,
        },
        metadata={
            "framework": "langchain",
            "foreign_tool_class": type(tool).__qualname__,
            "foreign_tool_module": type(tool).__module__,
        },
    )
    return ToolSpec(
        name=tool_name.strip(),
        namespace=namespace,
        description=description,
        provider=provider,
        access_mode=access_mode or "langchain",
        remote=remote,
        endpoints=[endpoint],
        execution_metadata={"adapter": "langchain_tool"},
        metadata={
            "adapter": "langchain_tool",
            "foreign_tool_class": type(tool).__qualname__,
            "foreign_tool_module": type(tool).__module__,
        },
    )


class LangChainToolInvoker:
    """Trusted binding for one imported LangChain tool object."""

    def __init__(self, tool: Any) -> None:
        self.tool = tool

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        if endpoint != "invoke":
            raise RuntimeError(f"unknown LangChain tool endpoint: {endpoint!r}")

        ainvoke = getattr(self.tool, "ainvoke", None)
        if callable(ainvoke):
            value = ainvoke(dict(arguments))
            if inspect.isawaitable(value):
                value = await value
        else:
            invoke = getattr(self.tool, "invoke", None)
            if not callable(invoke):
                raise TypeError("imported LangChain tool has neither ainvoke() nor invoke()")
            value = invoke(dict(arguments))
            if inspect.isawaitable(value):
                value = await value

        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=True, exclude_none=True)
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return dataclasses.asdict(value)
        return value


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
            tool_fingerprint=tool.fingerprint,
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
