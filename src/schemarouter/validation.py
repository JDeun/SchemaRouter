from __future__ import annotations

from copy import deepcopy
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


def projected_output_schema(
    endpoint: EndpointSpec,
    selected_fields: list[str],
) -> dict[str, Any]:
    """Return a conservative schema for an explicitly server-projected response.

    Declared object-only source paths can be narrowed recursively, including a root array whose
    items are objects. Unsupported shapes (for example refs/unions/arrays inside a selected path)
    retain the full schema and therefore fail closed.
    """

    schema = deepcopy(effective_output_schema(endpoint))
    if endpoint.server_projection is None or not selected_fields or not schema:
        return schema

    field_map = {field.name: field for field in endpoint.output_fields}
    selected = [
        field_map[name]
        for name in selected_fields
        if name in field_map
    ]
    if not selected:
        return schema

    selection_tree: dict[str, Any] = {}
    for field in selected:
        current = selection_tree
        path = field.projection_path
        if not path:
            return schema
        for index, part in enumerate(path):
            if index == len(path) - 1:
                existing = current.get(part)
                if isinstance(existing, dict) and existing:
                    return schema
                current[part] = None
                continue

            existing = current.get(part)
            if existing is None and part in current:
                return schema
            if existing is None:
                child: dict[str, Any] = {}
                current[part] = child
                current = child
            elif isinstance(existing, dict):
                current = existing
            else:
                return schema

    def narrow_object(
        object_schema: dict[str, Any],
        tree: dict[str, Any],
    ) -> dict[str, Any] | None:
        if object_schema.get("type") != "object":
            return None
        properties = object_schema.get("properties")
        if not isinstance(properties, dict):
            return None
        if any(name not in properties for name in tree):
            return None

        narrowed_properties: dict[str, Any] = {}
        for name, subtree in tree.items():
            property_schema = properties[name]
            if not isinstance(property_schema, dict):
                return None
            if subtree is None:
                narrowed_properties[name] = deepcopy(property_schema)
                continue
            if not isinstance(subtree, dict) or not subtree:
                return None
            narrowed_child = narrow_object(property_schema, subtree)
            if narrowed_child is None:
                return None
            narrowed_properties[name] = narrowed_child

        narrowed = deepcopy(object_schema)
        narrowed["properties"] = narrowed_properties

        required = object_schema.get("required")
        if isinstance(required, list):
            narrowed_required = [
                name
                for name in required
                if name in tree
            ]
            if narrowed_required:
                narrowed["required"] = narrowed_required
            else:
                narrowed.pop("required", None)
        return narrowed

    narrowed = narrow_object(schema, selection_tree)
    if narrowed is not None:
        return narrowed

    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        narrowed_items = narrow_object(schema["items"], selection_tree)
        if narrowed_items is not None:
            schema["items"] = narrowed_items
            return schema

    return schema


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
