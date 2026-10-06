from __future__ import annotations

import json
import re
import uuid
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

import httpx

from .._http_headers import validate_trusted_headers
from .._url_safety import safe_provenance_url
from ..errors import (
    InvocationUnavailableError,
    NonRetryableInvocationError,
    SchemaNotModifiedError,
    SchemaSourceError,
)
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolCall, ToolSpec
from ..network_policy import TRUSTED_INTERNAL_NETWORK_POLICY, NetworkPolicy
from ..schema_http import (
    attach_schema_http_validators,
    conditional_schema_headers,
    schema_http_validators_from_headers,
)
from ..source_identity import structured_source_identity_digest_for
from .base import AdapterContext, AdapterLoadResult, DiscoveryProfile, RefreshProfile
from .openapi import same_origin

_TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}

_MAX_DISCOVERY_BYTES = 5 * 1024 * 1024
_MAX_RESPONSE_BYTES = 10 * 1024 * 1024
_NESTED_FIELD_MAX_DEPTH = 8


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_.-").lower()
    return slug or "openrpc"


def _validate_http_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SchemaSourceError("OpenRPC URL must be absolute http(s)")
    if parsed.username or parsed.password:
        raise SchemaSourceError("OpenRPC URL must not contain credentials")
    if parsed.fragment:
        raise SchemaSourceError("OpenRPC URL must not contain a fragment")
    return url


async def _bounded_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None,
    max_bytes: int = _MAX_DISCOVERY_BYTES,
    network_policy: NetworkPolicy = TRUSTED_INTERNAL_NETWORK_POLICY,
) -> httpx.Response:
    _validate_http_url(url)
    await network_policy.authorize(url)
    async with client.stream(
        "GET",
        url,
        headers=headers,
        follow_redirects=False,
    ) as response:
        if response.status_code == 304:
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=b"",
                request=response.request,
            )
        if response.is_redirect:
            raise SchemaSourceError("OpenRPC schema redirects are not followed automatically")
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > max_bytes:
                raise SchemaSourceError(
                    f"OpenRPC document exceeds {max_bytes} byte safety limit"
                )

        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise SchemaSourceError(
                    f"OpenRPC document exceeds {max_bytes} byte safety limit"
                )
            chunks.append(chunk)

        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=b"".join(chunks),
            request=response.request,
        )


def _parse_document(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    version = value.get("openrpc")
    methods = value.get("methods")
    info = value.get("info")
    if not isinstance(version, str):
        return None
    if not isinstance(methods, list):
        return None
    if not isinstance(info, dict):
        return None
    return value


def _pointer_target(document: dict[str, Any], ref: str) -> dict[str, Any] | None:
    if not ref.startswith("#/"):
        return None
    node: Any = document
    try:
        for raw in ref[2:].split("/"):
            part = raw.replace("~1", "/").replace("~0", "~")
            node = node[part]
    except (KeyError, TypeError):
        return None
    return node if isinstance(node, dict) else None


def _resolve_local_ref(
    document: dict[str, Any],
    value: dict[str, Any],
) -> dict[str, Any]:
    current = value
    seen: set[str] = set()
    while isinstance(current, dict):
        ref = current.get("$ref")
        if not isinstance(ref, str) or not ref.startswith("#/") or ref in seen:
            return current
        seen.add(ref)
        target = _pointer_target(document, ref)
        if target is None:
            return current
        merged = deepcopy(target)
        merged.update({key: item for key, item in current.items() if key != "$ref"})
        current = merged
    return value


def _schema_properties(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    resolved = _resolve_local_ref(document, schema)
    properties = resolved.get("properties")
    if not isinstance(properties, dict):
        return {}

    merged = {
        str(name): _resolve_local_ref(document, value)
        for name, value in properties.items()
        if isinstance(value, dict)
    }

    for keyword in ("allOf", "oneOf", "anyOf"):
        branches = resolved.get(keyword)
        if not isinstance(branches, list):
            continue
        for branch in branches:
            if not isinstance(branch, dict):
                continue
            for name, spec in _schema_properties(document, branch).items():
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


def _schema_unit(schema: Any) -> str | None:
    if not isinstance(schema, dict):
        return None
    for key in ("x-ucum-unit", "x-unit", "unit"):
        value = schema.get(key)
        if isinstance(value, str) and value.strip() and value.strip() != "inapplicable":
            return value.strip()
    return None


def _openrpc_field_name(path: tuple[str, ...]) -> str:
    parts: list[str] = []
    for segment in path:
        if segment == "*":
            if not parts:
                raise ValueError("array wildcard cannot be the first named field segment")
            parts[-1] = parts[-1] + "[]"
            continue
        parts.append(segment)
    return ".".join(parts)


def _openrpc_schema_is_array(schema: dict[str, Any]) -> bool:
    raw_type = schema.get("type")
    return raw_type == "array" or (
        isinstance(raw_type, list) and "array" in raw_type
    )


def _fields_from_result_schema(
    document: dict[str, Any],
    schema: dict[str, Any],
) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    seen: set[str] = set()

    def visit(
        value: dict[str, Any],
        *,
        prefix: tuple[str, ...],
        depth: int,
        ancestors: frozenset[str],
    ) -> None:
        if depth >= _NESTED_FIELD_MAX_DEPTH:
            return
        resolved = _resolve_local_ref(document, value)
        signature = json.dumps(
            resolved,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        if signature in ancestors:
            return
        next_ancestors = ancestors | {signature}

        if _openrpc_schema_is_array(resolved):
            items = resolved.get("items")
            if isinstance(items, dict):
                visit(
                    items,
                    prefix=(*prefix, "*") if prefix else prefix,
                    depth=depth + 1,
                    ancestors=next_ancestors,
                )
            return

        for name, child in _schema_properties(document, resolved).items():
            path = (*prefix, name)
            field_name = _openrpc_field_name(path)
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
                        unit=_schema_unit(child),
                        identifier=(
                            name in {"id", "uuid", "key"}
                            or name.endswith("_id")
                        ),
                        source_type="openrpc",
                    )
                )
            visit(
                child,
                prefix=path,
                depth=depth + 1,
                ancestors=next_ancestors,
            )

    visit(schema, prefix=(), depth=0, ancestors=frozenset())
    return fields


def _input_schema(
    document: dict[str, Any],
    params: list[dict[str, Any]],
) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in params:
        resolved = _resolve_local_ref(document, param)
        name = resolved.get("name")
        schema = resolved.get("schema")
        if not isinstance(name, str) or not name:
            continue
        if not isinstance(schema, dict):
            schema = {}
        properties[name] = _resolve_local_ref(document, schema)
        if bool(resolved.get("required", False)):
            required.append(name)

    result: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        result["required"] = required
    return result


def _parameters(
    document: dict[str, Any],
    params: list[dict[str, Any]],
) -> list[ParameterSpec]:
    output: list[ParameterSpec] = []
    for param in params:
        resolved = _resolve_local_ref(document, param)
        name = resolved.get("name")
        if not isinstance(name, str) or not name:
            continue
        schema = resolved.get("schema")
        if not isinstance(schema, dict):
            schema = {}
        output.append(
            ParameterSpec(
                name=name,
                description=str(resolved.get("description") or ""),
                required=bool(resolved.get("required", False)),
                location="argument",
                json_schema=_resolve_local_ref(document, schema),
            )
        )
    return output


def _result_schema(
    document: dict[str, Any],
    method: dict[str, Any],
) -> dict[str, Any]:
    result = method.get("result")
    if not isinstance(result, dict):
        return {}
    result = _resolve_local_ref(document, result)
    schema = result.get("schema")
    if not isinstance(schema, dict):
        return {}
    return _resolve_local_ref(document, schema)


def _candidate_server_url(document: dict[str, Any]) -> str | None:
    servers = document.get("servers")
    if not isinstance(servers, list):
        return None
    for server in servers:
        if not isinstance(server, dict):
            continue
        url = server.get("url")
        if not isinstance(url, str) or "{" in url or "}" in url:
            continue
        try:
            return _validate_http_url(url)
        except SchemaSourceError:
            continue
    return None


def tool_from_openrpc(
    name: str,
    document: dict[str, Any],
    *,
    namespace: str | None = None,
) -> ToolSpec:
    parsed = _parse_document(document)
    if parsed is None:
        raise SchemaSourceError("document is not a supported OpenRPC schema")

    endpoints: list[EndpointSpec] = []
    for raw_method in parsed["methods"]:
        if not isinstance(raw_method, dict):
            continue
        method = _resolve_local_ref(parsed, raw_method)
        method_name = method.get("name")
        if not isinstance(method_name, str) or not method_name.strip():
            continue

        params_value = method.get("params")
        raw_params = (
            [item for item in params_value if isinstance(item, dict)]
            if isinstance(params_value, list)
            else []
        )
        param_structure = method.get("paramStructure", "either")
        if param_structure not in {"by-name", "by-position", "either"}:
            param_structure = "either"

        output_schema = _result_schema(parsed, method)
        endpoints.append(
            EndpointSpec(
                name=method_name,
                description=str(method.get("description") or method.get("summary") or ""),
                parameters=_parameters(parsed, raw_params),
                input_schema=_input_schema(parsed, raw_params),
                output_fields=_fields_from_result_schema(parsed, output_schema),
                output_schema=output_schema,
                method="POST",
                path="/",
                read_only=None,
                destructive=None,
                execution_metadata={
                    "transport": "jsonrpc",
                    "jsonrpc_method": method_name,
                    "param_structure": param_structure,
                },
                metadata={
                    "openrpc_tags": deepcopy(method.get("tags") or []),
                    "deprecated": bool(method.get("deprecated", False)),
                },
            )
        )

    if not endpoints:
        raise SchemaSourceError("OpenRPC document declares no usable methods")

    info = parsed.get("info") or {}
    return ToolSpec(
        name=name,
        namespace=namespace,
        description=str(info.get("description") or info.get("title") or ""),
        remote=True,
        source_type="openrpc",
        endpoints=endpoints,
        execution_metadata={"adapter": "openrpc"},
        metadata={
            "adapter": "openrpc",
            "openrpc_version": parsed.get("openrpc"),
            "api_version": info.get("version"),
            "remote": True,
        },
    )


class OpenRPCRemoteInvoker:
    """Trusted JSON-RPC 2.0 transport for a parsed OpenRPC tool."""

    def __init__(
        self,
        tool: ToolSpec,
        base_url: str,
        *,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        http_client: httpx.AsyncClient | None = None,
        network_policy: NetworkPolicy = TRUSTED_INTERNAL_NETWORK_POLICY,
    ) -> None:
        self.tool = tool
        self.base_url = _validate_http_url(base_url)
        self.trusted_headers = validate_trusted_headers(trusted_headers)
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.http_client = http_client
        self.network_policy = network_policy

    @staticmethod
    def _params(endpoint: EndpointSpec, arguments: dict[str, Any]) -> Any:
        structure = str(endpoint.execution_metadata.get("param_structure", "either"))
        if structure != "by-position":
            return dict(arguments)

        values: list[Any] = []
        missing_seen = False
        for parameter in endpoint.parameters:
            if parameter.name in arguments:
                if missing_seen:
                    raise NonRetryableInvocationError(
                        "JSON-RPC positional parameters cannot skip an earlier optional parameter"
                    )
                values.append(arguments[parameter.name])
            elif parameter.required:
                raise NonRetryableInvocationError(
                    f"missing required JSON-RPC parameter {parameter.name!r}"
                )
            else:
                missing_seen = True
        return values

    async def invoke_call(self, call: ToolCall) -> Any:
        endpoint = self.tool.endpoint(call.endpoint)
        method_name = endpoint.execution_metadata.get("jsonrpc_method")
        if not isinstance(method_name, str) or not method_name:
            raise NonRetryableInvocationError("OpenRPC endpoint is missing jsonrpc_method")

        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": method_name,
            "params": self._params(endpoint, call.arguments),
        }

        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
        )
        try:
            await self.network_policy.authorize(self.base_url)
            async with client.stream(
                "POST",
                self.base_url,
                headers=self.trusted_headers,
                json=payload,
                follow_redirects=False,
            ) as response:
                if response.is_redirect:
                    raise NonRetryableInvocationError(
                        "JSON-RPC transport redirects are not allowed"
                    )
                if response.status_code in _TRANSIENT_HTTP_STATUS_CODES:
                    raise InvocationUnavailableError(
                        f"JSON-RPC transport temporarily unavailable: HTTP {response.status_code}"
                    )
                if response.status_code >= 400:
                    raise NonRetryableInvocationError(
                        f"JSON-RPC request failed with HTTP {response.status_code}"
                    )

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self.max_response_bytes:
                        raise NonRetryableInvocationError(
                            "JSON-RPC response exceeded the safety size limit"
                        )
                    chunks.append(chunk)
                raw = b"".join(chunks)

            try:
                body = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise NonRetryableInvocationError(
                    "JSON-RPC response was not valid JSON"
                ) from exc

            if not isinstance(body, dict) or body.get("jsonrpc") != "2.0":
                raise NonRetryableInvocationError(
                    "JSON-RPC response does not declare jsonrpc='2.0'"
                )
            if body.get("id") != payload["id"]:
                raise NonRetryableInvocationError(
                    "JSON-RPC response id does not match the request id"
                )
            error = body.get("error")
            if error is not None:
                raise NonRetryableInvocationError(
                    "JSON-RPC method returned an application error"
                )
            if "result" not in body:
                raise NonRetryableInvocationError(
                    "JSON-RPC response is missing result"
                )
            return body["result"]
        except httpx.TimeoutException as exc:
            raise InvocationUnavailableError("JSON-RPC request timed out") from exc
        except httpx.TransportError as exc:
            raise InvocationUnavailableError("JSON-RPC transport failed") from exc
        finally:
            if owns_client:
                await client.aclose()


class OpenRPCSourceAdapter:
    kind = "openrpc"
    priority = 95
    discovery = DiscoveryProfile(
        activity="passive",
        http_methods=("GET",),
    )
    refresh = RefreshProfile(
        mode="url",
        source_key="source_url",
        source_location="metadata",
        http_validators=True,
    )

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        owns_client = context.http_client is None
        client = context.http_client or httpx.AsyncClient(
            timeout=context.timeout,
            follow_redirects=False,
        )
        try:
            try:
                response = await _bounded_get(
                    client,
                    context.url,
                    headers=conditional_schema_headers(
                        context.schema_headers,
                        context.schema_validators,
                    ),
                    network_policy=context.network_policy,
                )
                validators = schema_http_validators_from_headers(
                    response.headers,
                    fallback=context.schema_validators,
                )
                if response.status_code == 304:
                    raise SchemaNotModifiedError(validators=validators)
                document = response.json()
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

            parsed = _parse_document(document)
            if parsed is None:
                return None

            info = parsed.get("info") or {}
            inferred = (
                context.name
                or _slug(str(info.get("title") or urlparse(context.url).hostname or "openrpc"))
            )
            tool = tool_from_openrpc(
                inferred,
                parsed,
                namespace=context.namespace,
            )

            suggested_base = _candidate_server_url(parsed)
            selected_base = context.base_url
            if (
                selected_base is None
                and suggested_base is not None
                and same_origin(suggested_base, context.url)
            ):
                selected_base = suggested_base

            invoker = None
            if selected_base is not None:
                await context.network_policy.authorize(selected_base)
                invoker = OpenRPCRemoteInvoker(
                    tool,
                    selected_base,
                    trusted_headers=context.trusted_headers,
                    timeout=context.timeout,
                    http_client=context.http_client,
                    network_policy=context.network_policy,
                )
                tool.execution_metadata.update(
                    {
                        "execution_bound": True,
                        "approved_base_url": selected_base,
                        "requires_explicit_base_url": False,
                    }
                )
            else:
                tool.execution_metadata.update(
                    {
                        "execution_bound": False,
                        "requires_explicit_base_url": True,
                    }
                )

            tool.metadata.update(
                {
                    "source_url": safe_provenance_url(context.url),
                    "suggested_base_url": suggested_base,
                }
            )
            attach_schema_http_validators(
                tool.metadata,
                validators,
                source_identity_digest=structured_source_identity_digest_for(
                    tool,
                    self.refresh,
                ),
            )
            return AdapterLoadResult(tool=tool, invoker=invoker)
        finally:
            if owns_client:
                await client.aclose()
