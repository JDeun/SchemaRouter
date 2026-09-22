from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any
from urllib.parse import quote, unquote, urldefrag, urljoin, urlparse

import httpx

from ..errors import NonRetryableInvocationError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec
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
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_\x60|~0-9A-Za-z-]+$")
_MAX_RUNTIME_RESPONSE_BYTES = 16 * 1024 * 1024
_TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


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


def _response_schema(document: dict[str, Any], responses: dict[str, Any]) -> dict[str, Any]:
    for code in sorted(responses, key=str):
        if str(code).startswith("2"):
            response = _resolve_local_ref(document, responses[code])
            content = response.get("content", {}) if isinstance(response, dict) else {}
            for media in ("application/json", "application/problem+json"):
                if media in content and isinstance(content[media], dict):
                    schema = _resolve_local_ref(document, content[media].get("schema", {}))
                    if isinstance(schema, dict):
                        return _with_components(document, schema)
                    return {}
    return {}


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

    v0.1 intentionally supports the stable common subset and preserves unsupported constructs
    in metadata instead of guessing their runtime semantics.
    """
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
                if (
                    location == "header"
                    and parameter_name.casefold() in _SENSITIVE_RUNTIME_HEADERS
                ):
                    continue
                parameters.append(
                    ParameterSpec(
                        name=parameter_name,
                        description=parameter.get("description", ""),
                        required=bool(parameter.get("required")) or location == "path",
                        location=location,
                        json_schema=_resolve_local_ref(document, parameter.get("schema", {})),
                    )
                )

            request_body = _resolve_local_ref(document, operation.get("requestBody", {}))
            if isinstance(request_body, dict):
                content = request_body.get("content", {})
                json_body = content.get("application/json", {}) if isinstance(content, dict) else {}
                body_schema = (
                    _resolve_local_ref(document, json_body.get("schema", {}))
                    if isinstance(json_body, dict)
                    else {}
                )
                required_body = _schema_required(document, body_schema)
                for prop_name, prop_schema in _schema_properties(document, body_schema).items():
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
                            json_schema=prop_schema if isinstance(prop_schema, dict) else {},
                        )
                    )

            parameters = _disambiguate_parameter_names(parameters)

            response_schema = _response_schema(document, operation.get("responses", {}))
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
                for field_name, field_schema in _schema_properties(
                    document, response_schema
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
                    metadata={
                        "tags": operation.get("tags", []),
                        "security": operation.get("security"),
                        "deprecated": bool(operation.get("deprecated", False)),
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
        metadata={
            "adapter": "openapi",
            "openapi": document.get("openapi"),
            "title": (document.get("info") or {}).get("title"),
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
        query: dict[str, Any] = {}
        body: dict[str, Any] = {}
        headers: dict[str, str] = {}

        for parameter in endpoint_spec.parameters:
            if parameter.name not in arguments:
                continue
            value = arguments[parameter.name]
            wire_name = parameter.wire_name or parameter.name
            if parameter.location == "path":
                encoded = quote(str(value), safe="").replace(".", "%2E")
                path = path.replace("{" + wire_name + "}", encoded)
            elif parameter.location == "query":
                query[wire_name] = value
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
                headers[wire_name] = str(value)
            elif parameter.location == "body":
                body[wire_name] = value

        if re.search(r"{[^{}]+}", path):
            raise NonRetryableInvocationError(
                f"unresolved path parameter in endpoint {endpoint_name!r}"
            )

        headers.update(self.trusted_headers)

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
            async with client.stream(
                endpoint_spec.method,
                url,
                params=query or None,
                json=body or None,
                headers=headers or None,
                follow_redirects=False,
            ) as response:
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    if response.status_code not in _TRANSIENT_HTTP_STATUS_CODES:
                        raise NonRetryableInvocationError(
                            "OpenAPI request failed with non-retryable HTTP status "
                            f"{response.status_code}"
                        ) from exc
                    raise

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
        finally:
            if owns_client:
                await client.aclose()

        if "json" in content_type:
            try:
                return json.loads(content)
            except json.JSONDecodeError as exc:
                raise NonRetryableInvocationError(
                    "OpenAPI response declared JSON but could not be decoded"
                ) from exc
        return {"text": content.decode(encoding, errors="replace")}
