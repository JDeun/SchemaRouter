from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urljoin

import httpx

from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolSpec

_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


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


def _response_schema(document: dict[str, Any], responses: dict[str, Any]) -> dict[str, Any]:
    for code in sorted(responses, key=str):
        if str(code).startswith("2"):
            response = _resolve_local_ref(document, responses[code])
            content = response.get("content", {}) if isinstance(response, dict) else {}
            for media in ("application/json", "application/problem+json"):
                if media in content and isinstance(content[media], dict):
                    return _resolve_local_ref(document, content[media].get("schema", {}))
    return {}


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
        if not isinstance(path_item, dict):
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
                    method=method.upper(),
                    path=path,
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
        return urljoin(source_url, str(servers[0]["url"]))
    return urljoin(source_url, "/")


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
        self.tool = tool
        self.base_url = base_url
        self.trusted_headers = dict(trusted_headers or {})
        self.timeout = timeout

    async def __call__(self, endpoint_name: str, arguments: dict[str, Any]) -> Any:
        endpoint = self.tool.endpoint(endpoint_name)
        if not endpoint.method or not endpoint.path:
            raise RuntimeError(f"endpoint {endpoint_name!r} is missing HTTP method/path")

        path = endpoint.path
        query: dict[str, Any] = {}
        body: dict[str, Any] = {}
        headers = dict(self.trusted_headers)

        for parameter in endpoint.parameters:
            if parameter.name not in arguments:
                continue
            value = arguments[parameter.name]
            if parameter.location == "path":
                path = path.replace("{" + parameter.name + "}", str(value))
            elif parameter.location == "query":
                query[parameter.name] = value
            elif parameter.location == "header":
                headers[parameter.name] = str(value)
            elif parameter.location == "body":
                body[parameter.name] = value

        url = urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
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
