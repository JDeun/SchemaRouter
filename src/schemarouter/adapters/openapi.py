from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse

import httpx

from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec

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


def _resolve_local_ref(document: dict[str, Any], value: Any) -> Any:
    if not isinstance(value, dict) or "$ref" not in value:
        return value
    ref = value["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return value
    node: Any = document
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[part]
    return deepcopy(node)


def _schema_properties(document: dict[str, Any], schema: Any) -> dict[str, dict[str, Any]]:
    schema = _resolve_local_ref(document, schema)
    if not isinstance(schema, dict):
        return {}
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return {}
    return {name: _resolve_local_ref(document, spec) for name, spec in props.items()}


def _parameters_schema(parameters: list[ParameterSpec]) -> dict[str, Any]:
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
    return schema


def _response_schema(document: dict[str, Any], responses: dict[str, Any]) -> dict[str, Any]:
    for code in sorted(responses, key=str):
        if str(code).startswith("2"):
            response = _resolve_local_ref(document, responses[code])
            content = response.get("content", {}) if isinstance(response, dict) else {}
            for media in ("application/json", "application/problem+json"):
                if media in content and isinstance(content[media], dict):
                    return _resolve_local_ref(document, content[media].get("schema", {}))
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
        try:
            _validate_endpoint_path(path)
        except ValueError:
            continue

        path_parameters = path_item.get("parameters", [])
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            fallback_name = path.strip("/").replace("/", "_") or "root"
            operation_id = operation.get("operationId") or f"{method.lower()}_{fallback_name}"
            parameters: list[ParameterSpec] = []
            merged_parameters = [*path_parameters, *operation.get("parameters", [])]
            seen: set[tuple[str, str]] = set()
            for raw_parameter in merged_parameters:
                parameter = _resolve_local_ref(document, raw_parameter)
                if not isinstance(parameter, dict) or "name" not in parameter:
                    continue
                location = parameter.get("in", "query")
                key = (parameter["name"], location)
                if key in seen:
                    continue
                seen.add(key)
                if location not in {"path", "query", "header"}:
                    continue
                if (
                    location == "header"
                    and str(parameter["name"]).casefold() in _SENSITIVE_RUNTIME_HEADERS
                ):
                    continue
                parameters.append(
                    ParameterSpec(
                        name=parameter["name"],
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
                required_body = (
                    set(body_schema.get("required", []))
                    if isinstance(body_schema, dict)
                    else set()
                )
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
                    input_schema=_parameters_schema(parameters),
                    output_schema=response_schema if isinstance(response_schema, dict) else {},
                    method=method.upper(),
                    path=path,
                    read_only=method.lower() in {"get", "head", "options"},
                    destructive=method.lower() == "delete",
                    metadata={
                        "tags": operation.get("tags", []),
                        "security": operation.get("security"),
                        "deprecated": bool(operation.get("deprecated", False)),
                    },
                )
            )

    return ToolSpec(
        name=name,
        namespace=namespace,
        description=(document.get("info") or {}).get("description", ""),
        endpoints=endpoints,
        metadata={
            "adapter": "openapi",
            "openapi": document.get("openapi"),
            "title": (document.get("info") or {}).get("title"),
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
        self.trusted_header_names = set(trusted_names)
        self.timeout = timeout

    async def __call__(self, endpoint_name: str, arguments: dict[str, Any]) -> Any:
        endpoint = self.tool.endpoint(endpoint_name)
        if not endpoint.method or not endpoint.path:
            raise RuntimeError(f"endpoint {endpoint_name!r} is missing HTTP method/path")

        try:
            _validate_endpoint_path(endpoint.path)
        except ValueError as exc:
            raise RuntimeError(f"unsafe endpoint path for {endpoint_name!r}") from exc

        path = endpoint.path
        query: dict[str, Any] = {}
        body: dict[str, Any] = {}
        headers: dict[str, str] = {}

        for parameter in endpoint.parameters:
            if parameter.name not in arguments:
                continue
            value = arguments[parameter.name]
            if parameter.location == "path":
                encoded = quote(str(value), safe="").replace(".", "%2E")
                path = path.replace("{" + parameter.name + "}", encoded)
            elif parameter.location == "query":
                query[parameter.name] = value
            elif parameter.location == "header":
                normalized_name = parameter.name.casefold()
                if not _HEADER_NAME_RE.fullmatch(parameter.name):
                    raise RuntimeError(f"invalid header parameter name: {parameter.name!r}")
                if normalized_name in self.trusted_header_names:
                    raise RuntimeError(
                        f"tool argument cannot override trusted header {parameter.name!r}"
                    )
                if normalized_name in _SENSITIVE_RUNTIME_HEADERS:
                    raise RuntimeError(
                        f"sensitive header {parameter.name!r} must come from trusted runtime auth"
                    )
                headers[parameter.name] = str(value)
            elif parameter.location == "body":
                body[parameter.name] = value

        if re.search(r"{[^{}]+}", path):
            raise RuntimeError(f"unresolved path parameter in endpoint {endpoint_name!r}")

        headers.update(self.trusted_headers)

        # Concatenation is intentional: urljoin would normalize dot-segments or allow an
        # absolute path to replace the approved server path prefix.
        url = self.base_url + "/" + path.lstrip("/")
        if _origin(url) != self.approved_origin:
            raise RuntimeError("endpoint path escaped the approved API origin")

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            response = await client.request(
                endpoint.method,
                url,
                params=query or None,
                json=body or None,
                headers=headers or None,
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "json" in content_type:
                return response.json()
            return {"text": response.text}
