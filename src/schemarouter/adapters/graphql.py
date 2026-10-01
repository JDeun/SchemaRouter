from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .._url_safety import safe_provenance_url
from ..errors import (
    InvocationUnavailableError,
    NonRetryableInvocationError,
    SchemaSourceError,
)
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolCall, ToolSpec
from .base import AdapterContext, AdapterLoadResult, DiscoveryProfile, RefreshProfile

_MAX_INTROSPECTION_BYTES = 5 * 1024 * 1024
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
_MAX_TYPE_DEPTH = 8
_MAX_DEFAULT_SELECTION_FIELDS = 16


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_.-").lower()
    return slug or "graphql"


def _validate_graphql_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SchemaSourceError("GraphQL endpoint must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise SchemaSourceError("GraphQL endpoint URL must not contain credentials")
    if parsed.fragment:
        raise SchemaSourceError("GraphQL endpoint URL must not contain a fragment")
    return url


def _type_ref_selection(depth: int = 7) -> str:
    value = "kind name"
    for _ in range(depth):
        value = f"kind name ofType {{ {value} }}"
    return value


_TYPE_REF = _type_ref_selection()
_INTROSPECTION_QUERY = f"""
query SchemaRouterIntrospection {{
  __schema {{
    queryType {{ name }}
    mutationType {{ name }}
    subscriptionType {{ name }}
    types {{
      kind
      name
      description
      fields(includeDeprecated: true) {{
        name
        description
        isDeprecated
        deprecationReason
        args {{
          name
          description
          defaultValue
          type {{ {_TYPE_REF} }}
        }}
        type {{ {_TYPE_REF} }}
      }}
      inputFields {{
        name
        description
        defaultValue
        type {{ {_TYPE_REF} }}
      }}
      enumValues(includeDeprecated: true) {{
        name
        description
        isDeprecated
      }}
      possibleTypes {{
        kind
        name
      }}
    }}
  }}
}}
""".strip()


async def _bounded_post(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None,
    payload: dict[str, Any],
    max_bytes: int,
) -> dict[str, Any]:
    _validate_graphql_url(url)
    async with client.stream(
        "POST",
        url,
        headers=headers,
        json=payload,
        follow_redirects=False,
    ) as response:
        if response.is_redirect:
            raise SchemaSourceError("GraphQL redirects are not followed automatically")
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > max_bytes:
                raise SchemaSourceError(
                    f"GraphQL response exceeds {max_bytes} byte safety limit"
                )

        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise SchemaSourceError(
                    f"GraphQL response exceeds {max_bytes} byte safety limit"
                )
            chunks.append(chunk)

    try:
        value = json.loads(b"".join(chunks))
    except json.JSONDecodeError as exc:
        raise SchemaSourceError("GraphQL endpoint did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise SchemaSourceError("GraphQL endpoint returned a non-object response")
    return value


def _type_index(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    types = schema.get("types")
    if not isinstance(types, list):
        return {}
    return {
        str(item["name"]): item
        for item in types
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }


def _is_non_null(ref: Any) -> bool:
    return isinstance(ref, dict) and ref.get("kind") == "NON_NULL"


def _unwrap_non_null(ref: Any) -> Any:
    if _is_non_null(ref):
        return ref.get("ofType")
    return ref


def _type_signature(ref: Any) -> str | None:
    if not isinstance(ref, dict):
        return None
    kind = ref.get("kind")
    name = ref.get("name")
    if kind == "NON_NULL":
        inner = _type_signature(ref.get("ofType"))
        return f"{inner}!" if inner else None
    if kind == "LIST":
        inner = _type_signature(ref.get("ofType"))
        return f"[{inner}]" if inner else None
    if isinstance(name, str) and name:
        return name
    return None


def _scalar_schema(name: str) -> dict[str, Any]:
    if name in {"String", "ID"}:
        return {"type": "string"}
    if name == "Int":
        return {"type": "integer"}
    if name == "Float":
        return {"type": "number"}
    if name == "Boolean":
        return {"type": "boolean"}
    return {}


def _json_schema_for_type(
    ref: Any,
    types: dict[str, dict[str, Any]],
    *,
    input_position: bool,
    depth: int = 0,
    ancestors: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if depth >= _MAX_TYPE_DEPTH or not isinstance(ref, dict):
        return {}

    nullable = not _is_non_null(ref)
    value = _unwrap_non_null(ref)
    if not isinstance(value, dict):
        return {}

    kind = value.get("kind")
    name = value.get("name")
    if kind == "LIST":
        item_schema = _json_schema_for_type(
            value.get("ofType"),
            types,
            input_position=input_position,
            depth=depth + 1,
            ancestors=ancestors,
        )
        schema: dict[str, Any] = {
            "type": "array",
            "items": item_schema,
        }
    elif kind == "SCALAR" and isinstance(name, str):
        schema = _scalar_schema(name)
    elif kind == "ENUM" and isinstance(name, str):
        definition = types.get(name, {})
        enum_values = definition.get("enumValues")
        values = (
            [
                str(item["name"])
                for item in enum_values
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
            if isinstance(enum_values, list)
            else []
        )
        schema = {"type": "string"}
        if values:
            schema["enum"] = values
    elif kind in {"OBJECT", "INTERFACE", "INPUT_OBJECT"} and isinstance(name, str):
        if name in ancestors:
            schema = {"type": "object"}
        else:
            definition = types.get(name, {})
            raw_fields = (
                definition.get("inputFields")
                if kind == "INPUT_OBJECT"
                else definition.get("fields")
            )
            properties: dict[str, Any] = {}
            required: list[str] = []
            if isinstance(raw_fields, list):
                for field in raw_fields:
                    if not isinstance(field, dict):
                        continue
                    field_name = field.get("name")
                    field_type = field.get("type")
                    if not isinstance(field_name, str):
                        continue
                    properties[field_name] = _json_schema_for_type(
                        field_type,
                        types,
                        input_position=input_position,
                        depth=depth + 1,
                        ancestors=ancestors | {name},
                    )
                    description = field.get("description")
                    if isinstance(description, str) and description:
                        properties[field_name] = {
                            **properties[field_name],
                            "description": description,
                        }
                    if input_position and _is_non_null(field_type):
                        required.append(field_name)
            schema = {
                "type": "object",
                "properties": properties,
                "additionalProperties": True,
            }
            if input_position and required:
                schema["required"] = required
    elif kind == "UNION" and isinstance(name, str):
        definition = types.get(name, {})
        possible = definition.get("possibleTypes")
        options: list[dict[str, Any]] = []
        if isinstance(possible, list):
            for item in possible:
                if not isinstance(item, dict):
                    continue
                option_name = item.get("name")
                if not isinstance(option_name, str):
                    continue
                options.append(
                    _json_schema_for_type(
                        {"kind": "OBJECT", "name": option_name},
                        types,
                        input_position=False,
                        depth=depth + 1,
                        ancestors=ancestors | {name},
                    )
                )
        schema = {"anyOf": options} if options else {}
    else:
        schema = {}

    if nullable and schema:
        raw_type = schema.get("type")
        if isinstance(raw_type, str):
            schema = dict(schema)
            schema["type"] = [raw_type, "null"]
    return schema


def _input_contract(
    args: list[dict[str, Any]],
    types: dict[str, dict[str, Any]],
) -> tuple[list[ParameterSpec], dict[str, Any], dict[str, str]]:
    parameters: list[ParameterSpec] = []
    properties: dict[str, Any] = {}
    required: list[str] = []
    signatures: dict[str, str] = {}

    for arg in args:
        name = arg.get("name")
        ref = arg.get("type")
        if not isinstance(name, str):
            continue
        schema = _json_schema_for_type(
            ref,
            types,
            input_position=True,
        )
        description = str(arg.get("description") or "")
        parameters.append(
            ParameterSpec(
                name=name,
                description=description,
                required=_is_non_null(ref),
                location="argument",
                json_schema=schema,
            )
        )
        properties[name] = schema
        if _is_non_null(ref):
            required.append(name)
        signature = _type_signature(ref)
        if signature:
            signatures[name] = signature

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        input_schema["required"] = required
    return parameters, input_schema, signatures


def _schema_has_type(schema: dict[str, Any], expected: str) -> bool:
    raw = schema.get("type")
    if isinstance(raw, str):
        return raw == expected
    return isinstance(raw, list) and expected in raw


def _graphql_field_name(path: tuple[str, ...]) -> str:
    parts: list[str] = []
    for segment in path:
        if segment == "*":
            if not parts:
                raise ValueError("array wildcard cannot be the first named field segment")
            parts[-1] = parts[-1] + "[]"
            continue
        parts.append(segment)
    return ".".join(parts)


def _fields_from_output_schema(schema: dict[str, Any]) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    seen: set[str] = set()

    def visit(value: dict[str, Any], *, prefix: tuple[str, ...], depth: int) -> None:
        if depth >= _MAX_TYPE_DEPTH:
            return
        if _schema_has_type(value, "array"):
            items = value.get("items")
            if isinstance(items, dict):
                visit(
                    items,
                    prefix=(*prefix, "*") if prefix else prefix,
                    depth=depth + 1,
                )
            return

        properties = value.get("properties")
        if not isinstance(properties, dict):
            return
        for name, child in properties.items():
            if not isinstance(name, str) or not isinstance(child, dict):
                continue
            path = (*prefix, name)
            field_name = _graphql_field_name(path)
            if field_name not in seen:
                seen.add(field_name)
                fields.append(
                    FieldSpec(
                        name=field_name,
                        description=str(child.get("description") or ""),
                        json_schema=child,
                        aliases=[name.replace("_", " ")],
                        path=list(path) if prefix else [],
                        result_path=(
                            list(path)
                            if "*" in path
                            else ([field_name] if prefix else [])
                        ),
                        identifier=(
                            name in {"id", "uuid", "key"}
                            or name.endswith("_id")
                        ),
                        source_type="graphql",
                    )
                )
            visit(child, prefix=path, depth=depth + 1)

    visit(schema, prefix=(), depth=0)
    return fields


def _default_field_names(schema: dict[str, Any]) -> list[str]:
    if _schema_has_type(schema, "array"):
        items = schema.get("items")
        if isinstance(items, dict):
            return _default_field_names(items)
        return []

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []

    identifiers = [
        name
        for name in ("id", "uuid", "key")
        if name in properties and isinstance(properties[name], dict)
    ]
    scalar = [
        name
        for name, child in properties.items()
        if isinstance(child, dict)
        and not _schema_has_type(child, "object")
        and not _schema_has_type(child, "array")
    ]
    return list(dict.fromkeys([*identifiers, *scalar]))[:_MAX_DEFAULT_SELECTION_FIELDS]


def _selection_tree(paths: list[tuple[str, ...]]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path in paths:
        parts = [part for part in path if part != "*"]
        if not parts:
            continue
        node = tree
        for index, part in enumerate(parts):
            if index == len(parts) - 1:
                existing = node.get(part)
                if not isinstance(existing, dict):
                    node[part] = None
                continue
            existing = node.get(part)
            if not isinstance(existing, dict):
                child: dict[str, Any] = {}
                node[part] = child
                node = child
            else:
                node = existing
    return tree


def _child_schema(schema: dict[str, Any]) -> dict[str, Any]:
    if _schema_has_type(schema, "array"):
        items = schema.get("items")
        return items if isinstance(items, dict) else {}
    return schema


def _render_selection(
    schema: dict[str, Any],
    tree: dict[str, Any],
) -> str:
    schema = _child_schema(schema)
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return ""

    if not tree:
        names = _default_field_names(schema)
        return " ".join(names or ["__typename"])

    rendered: list[str] = []
    for name, subtree in tree.items():
        child = properties.get(name)
        if not isinstance(child, dict):
            continue
        complex_child = _schema_has_type(child, "object") or _schema_has_type(
            child,
            "array",
        )
        if isinstance(subtree, dict) and subtree:
            nested = _render_selection(child, subtree)
            rendered.append(f"{name} {{ {nested or '__typename'} }}")
        elif complex_child:
            nested = _render_selection(child, {})
            rendered.append(f"{name} {{ {nested or '__typename'} }}")
        else:
            rendered.append(name)
    return " ".join(rendered or ["__typename"])


def _operation_query(
    endpoint: EndpointSpec,
    fields: list[str],
) -> str:
    operation = str(endpoint.execution_metadata["graphql_operation"])
    field_name = str(endpoint.execution_metadata["graphql_field"])
    arg_types = endpoint.execution_metadata.get("graphql_arg_types")
    if not isinstance(arg_types, dict):
        arg_types = {}

    variables = [
        f"${name}: {signature}"
        for name, signature in arg_types.items()
        if isinstance(name, str) and isinstance(signature, str)
    ]
    call_args = [
        f"{name}: ${name}"
        for name in arg_types
        if isinstance(name, str)
    ]
    variable_clause = f"({', '.join(variables)})" if variables else ""
    argument_clause = f"({', '.join(call_args)})" if call_args else ""

    field_map = {field.name: field for field in endpoint.output_fields}
    selection_paths = [
        field_map[name].projection_path
        for name in fields
        if name in field_map
    ]
    selection = _render_selection(
        endpoint.output_schema,
        _selection_tree(selection_paths),
    )
    selection_clause = f" {{ {selection} }}" if selection else ""
    return (
        f"{operation} SchemaRouter{variable_clause} "
        f"{{ {field_name}{argument_clause}{selection_clause} }}"
    )


def _root_fields(
    schema: dict[str, Any],
    root_name: str | None,
) -> list[dict[str, Any]]:
    if not root_name:
        return []
    definition = _type_index(schema).get(root_name, {})
    fields = definition.get("fields")
    if not isinstance(fields, list):
        return []
    return [item for item in fields if isinstance(item, dict)]


def tool_from_graphql_introspection(
    name: str,
    introspection: dict[str, Any],
    *,
    namespace: str | None = None,
) -> ToolSpec:
    data = introspection.get("data")
    if not isinstance(data, dict):
        raise SchemaSourceError("GraphQL introspection response is missing data")
    schema = data.get("__schema")
    if not isinstance(schema, dict):
        raise SchemaSourceError("GraphQL introspection response is missing __schema")

    types = _type_index(schema)
    query_type = schema.get("queryType")
    mutation_type = schema.get("mutationType")
    subscription_type = schema.get("subscriptionType")
    query_name = query_type.get("name") if isinstance(query_type, dict) else None
    mutation_name = mutation_type.get("name") if isinstance(mutation_type, dict) else None
    subscription_name = (
        subscription_type.get("name")
        if isinstance(subscription_type, dict)
        else None
    )

    endpoints: list[EndpointSpec] = []
    for operation, root_name in (("query", query_name), ("mutation", mutation_name)):
        for field in _root_fields(schema, root_name):
            field_name = field.get("name")
            if not isinstance(field_name, str):
                continue
            args = field.get("args")
            arg_list = (
                [item for item in args if isinstance(item, dict)]
                if isinstance(args, list)
                else []
            )
            parameters, input_schema, arg_types = _input_contract(arg_list, types)
            output_schema = _json_schema_for_type(
                field.get("type"),
                types,
                input_position=False,
            )
            endpoints.append(
                EndpointSpec(
                    name=field_name,
                    description=str(field.get("description") or ""),
                    parameters=parameters,
                    input_schema=input_schema,
                    output_fields=_fields_from_output_schema(output_schema),
                    output_schema=output_schema,
                    method="POST",
                    path="/",
                    read_only=True if operation == "query" else False,
                    destructive=False if operation == "query" else None,
                    execution_metadata={
                        "transport": "graphql",
                        "graphql_operation": operation,
                        "graphql_field": field_name,
                        "graphql_arg_types": arg_types,
                    },
                    metadata={
                        "deprecated": bool(field.get("isDeprecated", False)),
                        "deprecation_reason": field.get("deprecationReason"),
                    },
                )
            )

    if not endpoints:
        raise SchemaSourceError("GraphQL schema exposes no usable query or mutation fields")

    return ToolSpec(
        name=name,
        namespace=namespace,
        description="GraphQL introspected capability surface",
        remote=True,
        source_type="graphql",
        endpoints=endpoints,
        execution_metadata={"adapter": "graphql"},
        metadata={
            "adapter": "graphql",
            "remote": True,
            "subscription_root": subscription_name,
            "subscriptions_supported": False,
        },
    )


class GraphQLRemoteInvoker:
    """Call-aware GraphQL executor that renders selected fields as a selection set."""

    projects_fields = False

    def __init__(
        self,
        tool: ToolSpec,
        endpoint_url: str,
        *,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.tool = tool
        self.endpoint_url = _validate_graphql_url(endpoint_url)
        self.trusted_headers = dict(trusted_headers or {})
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.http_client = http_client

    async def invoke_call(self, call: ToolCall) -> Any:
        endpoint = self.tool.endpoint(call.endpoint)
        query = _operation_query(endpoint, call.fields)
        payload = {
            "query": query,
            "variables": dict(call.arguments),
        }

        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
        )
        try:
            try:
                response = await _bounded_post(
                    client,
                    self.endpoint_url,
                    headers=self.trusted_headers,
                    payload=payload,
                    max_bytes=self.max_response_bytes,
                )
            except httpx.TimeoutException as exc:
                raise InvocationUnavailableError("GraphQL request timed out") from exc
            except httpx.TransportError as exc:
                raise InvocationUnavailableError("GraphQL transport failed") from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {408, 425, 429} or status >= 500:
                    raise InvocationUnavailableError(
                        f"GraphQL transport temporarily unavailable: HTTP {status}"
                    ) from exc
                raise NonRetryableInvocationError(
                    f"GraphQL request failed with HTTP {status}"
                ) from exc
            except SchemaSourceError as exc:
                raise NonRetryableInvocationError(str(exc)) from exc

            errors = response.get("errors")
            if isinstance(errors, list) and errors:
                raise NonRetryableInvocationError(
                    "GraphQL response contained execution errors"
                )
            data = response.get("data")
            if not isinstance(data, dict):
                raise NonRetryableInvocationError("GraphQL response is missing data")
            field_name = str(endpoint.execution_metadata["graphql_field"])
            if field_name not in data:
                raise NonRetryableInvocationError(
                    f"GraphQL response is missing root field {field_name!r}"
                )
            return data[field_name]
        finally:
            if owns_client:
                await client.aclose()


class GraphQLSourceAdapter:
    kind = "graphql"
    priority = 70
    discovery = DiscoveryProfile(
        activity="active",
        http_methods=("POST",),
    )
    refresh = RefreshProfile(
        mode="url",
        source_key="source_url",
        source_location="metadata",
    )

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        if context.base_url is not None:
            raise SchemaSourceError(
                "base_url is not valid for GraphQL; the source URL is the execution endpoint"
            )

        owns_client = context.http_client is None
        client = context.http_client or httpx.AsyncClient(
            timeout=context.timeout,
            follow_redirects=False,
        )
        try:
            try:
                response = await _bounded_post(
                    client,
                    context.url,
                    headers=context.schema_headers,
                    payload={"query": _INTROSPECTION_QUERY},
                    max_bytes=_MAX_INTROSPECTION_BYTES,
                )
            except SchemaSourceError:
                raise
            except (
                httpx.TimeoutException,
                httpx.TransportError,
                httpx.HTTPStatusError,
            ):
                raise
            except Exception:  # noqa: BLE001
                return None

            data = response.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("__schema"), dict):
                errors = response.get("errors")
                if isinstance(errors, list) and errors:
                    raise SchemaSourceError(
                        "GraphQL introspection is unavailable or disabled"
                    )
                return None

            inferred_name = context.name or _slug(
                urlparse(context.url).hostname or "graphql"
            )
            tool = tool_from_graphql_introspection(
                inferred_name,
                response,
                namespace=context.namespace,
            )
            tool.execution_metadata.update(
                {
                    "execution_bound": True,
                    "approved_endpoint_url": safe_provenance_url(context.url),
                }
            )
            tool.metadata.update(
                {
                    "source_url": safe_provenance_url(context.url),
                }
            )
            invoker = GraphQLRemoteInvoker(
                tool,
                context.url,
                trusted_headers=context.trusted_headers,
                timeout=context.timeout,
                http_client=context.http_client,
            )
            return AdapterLoadResult(tool=tool, invoker=invoker)
        finally:
            if owns_client:
                await client.aclose()
