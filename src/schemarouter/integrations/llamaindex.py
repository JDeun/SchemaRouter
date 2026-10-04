from __future__ import annotations

import asyncio
import dataclasses
import inspect
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Any, Literal, cast, get_type_hints
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, TypeAdapter

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


def _llamaindex_input_schema(tool: Any) -> dict[str, Any]:
    metadata = getattr(tool, "metadata", None)
    getter = getattr(metadata, "get_parameters_dict", None)
    if callable(getter):
        try:
            schema = getter()
        except Exception:  # noqa: BLE001
            schema = None
        if isinstance(schema, dict):
            return deepcopy(schema)

    fn_schema = getattr(metadata, "fn_schema", None)
    model_json_schema = getattr(fn_schema, "model_json_schema", None)
    if callable(model_json_schema):
        try:
            schema = model_json_schema()
        except Exception:  # noqa: BLE001
            schema = None
        if isinstance(schema, dict):
            return deepcopy(schema)
    return {}


def _llamaindex_output_schema(tool: Any) -> dict[str, Any]:
    try:
        real_fn = getattr(tool, "real_fn", None)
    except Exception:  # noqa: BLE001
        real_fn = None
    if not callable(real_fn):
        return {}

    try:
        hints = get_type_hints(real_fn)
    except Exception:  # noqa: BLE001
        hints = {}
    annotation = hints.get("return", inspect.signature(real_fn).return_annotation)
    if annotation is inspect.Signature.empty:
        return {}
    try:
        schema = TypeAdapter(annotation).json_schema()
    except Exception:  # noqa: BLE001
        return {}
    return schema if isinstance(schema, dict) else {}


def _llama_schema_properties(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {}
    return {
        str(name): value
        for name, value in properties.items()
        if isinstance(value, dict)
    }


def _llama_schema_unit(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return None
    for key in ("x-ucum-unit", "x-unit", "unit"):
        value = schema.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "inapplicable":
            return value.strip()
    return None


def _llama_parameters_from_schema(schema: dict[str, Any]) -> list[ParameterSpec]:
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
        for name, spec in _llama_schema_properties(schema).items()
    ]


def _llama_resolve_local_ref(
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


def _llama_schema_is_array(schema: dict[str, Any]) -> bool:
    raw_type = schema.get("type")
    return raw_type == "array" or (
        isinstance(raw_type, list) and "array" in raw_type
    )


def _llama_field_name(path: tuple[str, ...]) -> str:
    parts: list[str] = []
    for segment in path:
        if segment == "*":
            if not parts:
                raise ValueError("array wildcard cannot be the first named field segment")
            parts[-1] = parts[-1] + "[]"
            continue
        parts.append(segment)
    return ".".join(parts)


def _llama_fields_from_schema(schema: dict[str, Any]) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    seen: set[str] = set()
    root = _llama_resolve_local_ref(schema, schema)

    def visit(
        value: dict[str, Any],
        *,
        prefix: tuple[str, ...],
        depth: int,
        ancestors: frozenset[str],
    ) -> None:
        if depth >= 8:
            return
        resolved = _llama_resolve_local_ref(schema, value)
        signature = repr(
            sorted(
                (key, repr(item))
                for key, item in resolved.items()
            )
        )
        if signature in ancestors:
            return
        next_ancestors = ancestors | {signature}

        if _llama_schema_is_array(resolved):
            items = resolved.get("items")
            if isinstance(items, dict):
                visit(
                    items,
                    prefix=(*prefix, "*") if prefix else prefix,
                    depth=depth + 1,
                    ancestors=next_ancestors,
                )
            return

        for name, child in _llama_schema_properties(resolved).items():
            resolved_child = _llama_resolve_local_ref(schema, child)
            path = (*prefix, name)
            field_name = _llama_field_name(path)
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
                        unit=_llama_schema_unit(resolved_child),
                        identifier=(
                            name in {"id", "uuid", "key"}
                            or name.endswith("_id")
                        ),
                        source_type="llamaindex",
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


def tool_from_llamaindex(
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
    """Compile a LlamaIndex BaseTool-like object into the canonical SchemaRouter contract."""

    metadata = getattr(tool, "metadata", None)
    metadata_name = None
    name_getter = getattr(metadata, "get_name", None)
    if callable(name_getter):
        try:
            metadata_name = name_getter()
        except Exception:  # noqa: BLE001
            metadata_name = None
    if metadata_name is None:
        metadata_name = getattr(metadata, "name", None)

    tool_name = name or metadata_name
    if not isinstance(tool_name, str) or not tool_name.strip():
        raise TypeError("LlamaIndex tool must expose a non-empty name or receive name=")

    description = getattr(metadata, "description", "")
    if not isinstance(description, str):
        description = str(description)

    input_schema = _llamaindex_input_schema(tool)
    output_schema = _llamaindex_output_schema(tool)
    endpoint = EndpointSpec(
        name="invoke",
        description=description,
        parameters=_llama_parameters_from_schema(input_schema),
        input_schema=input_schema,
        output_fields=_llama_fields_from_schema(output_schema),
        output_schema=output_schema,
        read_only=read_only,
        destructive=destructive,
        execution_metadata={
            "framework": "llamaindex",
            "foreign_tool_name": tool_name,
        },
        metadata={
            "framework": "llamaindex",
            "foreign_tool_class": type(tool).__qualname__,
            "foreign_tool_module": type(tool).__module__,
        },
    )
    return ToolSpec(
        name=tool_name.strip(),
        namespace=namespace,
        description=description,
        provider=provider,
        access_mode=access_mode or "llamaindex",
        remote=remote,
        endpoints=[endpoint],
        execution_metadata={"adapter": "llamaindex_tool"},
        metadata={
            "adapter": "llamaindex_tool",
            "foreign_tool_class": type(tool).__qualname__,
            "foreign_tool_module": type(tool).__module__,
        },
    )


class LlamaIndexToolInvoker:
    """Trusted binding for one imported LlamaIndex tool object."""

    def __init__(self, tool: Any) -> None:
        self.tool = tool

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        if endpoint != "invoke":
            raise RuntimeError(f"unknown LlamaIndex tool endpoint: {endpoint!r}")

        acall = getattr(self.tool, "acall", None)
        if callable(acall):
            value = acall(**dict(arguments))
            if inspect.isawaitable(value):
                value = await value
        else:
            call = getattr(self.tool, "call", None)
            if callable(call):
                value = call(**dict(arguments))
            elif callable(self.tool):
                value = self.tool(**dict(arguments))
            else:
                raise TypeError("imported LlamaIndex tool is not callable")
            if inspect.isawaitable(value):
                value = await value

        raw_output = getattr(value, "raw_output", None)
        if raw_output is not None:
            value = raw_output
        else:
            content = getattr(value, "content", None)
            if content is not None:
                value = content

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json", by_alias=True, exclude_none=True)
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return dataclasses.asdict(value)
        return value



def _coerce_export_run_config(
    config: RunConfig | dict[str, Any] | None,
) -> RunConfig:
    if config is None:
        run_config = RunConfig()
    elif isinstance(config, RunConfig):
        run_config = config
    else:
        run_config = RunConfig.model_validate(config)
    if run_config.run_id is not None:
        return run_config
    return run_config.model_copy(update={"run_id": uuid4().hex})


def _authorized_endpoint_view(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    run_config: RunConfig,
) -> tuple[ToolSpec, EndpointSpec, EndpointSpec]:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint(endpoint_name)
    policy = router.authorization_policy
    if policy is None:
        return tool, endpoint, endpoint

    principal = run_config.principal
    authorized = router._audit_export_authorization(
        principal,
        tool,
        endpoint,
        run_id=run_config.run_id,
        principal_audit_id=run_config.principal_audit_id,
    )
    if not authorized:
        if principal is None:
            raise PolicyViolationError(
                "principal context is required when authorization_policy is configured"
            )
        raise PolicyViolationError("authorization denied for requested capability")

    projected = router._data_scope_endpoint_view(principal, tool, endpoint)
    if projected is None:
        raise PolicyViolationError("authorization denied for requested data scope")
    return tool, endpoint, projected


def to_llamaindex_tool(
    router: SchemaRouter,
    tool_key: str,
    endpoint_name: str,
    *,
    name: str | None = None,
    description: str | None = None,
    run_config: RunConfig | dict[str, Any] | None = None,
):
    """Expose one principal-aware endpoint as a LlamaIndex FunctionTool."""
    try:
        from llama_index.core.tools import FunctionTool
    except ImportError as exc:
        raise ImportError(
            'LlamaIndex integration requires: pip install "schemarouter[llamaindex]"'
        ) from exc

    resolved_config = _coerce_export_run_config(run_config)
    tool, endpoint, visible_endpoint = _authorized_endpoint_view(
        router,
        tool_key,
        endpoint_name,
        resolved_config,
    )
    fields = [field.name for field in visible_endpoint.output_fields]
    schema = effective_input_schema(visible_endpoint)
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
        plan = ExecutionPlan(
            query=f"LlamaIndex invocation of {tool_key}.{endpoint_name}",
            registry_version=router.registry.version,
            calls=[call],
        )
        result = await router.execute(plan, config=resolved_config)
        return result[0].data

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
    run_config: RunConfig | dict[str, Any] | None = None,
) -> list[Any]:
    """Expose principal-visible endpoints as LlamaIndex FunctionTool objects."""
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
                exported = to_llamaindex_tool(
                    router,
                    tool.key,
                    endpoint.name,
                    run_config=resolved_config,
                )
            except PolicyViolationError:
                continue
            tools.append(exported)
    return tools
