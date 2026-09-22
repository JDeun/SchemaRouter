from __future__ import annotations

import re
from copy import deepcopy
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from ..errors import NonRetryableInvocationError, SchemaSourceError
from ..models import EndpointSpec, FieldSpec, ParameterSpec, ToolCall, ToolSpec
from .base import AdapterContext, AdapterLoadResult

_MAX_DISCOVERY_BYTES = 2 * 1024 * 1024
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_VERSION_SEGMENT = re.compile(r"^v\d+(?:\.\d+)?$")
_ENTRY_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
_TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_.-").lower()
    return slug or "optimade"


def _safe_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SchemaSourceError("OPTIMADE URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise SchemaSourceError("OPTIMADE URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise SchemaSourceError("OPTIMADE base URL must not contain query or fragment")
    return url.rstrip("/")


def _candidate_versioned_bases(url: str) -> tuple[str, ...]:
    base = _safe_base_url(url)
    leaf = urlparse(base).path.rstrip("/").rsplit("/", 1)[-1]
    if _VERSION_SEGMENT.fullmatch(leaf):
        return (base,)
    return (f"{base}/v1", base)


def _validate_entry_type(entry_type: str) -> str:
    parts = entry_type.split("/")
    if not parts or any(not part or not _ENTRY_SEGMENT.fullmatch(part) for part in parts):
        raise SchemaSourceError(f"unsafe OPTIMADE entry type: {entry_type!r}")
    return entry_type


async def _bounded_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None,
    params: dict[str, Any] | None = None,
    max_bytes: int,
    max_redirects: int = 5,
) -> httpx.Response:
    current = _safe_base_url(url)
    initial = urlparse(current)
    query_params = params

    for _ in range(max_redirects + 1):
        async with client.stream(
            "GET",
            current,
            headers=headers,
            params=query_params,
            follow_redirects=False,
        ) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SchemaSourceError("OPTIMADE redirect is missing Location")
                target = urljoin(current, location)
                parsed = urlparse(target)
                if (
                    parsed.scheme not in {"http", "https"}
                    or not parsed.netloc
                    or parsed.username
                    or parsed.password
                ):
                    raise SchemaSourceError("OPTIMADE redirect target is not a safe http(s) URL")
                if (
                    parsed.scheme.casefold() != initial.scheme.casefold()
                    or parsed.hostname != initial.hostname
                    or (parsed.port or (443 if parsed.scheme == "https" else 80))
                    != (initial.port or (443 if initial.scheme == "https" else 80))
                ):
                    raise SchemaSourceError(
                        "cross-origin OPTIMADE redirects are not allowed"
                    )
                current = target
                query_params = None
                continue

            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > max_bytes:
                    raise SchemaSourceError(
                        f"OPTIMADE response exceeds {max_bytes} byte safety limit"
                    )

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise SchemaSourceError(
                        f"OPTIMADE response exceeds {max_bytes} byte safety limit"
                    )
                chunks.append(chunk)

            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=b"".join(chunks),
                request=response.request,
            )

    raise SchemaSourceError("OPTIMADE URL exceeded the redirect limit")


def _base_info_attributes(document: Any) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None
    data = document.get("data")
    if not isinstance(data, dict) or data.get("type") != "info":
        return None
    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        return None
    if not isinstance(attributes.get("api_version"), str):
        return None
    if not isinstance(attributes.get("available_endpoints"), list):
        return None
    return attributes


def _entry_info_payload(document: Any, entry_type: str) -> dict[str, Any] | None:
    if not isinstance(document, dict):
        return None
    data = document.get("data")
    if not isinstance(data, dict):
        return None

    declared_type = data.get("type")
    declared_id = data.get("id")
    if declared_type is not None and declared_type != "info":
        return None
    if declared_id is not None and declared_id != entry_type:
        return None

    payload = dict(data)
    attributes = data.get("attributes")
    if isinstance(attributes, dict):
        payload.update(attributes)
    payload["_identity_inferred"] = declared_type is None or declared_id is None
    return payload


_OPTIMADE_TO_JSON_TYPE = {
    "string": "string",
    "integer": "integer",
    "float": "number",
    "boolean": "boolean",
    "timestamp": "string",
    "list": "array",
    "dictionary": "object",
    "number": "number",
    "array": "array",
    "object": "object",
    "null": "null",
}


def _normalize_optimade_schema(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_optimade_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    normalized = {
        key: _normalize_optimade_schema(item)
        for key, item in value.items()
        if key not in {"title", "description"}
    }
    raw_type = normalized.get("type")
    if isinstance(raw_type, str):
        mapped = _OPTIMADE_TO_JSON_TYPE.get(raw_type)
        if mapped is None:
            normalized.pop("type", None)
        else:
            normalized["type"] = mapped
            if raw_type == "timestamp":
                normalized.setdefault("format", "date-time")
    elif isinstance(raw_type, list):
        mapped_types = [
            _OPTIMADE_TO_JSON_TYPE[item]
            for item in raw_type
            if isinstance(item, str) and item in _OPTIMADE_TO_JSON_TYPE
        ]
        if mapped_types:
            normalized["type"] = list(dict.fromkeys(mapped_types))
            if "timestamp" in raw_type:
                normalized.setdefault("format", "date-time")
        else:
            normalized.pop("type", None)

    return normalized


def _property_schema(spec: dict[str, Any]) -> dict[str, Any]:
    return _normalize_optimade_schema(deepcopy(spec))


def _field_from_property(name: str, spec: dict[str, Any]) -> FieldSpec:
    description = str(spec.get("description") or spec.get("title") or "")
    unit = spec.get("x-optimade-unit") or spec.get("unit")
    return FieldSpec(
        name=name,
        description=description,
        json_schema=_property_schema(spec),
        aliases=[name.replace("_", " ")],
        unit=str(unit) if unit not in {None, "inapplicable"} else None,
        identifier=False,
        source_type="optimade",
    )


def _output_schema(fields: list[FieldSpec], *, many: bool) -> dict[str, Any]:
    properties = {field.name: deepcopy(field.json_schema) for field in fields}
    item = {
        "type": "object",
        "properties": properties,
        "required": ["id", "type"],
        "additionalProperties": True,
    }
    if many:
        return {"type": "array", "items": item}
    return item


def _search_parameters() -> list[ParameterSpec]:
    return [
        ParameterSpec(
            name="filter",
            description="OPTIMADE filter expression.",
            location="query",
            json_schema={"type": "string"},
            aliases=["where", "query filter"],
        ),
        ParameterSpec(
            name="page_limit",
            description="Maximum number of entries to return.",
            location="query",
            json_schema={"type": "integer", "minimum": 1},
            aliases=["limit", "top"],
        ),
        ParameterSpec(
            name="sort",
            description="Comma-delimited OPTIMADE sort expression.",
            location="query",
            json_schema={"type": "string"},
        ),
        ParameterSpec(
            name="include",
            description="Comma-delimited related resource types to include.",
            location="query",
            json_schema={"type": "string"},
        ),
        ParameterSpec(
            name="page_offset",
            description="Offset-based pagination value.",
            location="query",
            json_schema={"type": "integer", "minimum": 0},
        ),
        ParameterSpec(
            name="page_number",
            description="Page-number pagination value.",
            location="query",
            json_schema={"type": "integer", "minimum": 1},
        ),
        ParameterSpec(
            name="page_cursor",
            description="Cursor-based pagination value.",
            location="query",
            json_schema={"type": "string"},
        ),
        ParameterSpec(
            name="email_address",
            description="Optional contact email sent to the OPTIMADE provider.",
            location="query",
            json_schema={"type": "string"},
        ),
    ]


def _endpoint_token(entry_type: str) -> str:
    return _slug(entry_type.replace("/", "__"))


def _tool_from_discovery(
    *,
    name: str,
    namespace: str | None,
    versioned_base_url: str,
    base_info: dict[str, Any],
    entries: dict[str, dict[str, Any]],
    skipped: list[str],
) -> ToolSpec:
    endpoints: list[EndpointSpec] = []
    inferred_identity: list[str] = []
    for entry_type, info in entries.items():
        if bool(info.get("_identity_inferred")):
            inferred_identity.append(entry_type)
        properties = info.get("properties")
        if not isinstance(properties, dict):
            continue

        output_by_format = info.get("output_fields_by_format")
        json_fields: list[str]
        if isinstance(output_by_format, dict) and isinstance(output_by_format.get("json"), list):
            json_fields = [
                str(field)
                for field in output_by_format["json"]
                if isinstance(field, str)
            ]
        else:
            json_fields = [str(field) for field in properties]

        fields = [
            FieldSpec(
                name="id",
                description="OPTIMADE entry identifier.",
                json_schema={"type": "string"},
                aliases=["identifier", "entry id"],
                identifier=True,
                source_type="optimade",
            ),
            FieldSpec(
                name="type",
                description="OPTIMADE entry type.",
                json_schema={"type": "string"},
                aliases=["entry type"],
                source_type="optimade",
            ),
        ]
        seen = {"id", "type"}
        for field_name in json_fields:
            if field_name in seen:
                continue
            raw_spec = properties.get(field_name)
            if not isinstance(raw_spec, dict):
                continue
            fields.append(_field_from_property(field_name, raw_spec))
            seen.add(field_name)

        token = _endpoint_token(entry_type)
        description = str(info.get("description") or f"OPTIMADE {entry_type} entries")
        safe_entry_type = _validate_entry_type(entry_type)
        endpoints.extend(
            [
                EndpointSpec(
                    name=f"search_{token}",
                    description=f"Search {description}",
                    parameters=_search_parameters(),
                    output_fields=fields,
                    output_schema=_output_schema(fields, many=True),
                    method="GET",
                    path=f"/{safe_entry_type}",
                    read_only=True,
                    destructive=False,
                    metadata={
                        "entry_type": entry_type,
                        "mode": "search",
                        "field_projection": "response_fields",
                    },
                ),
                EndpointSpec(
                    name=f"get_{token}",
                    description=f"Get one {description}",
                    parameters=[
                        ParameterSpec(
                            name="id",
                            description="OPTIMADE entry identifier.",
                            required=True,
                            location="path",
                            json_schema={"type": "string", "minLength": 1},
                            aliases=["identifier", "entry id"],
                        )
                    ],
                    output_fields=fields,
                    output_schema=_output_schema(fields, many=False),
                    method="GET",
                    path=f"/{safe_entry_type}/{{id}}",
                    read_only=True,
                    destructive=False,
                    metadata={
                        "entry_type": entry_type,
                        "mode": "get",
                        "field_projection": "response_fields",
                    },
                ),
            ]
        )

    if not endpoints:
        detail = ", ".join(skipped) if skipped else "no entry types were discovered"
        raise SchemaSourceError(
            "OPTIMADE source exposed no usable entry schemas: " + detail
        )

    return ToolSpec(
        name=name,
        namespace=namespace,
        description="OPTIMADE interoperable materials database",
        endpoints=endpoints,
        source_type="optimade",
        metadata={
            "adapter": "optimade",
            "remote": True,
            "api_version": base_info.get("api_version"),
            "versioned_base_url": versioned_base_url,
            "is_index": bool(base_info.get("is_index", False)),
            "skipped_entry_types": skipped,
            "inferred_entry_info_identity": inferred_identity,
        },
    )


class OPTIMADESourceAdapter:
    kind = "optimade"
    priority = 90

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        candidates = _candidate_versioned_bases(context.base_url or context.url)

        owns_client = context.http_client is None
        client = context.http_client or httpx.AsyncClient(
            timeout=context.timeout,
            follow_redirects=False,
        )
        try:
            versioned_base_url: str | None = None
            base_info: dict[str, Any] | None = None
            for candidate in candidates:
                try:
                    response = await _bounded_get(
                        client,
                        f"{candidate}/info",
                        headers=context.schema_headers,
                        max_bytes=_MAX_DISCOVERY_BYTES,
                    )
                    document = response.json()
                except SchemaSourceError:
                    raise
                except Exception:  # noqa: BLE001
                    continue
                attributes = _base_info_attributes(document)
                if attributes is not None:
                    versioned_base_url = candidate
                    base_info = attributes
                    break

            if versioned_base_url is None or base_info is None:
                return None

            if bool(base_info.get("is_index", False)):
                raise SchemaSourceError(
                    "OPTIMADE index meta-databases are discovery catalogs, not executable "
                    "entry databases; provide a concrete provider database URL"
                )

            entry_types_by_format = base_info.get("entry_types_by_format")
            if (
                isinstance(entry_types_by_format, dict)
                and isinstance(entry_types_by_format.get("json"), list)
            ):
                entry_types = [
                    str(value)
                    for value in entry_types_by_format["json"]
                    if isinstance(value, str)
                ]
            else:
                entry_types = [
                    str(value)
                    for value in base_info.get("available_endpoints", [])
                    if isinstance(value, str) and value not in {"info", "links"}
                ]

            entry_types = list(dict.fromkeys(entry_types))[:32]
            entries: dict[str, dict[str, Any]] = {}
            skipped: list[str] = []
            for entry_type in entry_types:
                try:
                    safe_entry_type = _validate_entry_type(entry_type)
                except SchemaSourceError as exc:
                    skipped.append(f"{entry_type}:{type(exc).__name__}")
                    continue
                try:
                    response = await _bounded_get(
                        client,
                        f"{versioned_base_url}/info/{safe_entry_type}",
                        headers=context.schema_headers,
                        max_bytes=_MAX_DISCOVERY_BYTES,
                    )
                    payload = _entry_info_payload(response.json(), entry_type)
                except SchemaSourceError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    skipped.append(f"{entry_type}:{type(exc).__name__}")
                    continue
                if payload is None or not isinstance(payload.get("properties"), dict):
                    skipped.append(f"{entry_type}:invalid_info")
                    continue
                entries[entry_type] = payload

            parsed = urlparse(versioned_base_url)
            inferred_name = context.name or _slug(parsed.hostname or "optimade")
            tool = _tool_from_discovery(
                name=inferred_name,
                namespace=context.namespace,
                versioned_base_url=versioned_base_url,
                base_info=base_info,
                entries=entries,
                skipped=skipped,
            )
            invoker = OPTIMADERemoteInvoker(
                tool,
                versioned_base_url,
                trusted_headers=context.trusted_headers,
                timeout=context.timeout,
                http_client=context.http_client,
            )
            return AdapterLoadResult(tool=tool, invoker=invoker)
        finally:
            if owns_client:
                await client.aclose()


class OPTIMADERemoteInvoker:
    """Call-aware OPTIMADE invoker that maps planned fields to response_fields."""

    projects_fields = True

    def __init__(
        self,
        tool: ToolSpec,
        versioned_base_url: str,
        *,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.tool = tool
        self.base_url = _safe_base_url(versioned_base_url)
        self.trusted_headers = dict(trusted_headers or {})
        self.timeout = timeout
        self.http_client = http_client

    async def invoke_call(self, call: ToolCall) -> Any:
        endpoint = self.tool.endpoint(call.endpoint)
        entry_type = _validate_entry_type(str(endpoint.metadata["entry_type"]))
        mode = str(endpoint.metadata["mode"])

        arguments = dict(call.arguments)
        query = {
            key: value
            for key, value in arguments.items()
            if key != "id"
        }
        selected_fields = [
            field
            for field in call.fields
            if field not in {"id", "type"}
        ]
        if selected_fields:
            query["response_fields"] = ",".join(selected_fields)
        if mode == "search":
            query.setdefault("page_limit", 20)
            url = f"{self.base_url}/{entry_type}"
        elif mode == "get":
            entry_id = arguments.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                raise RuntimeError("OPTIMADE get endpoint requires a non-empty id")
            url = f"{self.base_url}/{entry_type}/{quote(entry_id, safe='')}"
        else:
            raise NonRetryableInvocationError(
                f"unknown OPTIMADE endpoint mode: {mode!r}"
            )

        owns_client = self.http_client is None
        client = self.http_client or httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,
        )
        try:
            try:
                response = await _bounded_get(
                    client,
                    url,
                    headers=self.trusted_headers,
                    params=query or None,
                    max_bytes=_MAX_RESPONSE_BYTES,
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in _TRANSIENT_HTTP_STATUS_CODES:
                    raise NonRetryableInvocationError(
                        "OPTIMADE request failed with non-retryable HTTP status "
                        f"{exc.response.status_code}"
                    ) from exc
                raise
            except SchemaSourceError as exc:
                raise NonRetryableInvocationError(
                    "OPTIMADE runtime response violated the transport safety contract"
                ) from exc

            try:
                payload = response.json()
            except ValueError as exc:
                raise NonRetryableInvocationError(
                    "OPTIMADE response could not be decoded as JSON"
                ) from exc
        finally:
            if owns_client:
                await client.aclose()

        data = payload.get("data") if isinstance(payload, dict) else None
        if mode == "search":
            if not isinstance(data, list):
                raise NonRetryableInvocationError(
                    "OPTIMADE listing response must contain a data list"
                )
            return [
                self._flatten_entry(item, call.fields)
                for item in data
            ]

        if not isinstance(data, dict):
            raise NonRetryableInvocationError(
                "OPTIMADE single-entry response must contain a data object"
            )
        return self._flatten_entry(data, call.fields)

    @staticmethod
    def _flatten_entry(item: Any, fields: list[str]) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise NonRetryableInvocationError("OPTIMADE entry must be an object")
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            attributes = {}

        value: dict[str, Any] = {
            "id": item.get("id"),
            "type": item.get("type"),
            **attributes,
        }
        requested = set(fields)
        missing = sorted(
            field
            for field in requested
            if field not in value
        )
        if missing:
            raise NonRetryableInvocationError(
                "OPTIMADE provider omitted requested response fields: "
                + ", ".join(missing)
            )
        if not requested:
            return value

        keep = requested | {"id", "type"}
        return {key: value[key] for key in value if key in keep}
