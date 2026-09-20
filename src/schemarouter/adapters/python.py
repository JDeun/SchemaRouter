from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel, TypeAdapter

from ..errors import RegistrationError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec

_CALL_ENDPOINT = "call"


def _schema_for(annotation: Any) -> dict[str, Any]:
    if annotation is inspect.Signature.empty:
        return {}
    try:
        return TypeAdapter(annotation).json_schema()
    except Exception as exc:  # noqa: BLE001
        raise RegistrationError(
            f"cannot derive JSON Schema for annotation {annotation!r}"
        ) from exc


def _top_level_object_schema(schema: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/$defs/"):
        return schema
    name = ref.removeprefix("#/$defs/")
    definitions = schema.get("$defs", {})
    resolved = definitions.get(name)
    return resolved if isinstance(resolved, dict) else schema


def _fields_from_schema(schema: dict[str, Any]) -> list[FieldSpec]:
    object_schema = _top_level_object_schema(schema)
    properties = object_schema.get("properties", {})
    if not isinstance(properties, dict):
        return []

    return [
        FieldSpec(
            name=name,
            description=(
                field_schema.get("description", "")
                if isinstance(field_schema, dict)
                else ""
            ),
            json_schema=field_schema if isinstance(field_schema, dict) else {},
            identifier=name in {"id", "uuid", "key"} or name.endswith("_id"),
            aliases=[name.replace("_", " ")],
        )
        for name, field_schema in properties.items()
    ]


def tool_from_callable(
    function: Callable[..., Any],
    *,
    name: str | None = None,
    namespace: str | None = None,
    description: str | None = None,
    read_only: bool | None = None,
    destructive: bool | None = None,
) -> ToolSpec:
    """Create a typed ToolSpec from a normal Python callable."""
    signature = inspect.signature(function)
    try:
        hints = get_type_hints(function)
    except Exception:  # noqa: BLE001
        hints = {}

    parameters: list[ParameterSpec] = []
    properties: dict[str, Any] = {}
    required: list[str] = []

    for parameter in signature.parameters.values():
        if parameter.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise RegistrationError(
                f"callable {function.__name__!r} has positional-only parameter "
                f"{parameter.name!r}; SchemaRouter invokes Python tools by keyword"
            )
        if parameter.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            raise RegistrationError(
                f"callable {function.__name__!r} uses variadic parameter "
                f"{parameter.name!r}; variadic Python tools require an explicit ToolSpec"
            )

        annotation = hints.get(parameter.name, parameter.annotation)
        parameter_schema = _schema_for(annotation)
        is_required = parameter.default is inspect.Signature.empty
        parameters.append(
            ParameterSpec(
                name=parameter.name,
                required=is_required,
                location="argument",
                json_schema=parameter_schema,
            )
        )
        properties[parameter.name] = parameter_schema
        if is_required:
            required.append(parameter.name)

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        input_schema["required"] = required

    return_annotation = hints.get("return", signature.return_annotation)
    output_schema = _schema_for(return_annotation)
    endpoint = EndpointSpec(
        name=_CALL_ENDPOINT,
        description=description or inspect.getdoc(function) or "",
        parameters=parameters,
        output_fields=_fields_from_schema(output_schema),
        input_schema=input_schema,
        output_schema=output_schema,
        read_only=read_only,
        destructive=destructive,
        metadata={
            "adapter": "python",
            "callable_name": function.__qualname__,
            "callable_module": function.__module__,
        },
    )
    return ToolSpec(
        name=name or function.__name__,
        namespace=namespace,
        description=description or inspect.getdoc(function) or "",
        endpoints=[endpoint],
        metadata={"adapter": "python"},
    )


class PythonCallableInvoker:
    """Invoke a Python callable through the common endpoint contract."""

    def __init__(self, function: Callable[..., Any]) -> None:
        self.function = function

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        if endpoint != _CALL_ENDPOINT:
            raise RuntimeError(f"unknown Python callable endpoint: {endpoint!r}")

        value = self.function(**arguments)
        if inspect.isawaitable(value):
            value = await value
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return dataclasses.asdict(value)
        return value


def schema_tool(
    *,
    name: str | None = None,
    namespace: str | None = None,
    description: str | None = None,
    read_only: bool | None = None,
    destructive: bool | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach SchemaRouter registration metadata without wrapping the function."""

    def decorator(function: Callable[..., Any]) -> Callable[..., Any]:
        function.__schemarouter_options__ = {
            "name": name,
            "namespace": namespace,
            "description": description,
            "read_only": read_only,
            "destructive": destructive,
        }
        return function

    return decorator


def callable_options(function: Callable[..., Any]) -> dict[str, Any]:
    value = getattr(function, "__schemarouter_options__", {})
    return dict(value) if isinstance(value, dict) else {}
