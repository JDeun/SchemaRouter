from __future__ import annotations

import asyncio
import dataclasses
import inspect
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any

from ..errors import PolicyViolationError
from ..models import (
    EndpointSpec,
    ExecutionPlan,
    FieldSpec,
    ParameterSpec,
    ToolCall,
    ToolSpec,
)
from ..runs import RunConfig
from ..runtime import SchemaRouter
from ..validation import effective_input_schema
from ._export_contract import (
    _authorized_endpoint_view,
    _capture_exported_endpoint_contract,
    _coerce_export_run_config,
    _resolve_live_exported_endpoint,
)


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


def _langchain_resolve_local_ref(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    current = schema
    seen: set[str] = set()
    while isinstance(current, dict):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            return current
        seen.add(ref)
        node: Any = document
        try:
            for raw in ref[2:].split("/"):
                part = raw.replace("~1", "/").replace("~0", "~")
                node = node[part]
        except (KeyError, TypeError):
            return current
        if not isinstance(node, dict):
            return current
        merged = dict(node)
        merged.update({key: value for key, value in current.items() if key != "$ref"})
        current = merged
    return schema


def _langchain_schema_is_array(schema: dict[str, Any]) -> bool:
    raw_type = schema.get("type")
    return raw_type == "array" or (
        isinstance(raw_type, list) and "array" in raw_type
    )


def _langchain_field_name(path: tuple[str, ...]) -> str:
    parts: list[str] = []
    for segment in path:
        if segment == "*":
            if not parts:
                raise ValueError("array wildcard cannot be the first named field segment")
            parts[-1] = parts[-1] + "[]"
            continue
        parts.append(segment)
    return ".".join(parts)


def _langchain_record_schema(schema: dict[str, Any]) -> dict[str, Any]:
    root = _langchain_resolve_local_ref(schema, schema)
    if _langchain_schema_is_array(root):
        items = root.get("items")
        if isinstance(items, dict):
            return _langchain_resolve_local_ref(schema, items)
    return root


def _fields_from_schema(schema: dict[str, Any]) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    seen: set[str] = set()
    root = _langchain_resolve_local_ref(schema, schema)

    def visit(
        value: dict[str, Any],
        *,
        prefix: tuple[str, ...],
        depth: int,
        ancestors: frozenset[str],
    ) -> None:
        if depth >= 8:
            return
        resolved = _langchain_resolve_local_ref(schema, value)
        signature = repr(
            sorted(
                (key, repr(item))
                for key, item in resolved.items()
            )
        )
        if signature in ancestors:
            return
        next_ancestors = ancestors | {signature}

        if _langchain_schema_is_array(resolved):
            items = resolved.get("items")
            if isinstance(items, dict):
                visit(
                    items,
                    prefix=(*prefix, "*") if prefix else prefix,
                    depth=depth + 1,
                    ancestors=next_ancestors,
                )
            return

        properties = _schema_properties(resolved)
        for name, child in properties.items():
            resolved_child = _langchain_resolve_local_ref(schema, child)
            path = (*prefix, name)
            field_name = _langchain_field_name(path)
            if field_name not in seen:
                seen.add(field_name)
                fields.append(
                    FieldSpec(
                        name=field_name,
                        description=str(resolved_child.get("description") or ""),
                        json_schema=resolved_child,
                        aliases=[name.replace("_", " ")],
                        path=list(path) if prefix else [],
                        result_path=(
                            list(path)
                            if "*" in path
                            else ([field_name] if prefix else [])
                        ),
                        unit=_schema_unit(resolved_child),
                        identifier=(
                            name in {"id", "uuid", "key"}
                            or name.endswith("_id")
                        ),
                        source_type="langchain",
                    )
                )
            visit(
                child,
                prefix=path,
                depth=depth + 1,
                ancestors=next_ancestors,
            )

    visit(root, prefix=(), depth=0, ancestors=frozenset())
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

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json", by_alias=True, exclude_none=True)
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
    run_config: RunConfig | dict[str, Any] | None = None,
):
    """Expose one principal-aware SchemaRouter endpoint as a LangChain StructuredTool."""
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise ImportError(
            'LangChain integration requires: pip install "schemarouter[langchain]"'
        ) from exc

    resolved_config = _coerce_export_run_config(run_config)
    tool, endpoint, visible_endpoint = _authorized_endpoint_view(
        router,
        tool_key,
        endpoint_name,
        resolved_config,
    )
    export_contract = _capture_exported_endpoint_contract(
        tool,
        endpoint,
        visible_endpoint,
    )

    async def ainvoke_endpoint(**arguments: Any) -> Any:
        live_tool, live_endpoint, live_visible_endpoint = (
            _resolve_live_exported_endpoint(
                router,
                tool_key,
                endpoint_name,
                resolved_config,
                export_contract,
            )
        )
        call = ToolCall(
            tool=tool_key,
            endpoint=endpoint_name,
            arguments=arguments,
            fields=[field.name for field in live_visible_endpoint.output_fields],
            schema_fingerprint=live_endpoint.fingerprint,
            tool_fingerprint=live_tool.fingerprint,
        )
        plan = ExecutionPlan(
            query=f"LangChain invocation of {tool_key}.{endpoint_name}",
            registry_version=router.registry.version,
            calls=[call],
        )
        result = await router.execute(plan, config=resolved_config)
        return result[0].data

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
        args_schema=effective_input_schema(visible_endpoint),
        func=invoke_endpoint,
        coroutine=ainvoke_endpoint,
    )


def to_langchain_tools(
    router: SchemaRouter,
    *,
    tool_keys: Sequence[str] | None = None,
    run_config: RunConfig | dict[str, Any] | None = None,
) -> list[Any]:
    """Expose principal-visible endpoints as LangChain StructuredTool objects."""
    resolved_config = _coerce_export_run_config(run_config)
    selected = set(tool_keys) if tool_keys is not None else None
    if router.authorization_policy is not None and resolved_config.principal is None:
        for tool in router.registry.tools():
            if selected is not None and tool.key not in selected:
                continue
            for endpoint in tool.endpoints:
                router._audit_export_authorization(
                    None,
                    tool,
                    endpoint,
                    run_id=resolved_config.run_id,
                    principal_audit_id=resolved_config.principal_audit_id,
                )
        raise PolicyViolationError(
            "principal context is required when authorization_policy is configured"
        )

    tools = []
    for tool in router.registry.tools():
        if selected is not None and tool.key not in selected:
            continue
        for endpoint in tool.endpoints:
            try:
                exported = to_langchain_tool(
                    router,
                    tool.key,
                    endpoint.name,
                    run_config=resolved_config,
                )
            except PolicyViolationError:
                continue
            tools.append(exported)
    return tools
