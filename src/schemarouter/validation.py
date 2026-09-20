from __future__ import annotations

from typing import Any

from jsonschema import exceptions, validators

from .errors import SchemaValidationError
from .models import EndpointSpec


def _synthesized_input_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    properties = {
        parameter.name: parameter.json_schema or {}
        for parameter in endpoint.parameters
    }
    required = [
        parameter.name
        for parameter in endpoint.parameters
        if parameter.required
    ]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def _synthesized_output_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    properties = {
        field.name: field.json_schema or {}
        for field in endpoint.output_fields
    }
    required = [
        name
        for name in endpoint.metadata.get("output_required", [])
        if name in properties
    ]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def effective_input_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    return endpoint.input_schema or _synthesized_input_schema(endpoint)


def effective_output_schema(endpoint: EndpointSpec) -> dict[str, Any]:
    if endpoint.output_schema:
        return endpoint.output_schema
    if endpoint.output_fields:
        return _synthesized_output_schema(endpoint)
    return {}


def validate_json_schema_value(
    value: Any,
    schema: dict[str, Any],
    *,
    context: str,
) -> None:
    if not schema:
        return

    try:
        validator_cls = validators.validator_for(schema)
        validator_cls.check_schema(schema)
        validator = validator_cls(schema)
        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
    except exceptions.SchemaError as exc:
        raise SchemaValidationError(
            f"{context}: declared JSON Schema is invalid: {exc.message}"
        ) from exc
    except Exception as exc:  # unresolved refs and validator/runtime failures fail closed
        raise SchemaValidationError(
            f"{context}: JSON Schema could not be evaluated safely"
        ) from exc

    if not errors:
        return

    first = errors[0]
    path = ".".join(str(part) for part in first.absolute_path)
    location = f" at {path}" if path else ""
    raise SchemaValidationError(
        f"{context}{location}: {first.message}"
    )
