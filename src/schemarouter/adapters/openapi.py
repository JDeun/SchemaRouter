from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any
from urllib.parse import quote, unquote, urldefrag, urljoin, urlparse

import httpx

from ..errors import InvocationUnavailableError, NonRetryableInvocationError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolCall, ToolSpec
from ..openapi_compatibility import analyze_openapi_compatibility

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
_SENSITIVE_RUNTIME_HEADERS = {
    "authorization",
    "connection",
    "content-length",
    "cookie",
    "host",
    "proxy-authorization",
    "transfer-encoding",
    "upgrade",
}
_OPENAPI_IGNORED_HEADER_PARAMETERS = {
    "accept",
    "authorization",
    "content-type",
}
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_\x60|~0-9A-Za-z-]+$")
_MAX_RUNTIME_RESPONSE_BYTES = 16 * 1024 * 1024
_TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

_SCHEMA_MAP_KEYWORDS = {
    "$defs",
    "definitions",
    "dependentSchemas",
    "patternProperties",
    "properties",
}
_SCHEMA_SINGLE_KEYWORDS = {
    "additionalProperties",
    "contains",
    "else",
    "if",
    "items",
    "not",
    "propertyNames",
    "then",
    "unevaluatedItems",
    "unevaluatedProperties",
}
_SCHEMA_LIST_KEYWORDS = {
    "allOf",
    "anyOf",
    "oneOf",
    "prefixItems",
}


def _normalize_openapi30_schema(schema: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Translate OAS 3.0 nullable semantics into ordinary JSON Schema type unions."""

    normalized: dict[str, Any] = {}
    converted = 0

    for key, value in schema.items():
        if key in _SCHEMA_MAP_KEYWORDS and isinstance(value, dict):
            mapped: dict[str, Any] = {}
            for child_name, child_schema in value.items():
                if isinstance(child_schema, dict):
                    child, child_count = _normalize_openapi30_schema(child_schema)
                    mapped[str(child_name)] = child
                    converted += child_count
                else:
                    mapped[str(child_name)] = deepcopy(child_schema)
            normalized[key] = mapped
            continue

        if key in _SCHEMA_SINGLE_KEYWORDS and isinstance(value, dict):
            child, child_count = _normalize_openapi30_schema(value)
            normalized[key] = child
            converted += child_count
            continue

        if key in _SCHEMA_LIST_KEYWORDS and isinstance(value, list):
            items: list[Any] = []
            for child_schema in value:
                if isinstance(child_schema, dict):
                    child, child_count = _normalize_openapi30_schema(child_schema)
                    items.append(child)
                    converted += child_count
                else:
                    items.append(deepcopy(child_schema))
            normalized[key] = items
            continue

        normalized[key] = deepcopy(value)

    if normalized.get("nullable") is True and "type" in normalized:
        raw_type = normalized.get("type")
        if isinstance(raw_type, str):
            normalized["type"] = (
                [raw_type, "null"]
                if raw_type != "null"
                else ["null"]
            )
            normalized.pop("nullable", None)
            converted += 1
        elif isinstance(raw_type, list) and all(
            isinstance(item, str) for item in raw_type
        ):
            normalized["type"] = list(dict.fromkeys([*raw_type, "null"]))
            normalized.pop("nullable", None)
            converted += 1

    return normalized, converted


def _normalize_openapi30_document(
    document: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    """Normalize Schema Objects without rewriting examples or arbitrary extension payloads."""

    result = deepcopy(document)
    converted = 0

    def visit(node: Any, path: tuple[str, ...] = ()) -> None:
        nonlocal converted
        if isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, (*path, str(index)))
            return
        if not isinstance(node, dict):
            return

        if len(path) >= 2 and path[-2:] == ("components", "schemas"):
            for name, schema in list(node.items()):
                if not isinstance(schema, dict):
                    continue
                normalized, count = _normalize_openapi30_schema(schema)
                node[name] = normalized
                converted += count
            return

        if (
            path
            and path[0] == "x-schemarouter-external-refs"
            and node.get("nullable") is True
            and "type" in node
        ):
            normalized, count = _normalize_openapi30_schema(node)
            node.clear()
            node.update(normalized)
            converted += count
            return

        for key, value in list(node.items()):
            if key in {"example", "examples", "default", "enum", "const"}:
                continue
            if key.startswith("x-") and key != "x-schemarouter-external-refs":
                continue
            if key == "schema" and isinstance(value, dict):
                normalized, count = _normalize_openapi30_schema(value)
                node[key] = normalized
                converted += count
                continue
            visit(value, (*path, str(key)))

    visit(result)
    return result, converted


def _local_ref_target(document: dict[str, Any], ref: str) -> Any | None:
    if not ref.startswith("#/"):
        return None
    node: Any = document
    try:
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            node = node[part]
    except (KeyError, TypeError):
        return None
    return deepcopy(node)


def _resolve_local_ref(document: dict[str, Any], value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    current = deepcopy(value)
    seen: set[str] = set()
    while isinstance(current, dict):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            break
        target = _local_ref_target(document, ref)
        if target is None:
            break
        seen.add(ref)
        siblings = {key: item for key, item in current.items() if key != "$ref"}
        if siblings and isinstance(target, dict):
            merged = deepcopy(target)
            merged.update(deepcopy(siblings))
            current = merged
        else:
            current = target
    return current


def _schema_fragments(
    document: dict[str, Any],
    schema: Any,
    *,
    seen_refs: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    if not isinstance(schema, dict):
        return []

    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/"):
        if ref in seen_refs:
            return []
        target = _local_ref_target(document, ref)
        fragments: list[dict[str, Any]] = []
        if isinstance(target, dict):
            fragments.extend(
                _schema_fragments(
                    document,
                    target,
                    seen_refs=seen_refs | {ref},
                )
            )
        siblings = {key: value for key, value in schema.items() if key != "$ref"}
        if siblings:
            fragments.extend(
                _schema_fragments(
                    document,
                    siblings,
                    seen_refs=seen_refs,
                )
            )
        return fragments

    fragments = [schema]
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for branch in all_of:
            fragments.extend(
                _schema_fragments(
                    document,
                    branch,
                    seen_refs=seen_refs,
                )
            )
    return fragments


def _schema_properties(document: dict[str, Any], schema: Any) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for fragment in _schema_fragments(document, schema):
        props = fragment.get("properties", {})
        if not isinstance(props, dict):
            continue
        for name, spec in props.items():
            resolved = _resolve_local_ref(document, spec)
            if not isinstance(resolved, dict):
                resolved = {}
            if name in merged and merged[name] != resolved:
                merged[name] = {"allOf": [merged[name], resolved]}
            else:
                merged[name] = resolved
    return merged


def _schema_required(document: dict[str, Any], schema: Any) -> set[str]:
    required: set[str] = set()
    for fragment in _schema_fragments(document, schema):
        names = fragment.get("required")
        if isinstance(names, list):
            required.update(name for name in names if isinstance(name, str))
    return required


def _schema_variant_branches(
    document: dict[str, Any],
    schema: Any,
    *,
    seen_refs: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Collect oneOf/anyOf branches for planner-side response field discovery.

    The original composed schema remains authoritative for runtime validation. This helper only
    exposes conditional response fields to the planner and never rewrites request-body semantics.
    """

    if not isinstance(schema, dict):
        return []

    branches: list[dict[str, Any]] = []
    seen_canonical: set[str] = set()

    for fragment in _schema_fragments(
        document,
        schema,
        seen_refs=seen_refs,
    ):
        for construct in ("oneOf", "anyOf"):
            raw_branches = fragment.get(construct)
            if not isinstance(raw_branches, list):
                continue
            for raw_branch in raw_branches:
                if not isinstance(raw_branch, dict):
                    continue

                next_seen = seen_refs
                ref = raw_branch.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/"):
                    if ref in seen_refs:
                        continue
                    next_seen = seen_refs | {ref}

                resolved = _resolve_local_ref(document, raw_branch)
                if not isinstance(resolved, dict):
                    continue

                canonical = json.dumps(
                    resolved,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                if canonical not in seen_canonical:
                    seen_canonical.add(canonical)
                    branches.append(resolved)

                for nested in _schema_variant_branches(
                    document,
                    resolved,
                    seen_refs=next_seen,
                ):
                    nested_canonical = json.dumps(
                        nested,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    )
                    if nested_canonical in seen_canonical:
                        continue
                    seen_canonical.add(nested_canonical)
                    branches.append(nested)

    return branches


def _with_components(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    resolved = deepcopy(schema)
    components = document.get("components")
    if isinstance(components, dict) and components:
        resolved["components"] = deepcopy(components)
    external_refs = document.get("x-schemarouter-external-refs")
    if isinstance(external_refs, dict) and external_refs:
        resolved["x-schemarouter-external-refs"] = deepcopy(external_refs)
    return resolved


def normalize_same_document_refs(
    document: dict[str, Any],
    source_url: str,
) -> tuple[dict[str, Any], int]:
    """Rewrite URI refs that resolve back to the loaded OpenAPI document as local refs."""
    source_resource, _ = urldefrag(source_url)
    normalized_count = 0

    def visit(value: Any) -> Any:
        nonlocal normalized_count
        if isinstance(value, dict):
            result = {key: visit(item) for key, item in value.items()}
            ref = result.get("$ref")
            if isinstance(ref, str) and not ref.startswith("#"):
                absolute = urljoin(source_resource, ref)
                resource, fragment = urldefrag(absolute)
                decoded_fragment = unquote(fragment)
                if resource == source_resource and decoded_fragment.startswith("/"):
                    result["$ref"] = "#" + decoded_fragment
                    normalized_count += 1
            return result
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value

    return visit(deepcopy(document)), normalized_count


def _openapi_parameter_defaults(location: str) -> tuple[str | None, bool | None]:
    if location == "query":
        return "form", True
    if location in {"path", "header"}:
        return "simple", False
    return None, None


def _with_openapi_parameter_defaults(parameter: ParameterSpec) -> ParameterSpec:
    default_style, default_explode = _openapi_parameter_defaults(parameter.location)
    if parameter.style is not None and parameter.explode is not None:
        return parameter
    return parameter.model_copy(
        update={
            "style": parameter.style or default_style,
            "explode": (
                parameter.explode
                if parameter.explode is not None
                else default_explode
            ),
        },
        deep=True,
    )


def _parameter_atom(value: Any, *, context: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    raise NonRetryableInvocationError(
        f"{context} contains a nested non-scalar value that cannot be serialized safely"
    )


def _path_atom(value: Any, *, context: str) -> str:
    return quote(_parameter_atom(value, context=context), safe="").replace(".", "%2E")


def _serialize_simple_path(parameter: ParameterSpec, value: Any) -> str:
    context = f"path parameter {parameter.name!r}"
    if isinstance(value, list):
        return ",".join(_path_atom(item, context=context) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        if parameter.explode:
            for key, item in value.items():
                parts.append(
                    f"{_path_atom(key, context=context)}={_path_atom(item, context=context)}"
                )
        else:
            for key, item in value.items():
                parts.extend(
                    (
                        _path_atom(key, context=context),
                        _path_atom(item, context=context),
                    )
                )
        return ",".join(parts)
    return _path_atom(value, context=context)


def _serialize_form_query(
    parameter: ParameterSpec,
    wire_name: str,
    value: Any,
) -> list[tuple[str, str]]:
    context = f"query parameter {parameter.name!r}"
    if parameter.allow_reserved:
        raise NonRetryableInvocationError(
            f"allowReserved=true is not supported for query parameter {parameter.name!r}"
        )
    if isinstance(value, list):
        if parameter.explode:
            return [
                (wire_name, _parameter_atom(item, context=context))
                for item in value
            ]
        return [
            (
                wire_name,
                ",".join(_parameter_atom(item, context=context) for item in value),
            )
        ]
    if isinstance(value, dict):
        if parameter.explode:
            return [
                (
                    _parameter_atom(key, context=context),
                    _parameter_atom(item, context=context),
                )
                for key, item in value.items()
            ]
        parts: list[str] = []
        for key, item in value.items():
            parts.extend(
                (
                    _parameter_atom(key, context=context),
                    _parameter_atom(item, context=context),
                )
            )
        return [(wire_name, ",".join(parts))]
    return [(wire_name, _parameter_atom(value, context=context))]


def _serialize_simple_header(parameter: ParameterSpec, value: Any) -> str:
    context = f"header parameter {parameter.name!r}"
    if isinstance(value, list):
        return ",".join(_parameter_atom(item, context=context) for item in value)
    if isinstance(value, dict):
        parts: list[str] = []
        if parameter.explode:
            for key, item in value.items():
                parts.append(
                    f"{_parameter_atom(key, context=context)}="
                    f"{_parameter_atom(item, context=context)}"
                )
        else:
            for key, item in value.items():
                parts.extend(
                    (
                        _parameter_atom(key, context=context),
                        _parameter_atom(item, context=context),
                    )
                )
        return ",".join(parts)
    return _parameter_atom(value, context=context)


def _disambiguate_parameter_names(
    parameters: list[ParameterSpec],
) -> list[ParameterSpec]:
    counts: dict[str, int] = {}
    for parameter in parameters:
        counts[parameter.name] = counts.get(parameter.name, 0) + 1

    used: set[str] = set()
    result: list[ParameterSpec] = []
    for parameter in parameters:
        raw_name = parameter.name
        logical_name = raw_name
        if counts[raw_name] > 1 or logical_name in used:
            base = f"{parameter.location}__{raw_name}"
            logical_name = base
            suffix = 2
            while logical_name in used:
                logical_name = f"{base}__{suffix}"
                suffix += 1

        used.add(logical_name)
        if logical_name == raw_name:
            result.append(parameter)
        else:
            result.append(
                parameter.model_copy(
                    update={
                        "name": logical_name,
                        "wire_name": parameter.wire_name or raw_name,
                    },
                    deep=True,
                )
            )
    return result


def _discriminated_body_schema(
    document: dict[str, Any],
    schema: Any,
) -> tuple[dict[str, Any], str] | None:
    """Return a safe tagged-union request body schema and discriminator property.

    SchemaRouter intentionally supports only explicit oneOf tagged unions here. Every branch must
    be object-like, require the discriminator property, and constrain that property to one unique
    const/single-value enum. This avoids flattening incompatible variant fields.
    """

    if not isinstance(schema, dict):
        return None

    discriminator = schema.get("discriminator")
    if not isinstance(discriminator, dict):
        return None
    property_name = discriminator.get("propertyName")
    if not isinstance(property_name, str) or not property_name:
        return None

    raw_branches = schema.get("oneOf")
    if not isinstance(raw_branches, list) or len(raw_branches) < 2:
        return None

    seen_tags: set[str] = set()
    for raw_branch in raw_branches:
        branch = _resolve_local_ref(document, raw_branch)
        if not isinstance(branch, dict):
            return None

        properties = _schema_properties(document, branch)
        required = _schema_required(document, branch)
        if property_name not in properties or property_name not in required:
            return None

        if branch.get("type") not in {None, "object"}:
            return None

        tag_schema = properties[property_name]
        raw_tag = tag_schema.get("const")
        if raw_tag is None:
            enum = tag_schema.get("enum")
            if not isinstance(enum, list) or len(enum) != 1:
                return None
            raw_tag = enum[0]

        if not isinstance(raw_tag, (str, int, float, bool)) or raw_tag is None:
            return None
        tag = json.dumps(raw_tag, sort_keys=True, ensure_ascii=True)
        if tag in seen_tags:
            return None
        seen_tags.add(tag)

    return schema, property_name


def _parameters_schema(
    document: dict[str, Any],
    parameters: list[ParameterSpec],
) -> dict[str, Any]:
    properties = {
        parameter.name: parameter.json_schema or {}
        for parameter in parameters
    }
    required = [
        parameter.name
        for parameter in parameters
        if parameter.required
    ]
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return _with_components(document, schema)


def _success_response_schemas(
    document: dict[str, Any],
    responses: Any,
) -> tuple[list[dict[str, Any]], bool]:
    """Collect supported success payload schemas and whether all success variants are validated."""
    if not isinstance(responses, dict):
        return [], False

    schemas: list[dict[str, Any]] = []
    validation_complete = True
    seen: set[str] = set()

    for code in sorted(responses, key=str):
        code_text = str(code).upper()
        if not re.fullmatch(r"2(?:[0-9]{2}|XX)", code_text):
            continue

        response = _resolve_local_ref(document, responses[code])
        if not isinstance(response, dict):
            validation_complete = False
            continue

        content = response.get("content")
        if content is None or content == {}:
            schema: dict[str, Any] = {"type": "null"}
        elif not isinstance(content, dict):
            validation_complete = False
            continue
        else:
            schema = {}
            found_supported_media = False
            for media in ("application/json", "application/problem+json"):
                media_spec = content.get(media)
                if not isinstance(media_spec, dict):
                    continue
                found_supported_media = True
                resolved = _resolve_local_ref(document, media_spec.get("schema", {}))
                if not isinstance(resolved, dict):
                    validation_complete = False
                    break
                schema = resolved
                break
            if not found_supported_media:
                validation_complete = False
                continue
            if not validation_complete and not schema:
                continue

        canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        if canonical not in seen:
            seen.add(canonical)
            schemas.append(schema)

    return schemas, validation_complete


def _combined_response_schema(
    document: dict[str, Any],
    schemas: list[dict[str, Any]],
    *,
    validation_complete: bool,
) -> dict[str, Any]:
    if not schemas or not validation_complete:
        return {}
    if len(schemas) == 1:
        return _with_components(document, schemas[0])
    return _with_components(document, {"anyOf": schemas})


def _response_properties(
    document: dict[str, Any],
    schemas: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for schema in schemas:
        if schema.get("type") == "null":
            continue

        property_sets = [_schema_properties(document, schema)]
        property_sets.extend(
            _schema_properties(document, branch)
            for branch in _schema_variant_branches(document, schema)
        )

        for properties in property_sets:
            for name, spec in properties.items():
                existing = merged.get(name)
                if existing is None or existing == spec:
                    merged[name] = spec
                    continue

                options = (
                    list(existing["anyOf"])
                    if set(existing) == {"anyOf"}
                    and isinstance(existing.get("anyOf"), list)
                    else [existing]
                )
                if spec not in options:
                    options.append(spec)
                merged[name] = {"anyOf": options}
    return merged


def _origin(url: str) -> tuple[str, str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be an absolute http(s) URL")
    default_port = 443 if parsed.scheme == "https" else 80
    return parsed.scheme.lower(), parsed.hostname.lower(), parsed.port or default_port


def same_origin(left: str, right: str) -> bool:
    try:
        return _origin(left) == _origin(right)
    except ValueError:
        return False


def _validate_endpoint_path(path: str) -> None:
    parsed = urlparse(path)
    if (
        not path.startswith("/")
        or parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("endpoint path must be a relative absolute-path without query/fragment")
    for segment in parsed.path.split("/"):
        if unquote(segment).casefold() in {".", ".."}:
            raise ValueError("endpoint path must not contain dot segments")


def _merge_parameters(
    document: dict[str, Any],
    path_parameters: list[Any],
    operation_parameters: list[Any],
) -> list[dict[str, Any]]:
    """Merge OpenAPI parameters with operation-level definitions overriding path-level ones."""
    merged: list[dict[str, Any]] = []
    positions: dict[tuple[str, str], int] = {}

    for raw_parameter in path_parameters:
        parameter = _resolve_local_ref(document, raw_parameter)
        if not isinstance(parameter, dict):
            continue
        name = parameter.get("name")
        location = parameter.get("in", "query")
        if not isinstance(name, str) or not name or not isinstance(location, str):
            continue
        key = (name, location)
        if key in positions:
            continue
        positions[key] = len(merged)
        merged.append(parameter)

    operation_seen: set[tuple[str, str]] = set()
    for raw_parameter in operation_parameters:
        parameter = _resolve_local_ref(document, raw_parameter)
        if not isinstance(parameter, dict):
            continue
        name = parameter.get("name")
        location = parameter.get("in", "query")
        if not isinstance(name, str) or not name or not isinstance(location, str):
            continue
        key = (name, location)
        if key in operation_seen:
            continue
        operation_seen.add(key)
        if key in positions:
            merged[positions[key]] = parameter
        else:
            positions[key] = len(merged)
            merged.append(parameter)

    return merged


def _disambiguate_generated_endpoint_names(
    endpoints: list[EndpointSpec],
) -> list[EndpointSpec]:
    """Resolve internal fallback-name collisions without rewriting explicit operationId values."""
    counts: dict[str, int] = {}
    for endpoint in endpoints:
        counts[endpoint.name] = counts.get(endpoint.name, 0) + 1

    reserved = {
        endpoint.name
        for endpoint in endpoints
        if counts[endpoint.name] == 1
        or not bool(endpoint.metadata.get("operation_id_generated"))
    }
    result: list[EndpointSpec] = []
    for endpoint in endpoints:
        if (
            counts[endpoint.name] == 1
            or not bool(endpoint.metadata.get("operation_id_generated"))
        ):
            result.append(endpoint)
            continue

        seed = f"{endpoint.method or ''} {endpoint.path or ''}"
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
        candidate_base = f"{endpoint.name}__{digest}"
        candidate = candidate_base
        suffix = 2
        while candidate in reserved:
            candidate = f"{candidate_base}__{suffix}"
            suffix += 1
        reserved.add(candidate)

        metadata = dict(endpoint.metadata)
        metadata["generated_operation_id_base"] = endpoint.name
        metadata["generated_operation_id_disambiguated"] = True
        result.append(
            endpoint.model_copy(
                update={"name": candidate, "metadata": metadata},
                deep=True,
            )
        )

    return result


def tool_from_openapi(
    name: str,
    document: dict[str, Any],
    *,
    namespace: str | None = None,
) -> ToolSpec:
    """Create a ToolSpec from an OpenAPI 3.x document.

    The adapter intentionally supports a stable common subset and preserves unsupported constructs
    in metadata instead of guessing their runtime semantics.
    """
    nullable_normalized = 0
    version = document.get("openapi")
    if isinstance(version, str) and version.startswith("3.0."):
        document, nullable_normalized = _normalize_openapi30_document(document)

    endpoints: list[EndpointSpec] = []
    for path, path_item in document.get("paths", {}).items():
        if not isinstance(path, str) or not isinstance(path_item, dict):
            continue
        path_item = _resolve_local_ref(document, path_item)
        if not isinstance(path_item, dict):
            continue
        try:
            _validate_endpoint_path(path)
        except ValueError:
            continue

        path_parameters = path_item.get("parameters", [])
        if not isinstance(path_parameters, list):
            path_parameters = []
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            explicit_operation_id = operation.get("operationId")
            fallback_name = path.strip("/").replace("/", "_") or "root"
            operation_id = (
                explicit_operation_id
                if isinstance(explicit_operation_id, str) and explicit_operation_id
                else f"{method.lower()}_{fallback_name}"
            )
            parameters: list[ParameterSpec] = []
            operation_parameters = operation.get("parameters", [])
            if not isinstance(operation_parameters, list):
                operation_parameters = []
            merged_parameters = _merge_parameters(
                document,
                path_parameters,
                operation_parameters,
            )
            for parameter in merged_parameters:
                parameter_name = parameter["name"]
                location = parameter.get("in", "query")
                if location not in {"path", "query", "header"}:
                    continue
                if location == "header":
                    normalized_parameter_name = parameter_name.casefold()
                    if (
                        normalized_parameter_name in _SENSITIVE_RUNTIME_HEADERS
                        or normalized_parameter_name in _OPENAPI_IGNORED_HEADER_PARAMETERS
                    ):
                        continue
                default_style, default_explode = _openapi_parameter_defaults(location)
                raw_style = parameter.get("style")
                raw_explode = parameter.get("explode")
                parameters.append(
                    ParameterSpec(
                        name=parameter_name,
                        description=parameter.get("description", ""),
                        required=bool(parameter.get("required")) or location == "path",
                        location=location,
                        style=raw_style if isinstance(raw_style, str) else default_style,
                        explode=(
                            raw_explode
                            if isinstance(raw_explode, bool)
                            else default_explode
                        ),
                        allow_reserved=(
                            bool(parameter.get("allowReserved"))
                            if location == "query"
                            else False
                        ),
                        json_schema=_resolve_local_ref(document, parameter.get("schema", {})),
                    )
                )

            request_body_required = False
            request_body_mode: str | None = None
            request_body_discriminator: str | None = None
            request_body = _resolve_local_ref(document, operation.get("requestBody", {}))
            if isinstance(request_body, dict):
                content = request_body.get("content", {})
                json_body = content.get("application/json", {}) if isinstance(content, dict) else {}
                body_schema = (
                    _resolve_local_ref(document, json_body.get("schema", {}))
                    if isinstance(json_body, dict)
                    else {}
                )
                body_properties = _schema_properties(document, body_schema)
                tagged_union = _discriminated_body_schema(document, body_schema)

                if tagged_union is not None:
                    tagged_schema, discriminator_property = tagged_union
                    parameters.append(
                        ParameterSpec(
                            name="body",
                            description=(
                                "OpenAPI discriminated JSON request body "
                                f"(tag: {discriminator_property})"
                            ),
                            required=bool(request_body.get("required")),
                            location="body_root",
                            json_schema=tagged_schema,
                            aliases=["request body", "json body"],
                        )
                    )
                    request_body_required = bool(request_body.get("required"))
                    request_body_mode = "discriminated_root"
                    request_body_discriminator = discriminator_property
                else:
                    body_type = (
                        body_schema.get("type")
                        if isinstance(body_schema, dict)
                        else None
                    )
                    body_is_supported_object = (
                        isinstance(body_schema, dict)
                        and bool(body_schema)
                        and (
                            body_type == "object"
                            or (body_type is None and bool(body_properties))
                        )
                        and "oneOf" not in body_schema
                        and "anyOf" not in body_schema
                    )
                    if body_is_supported_object:
                        request_body_required = bool(request_body.get("required"))
                        request_body_mode = "flattened_object"
                        required_body = _schema_required(document, body_schema)
                        for prop_name, prop_schema in body_properties.items():
                            parameters.append(
                                ParameterSpec(
                                    name=prop_name,
                                    description=(
                                        prop_schema.get("description", "")
                                        if isinstance(prop_schema, dict)
                                        else ""
                                    ),
                                    required=prop_name in required_body,
                                    location="body",
                                    json_schema=(
                                        prop_schema if isinstance(prop_schema, dict) else {}
                                    ),
                                )
                            )
                    elif isinstance(body_schema, dict) and bool(body_schema):
                        parameters.append(
                            ParameterSpec(
                                name="body",
                                description="OpenAPI JSON request body",
                                required=bool(request_body.get("required")),
                                location="body_root",
                                json_schema=body_schema,
                                aliases=["request body", "json body"],
                            )
                        )
                        request_body_required = bool(request_body.get("required"))
                        request_body_mode = "root_schema"

            parameters = _disambiguate_parameter_names(parameters)

            response_schemas, response_validation_complete = _success_response_schemas(
                document,
                operation.get("responses", {}),
            )
            response_schema = _combined_response_schema(
                document,
                response_schemas,
                validation_complete=response_validation_complete,
            )
            fields = [
                FieldSpec(
                    name=field_name,
                    description=(
                        field_schema.get("description", "")
                        if isinstance(field_schema, dict)
                        else ""
                    ),
                    json_schema=field_schema if isinstance(field_schema, dict) else {},
                    identifier=field_name in {"id", "uuid", "key"} or field_name.endswith("_id"),
                    aliases=[field_name.replace("_", " ")],
                )
                for field_name, field_schema in _response_properties(
                    document, response_schemas
                ).items()
            ]

            endpoints.append(
                EndpointSpec(
                    name=operation_id,
                    description=operation.get("summary") or operation.get("description", ""),
                    parameters=parameters,
                    output_fields=fields,
                    input_schema=_parameters_schema(document, parameters),
                    output_schema=response_schema if isinstance(response_schema, dict) else {},
                    method=method.upper(),
                    path=path,
                    read_only=method.lower() in {"get", "head", "options"},
                    destructive=method.lower() == "delete",
                    execution_metadata={
                        "request_body_required": request_body_required,
                        "request_body_mode": request_body_mode,
                        "request_body_discriminator": request_body_discriminator,
                    },
                    metadata={
                        "tags": operation.get("tags", []),
                        "security": operation.get("security"),
                        "deprecated": bool(operation.get("deprecated", False)),
                        # Kept as descriptive mirrors for backward-compatible inspection. Runtime
                        # behavior reads the fingerprinted execution_metadata contract above.
                        "request_body_required": request_body_required,
                        "request_body_mode": request_body_mode,
                        "request_body_discriminator": request_body_discriminator,
                        "operation_id_generated": not (
                            isinstance(explicit_operation_id, str)
                            and bool(explicit_operation_id)
                        ),
                    },
                )
            )

    endpoints = _disambiguate_generated_endpoint_names(endpoints)
    compatibility = analyze_openapi_compatibility(document)
    return ToolSpec(
        name=name,
        namespace=namespace,
        description=(document.get("info") or {}).get("description", ""),
        endpoints=endpoints,
        execution_metadata={"adapter": "openapi"},
        metadata={
            "adapter": "openapi",
            "openapi": document.get("openapi"),
            "title": (document.get("info") or {}).get("title"),
            "openapi_30_nullable_normalized": nullable_normalized,
            "compatibility": compatibility.model_dump(mode="json", by_alias=True),
        },
    )


def resolve_openapi_base_url(document: dict[str, Any], source_url: str) -> str:
    servers = document.get("servers") or []
    if servers and isinstance(servers[0], dict) and servers[0].get("url"):
        resolved = urljoin(source_url, str(servers[0]["url"]))
    else:
        resolved = urljoin(source_url, "/")

    parsed = urlparse(resolved)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("OpenAPI server URL is not a safe absolute http(s) base URL")
    return resolved


class OpenAPIRemoteInvoker:
    """Minimal trusted HTTP executor for a parsed OpenAPI tool."""

    def __init__(
        self,
        tool: ToolSpec,
        base_url: str,
        *,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_response_bytes: int = _MAX_RUNTIME_RESPONSE_BYTES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        parsed_base = urlparse(base_url)
        if parsed_base.scheme not in {"http", "https"} or not parsed_base.netloc:
            raise ValueError("base_url must be an absolute http(s) URL")
        if parsed_base.username or parsed_base.password:
            raise ValueError("base_url must not contain credentials")
        if parsed_base.query or parsed_base.fragment:
            raise ValueError("base_url must not contain query or fragment")

        trusted = dict(trusted_headers or {})
        trusted_names = [name.casefold() for name in trusted]
        if len(trusted_names) != len(set(trusted_names)):
            raise ValueError("trusted_headers contains case-insensitive duplicate names")
        for name in trusted:
            if not _HEADER_NAME_RE.fullmatch(name):
                raise ValueError(f"invalid trusted header name: {name!r}")

        self.tool = tool
        self.base_url = base_url.rstrip("/")
        self.approved_origin = _origin(base_url)
        self.trusted_headers = trusted
        if (
            isinstance(max_response_bytes, bool)
            or not isinstance(max_response_bytes, int)
            or max_response_bytes <= 0
        ):
            raise ValueError("max_response_bytes must be a positive integer")

        self.trusted_header_names = set(trusted_names)
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.http_client = http_client

    async def __call__(self, endpoint: str, arguments: dict[str, Any]) -> Any:
        return await self._invoke(endpoint, arguments, selected_fields=None)

    async def invoke_call(self, call: ToolCall) -> Any:
        return await self._invoke(
            call.endpoint,
            dict(call.arguments),
            selected_fields=list(call.fields),
        )

    async def _invoke(
        self,
        endpoint: str,
        arguments: dict[str, Any],
        *,
        selected_fields: list[str] | None,
    ) -> Any:
        endpoint_name = endpoint
        endpoint_spec = self.tool.endpoint(endpoint_name)
        if not endpoint_spec.method or not endpoint_spec.path:
            raise NonRetryableInvocationError(
                f"endpoint {endpoint_name!r} is missing HTTP method/path"
            )

        try:
            _validate_endpoint_path(endpoint_spec.path)
        except ValueError as exc:
            raise NonRetryableInvocationError(
                f"unsafe endpoint path for {endpoint_name!r}"
            ) from exc

        path = endpoint_spec.path
        query: list[tuple[str, str]] = []
        body: dict[str, Any] = {}
        root_body: Any | None = None
        root_body_seen = False
        headers: dict[str, str] = {}

        for parameter in endpoint_spec.parameters:
            if parameter.name not in arguments:
                continue
            value = arguments[parameter.name]
            wire_name = parameter.wire_name or parameter.name
            effective_parameter = _with_openapi_parameter_defaults(parameter)
            if parameter.location == "path":
                if effective_parameter.style != "simple":
                    raise NonRetryableInvocationError(
                        f"unsupported path parameter style {parameter.style!r} "
                        f"for {parameter.name!r}"
                    )
                encoded = _serialize_simple_path(effective_parameter, value)
                path = path.replace("{" + wire_name + "}", encoded)
            elif parameter.location == "query":
                if effective_parameter.style != "form":
                    raise NonRetryableInvocationError(
                        f"unsupported query parameter style {parameter.style!r} "
                        f"for {parameter.name!r}"
                    )
                query.extend(
                    _serialize_form_query(effective_parameter, wire_name, value)
                )
            elif parameter.location == "header":
                normalized_name = wire_name.casefold()
                if not _HEADER_NAME_RE.fullmatch(wire_name):
                    raise NonRetryableInvocationError(
                        f"invalid header parameter name: {wire_name!r}"
                    )
                if normalized_name in self.trusted_header_names:
                    raise NonRetryableInvocationError(
                        f"tool argument cannot override trusted header {wire_name!r}"
                    )
                if normalized_name in _SENSITIVE_RUNTIME_HEADERS:
                    raise NonRetryableInvocationError(
                        f"sensitive header {wire_name!r} must come from trusted runtime auth"
                    )
                if effective_parameter.style != "simple":
                    raise NonRetryableInvocationError(
                        f"unsupported header parameter style {parameter.style!r} "
                        f"for {parameter.name!r}"
                    )
                headers[wire_name] = _serialize_simple_header(
                    effective_parameter,
                    value,
                )
            elif parameter.location == "body":
                body[wire_name] = value
            elif parameter.location == "body_root":
                if root_body_seen:
                    raise NonRetryableInvocationError(
                        f"multiple root request bodies for endpoint {endpoint_name!r}"
                    )
                root_body = value
                root_body_seen = True

        if root_body_seen and body:
            raise NonRetryableInvocationError(
                f"mixed root and flattened request body for endpoint {endpoint_name!r}"
            )

        if re.search(r"{[^{}]+}", path):
            raise NonRetryableInvocationError(
                f"unresolved path parameter in endpoint {endpoint_name!r}"
            )

        if endpoint_spec.server_projection is not None and selected_fields:
            field_map = {field.name: field for field in endpoint_spec.output_fields}
            selectors = [
                endpoint_spec.server_projection.selector_for(field_map[name])
                for name in selected_fields
                if name in field_map
            ]
            if selectors:
                parameter_name = endpoint_spec.server_projection.parameter
                query = [
                    (name, value)
                    for name, value in query
                    if name != parameter_name
                ]
                query.append(
                    (
                        parameter_name,
                        endpoint_spec.server_projection.separator.join(selectors),
                    )
                )

        headers.update(self.trusted_headers)

        request_body_mode = endpoint_spec.execution_metadata.get("request_body_mode")
        if (
            request_body_mode in {"root_schema", "discriminated_root"}
            and bool(endpoint_spec.execution_metadata.get("request_body_required"))
            and not root_body_seen
        ):
            raise NonRetryableInvocationError(
                f"required root request body missing for endpoint {endpoint_name!r}"
            )

        # Concatenation is intentional: urljoin would normalize dot-segments or allow an
        # absolute path to replace the approved server path prefix.
        url = self.base_url + "/" + path.lstrip("/")
        if _origin(url) != self.approved_origin:
            raise NonRetryableInvocationError(
                "endpoint path escaped the approved API origin"
            )

        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
        )
        try:
            request_kwargs: dict[str, Any] = {
                "params": query or None,
                "headers": headers or None,
                "follow_redirects": False,
            }
            if root_body_seen:
                try:
                    request_kwargs["content"] = json.dumps(
                        root_body,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                except (TypeError, ValueError) as exc:
                    raise NonRetryableInvocationError(
                        f"root request body for endpoint {endpoint_name!r} is not JSON serializable"
                    ) from exc
                if not any(name.casefold() == "content-type" for name in headers):
                    request_kwargs["headers"] = {
                        **headers,
                        "Content-Type": "application/json",
                    }
            else:
                request_kwargs["json"] = (
                    body
                    if body or bool(endpoint_spec.execution_metadata.get("request_body_required"))
                    else None
                )

            async with client.stream(
                endpoint_spec.method,
                url,
                **request_kwargs,
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if response.status_code not in _TRANSIENT_HTTP_STATUS_CODES:
                        raise NonRetryableInvocationError(
                            "OpenAPI request failed with non-retryable HTTP status "
                            f"{response.status_code}"
                        ) from exc
                    raise InvocationUnavailableError(
                        "OpenAPI access path is temporarily unavailable with HTTP status "
                        f"{response.status_code}"
                    ) from exc

                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        declared_size = None
                    if (
                        declared_size is not None
                        and declared_size > self.max_response_bytes
                    ):
                        raise NonRetryableInvocationError(
                            "OpenAPI response exceeds "
                            f"{self.max_response_bytes} byte safety limit"
                        )

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.max_response_bytes:
                        raise NonRetryableInvocationError(
                            "OpenAPI response exceeds "
                            f"{self.max_response_bytes} byte safety limit"
                        )
                    chunks.append(chunk)

                content = b"".join(chunks)
                content_type = response.headers.get("content-type", "").lower()
                encoding = response.encoding or "utf-8"
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
            raise InvocationUnavailableError(
                "OpenAPI access path is temporarily unavailable"
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if not content and (
            endpoint_spec.method == "HEAD"
            or response.status_code in {204, 205}
            or not content_type
        ):
            return None
        if "json" in content_type:
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise NonRetryableInvocationError(
                    "OpenAPI response declared JSON but could not be decoded"
                ) from exc
        return {"text": content.decode(encoding, errors="replace")}
