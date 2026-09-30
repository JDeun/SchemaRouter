from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from .._url_safety import safe_provenance_url
from ..errors import (
    InvocationUnavailableError,
    NonRetryableInvocationError,
    SchemaSourceError,
)
from ..models import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    ServerProjectionSpec,
    ToolCall,
    ToolSpec,
)
from .base import AdapterContext, AdapterLoadResult

_MAX_METADATA_BYTES = 5 * 1024 * 1024
_MAX_RESPONSE_BYTES = 16 * 1024 * 1024
_EDM_NS = "http://docs.oasis-open.org/odata/ns/edm"
_EDMX_NS = "http://docs.oasis-open.org/odata/ns/edmx"
_COLLECTION_RE = re.compile(r"^Collection\((.+)\)$")


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_.-").lower()
    return slug or "odata"


def _validate_base_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SchemaSourceError("OData service URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise SchemaSourceError("OData service URL must not contain credentials")
    if parsed.query or parsed.fragment:
        raise SchemaSourceError("OData service URL must not contain query or fragment")
    return url.rstrip("/")


def _service_and_metadata_urls(url: str) -> tuple[str, str]:
    value = _validate_base_url(url)
    if value.endswith("/$metadata"):
        return value[: -len("/$metadata")], value
    return value, value + "/$metadata"


async def _bounded_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None,
    max_bytes: int,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    async with client.stream(
        "GET",
        url,
        headers=headers,
        params=params,
        follow_redirects=False,
    ) as response:
        if response.is_redirect:
            raise SchemaSourceError("OData redirects are not followed automatically")
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > max_bytes:
                raise SchemaSourceError(
                    f"OData response exceeds {max_bytes} byte safety limit"
                )

        chunks: list[bytes] = []
        total = 0
        async for chunk in response.aiter_bytes():
            total += len(chunk)
            if total > max_bytes:
                raise SchemaSourceError(
                    f"OData response exceeds {max_bytes} byte safety limit"
                )
            chunks.append(chunk)

        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=b"".join(chunks),
            request=response.request,
        )


def _safe_xml_root(content: bytes) -> ET.Element:
    lowered = content.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise SchemaSourceError("OData metadata must not contain DTD/entity declarations")
    try:
        return ET.fromstring(content)
    except ET.ParseError as exc:
        raise SchemaSourceError("OData metadata is not valid XML") from exc


def _edm_schema(type_name: str, *, nullable: bool = True) -> dict[str, Any]:
    match = _COLLECTION_RE.match(type_name)
    if match:
        item_schema = _edm_schema(match.group(1), nullable=False)
        schema: dict[str, Any] = {"type": "array", "items": item_schema}
        return schema

    mapping: dict[str, dict[str, Any]] = {
        "Edm.String": {"type": "string"},
        "Edm.Boolean": {"type": "boolean"},
        "Edm.Byte": {"type": "integer"},
        "Edm.SByte": {"type": "integer"},
        "Edm.Int16": {"type": "integer"},
        "Edm.Int32": {"type": "integer"},
        "Edm.Int64": {"type": "integer"},
        "Edm.Decimal": {"type": "number"},
        "Edm.Double": {"type": "number"},
        "Edm.Single": {"type": "number"},
        "Edm.Guid": {"type": "string", "format": "uuid"},
        "Edm.Date": {"type": "string", "format": "date"},
        "Edm.DateTimeOffset": {"type": "string", "format": "date-time"},
        "Edm.Duration": {"type": "string"},
        "Edm.TimeOfDay": {"type": "string"},
        "Edm.Binary": {"type": "string"},
    }
    schema = deepcopy(mapping.get(type_name, {}))
    if nullable and isinstance(schema.get("type"), str):
        schema["type"] = [schema["type"], "null"]
    return schema


def _qualified_types(root: ET.Element) -> dict[str, ET.Element]:
    types: dict[str, ET.Element] = {}
    for schema in root.findall(f".//{{{_EDM_NS}}}Schema"):
        namespace = schema.get("Namespace")
        if not namespace:
            continue
        for tag in ("EntityType", "ComplexType"):
            for item in schema.findall(f"{{{_EDM_NS}}}{tag}"):
                name = item.get("Name")
                if name:
                    types[f"{namespace}.{name}"] = item
    return types


def _key_names(entity_type: ET.Element) -> set[str]:
    result: set[str] = set()
    key = entity_type.find(f"{{{_EDM_NS}}}Key")
    if key is None:
        return result
    for ref in key.findall(f"{{{_EDM_NS}}}PropertyRef"):
        name = ref.get("Name")
        if name:
            result.add(name)
    return result


def _property_unit(prop: ET.Element) -> str | None:
    for annotation in prop.findall(f"{{{_EDM_NS}}}Annotation"):
        term = annotation.get("Term")
        if term not in {
            "Org.OData.Measures.V1.Unit",
            "Org.OData.Measures.V1.ISOCurrency",
        }:
            continue
        value = annotation.get("String")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _property_description(prop: ET.Element) -> str:
    for annotation in prop.findall(f"{{{_EDM_NS}}}Annotation"):
        if annotation.get("Term") not in {
            "Org.OData.Core.V1.Description",
            "Org.OData.Core.V1.LongDescription",
        }:
            continue
        value = annotation.get("String")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _object_schema(
    type_name: str,
    types: dict[str, ET.Element],
    *,
    depth: int = 0,
    ancestors: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    if depth >= 8 or type_name in ancestors:
        return {"type": "object"}

    node = types.get(type_name)
    if node is None:
        return _edm_schema(type_name)

    properties: dict[str, Any] = {}
    required: list[str] = []
    for prop in node.findall(f"{{{_EDM_NS}}}Property"):
        name = prop.get("Name")
        prop_type = prop.get("Type")
        if not name or not prop_type:
            continue
        nullable = prop.get("Nullable", "true").lower() != "false"
        collection = _COLLECTION_RE.match(prop_type)
        inner_type = collection.group(1) if collection else prop_type
        if inner_type in types:
            child = _object_schema(
                inner_type,
                types,
                depth=depth + 1,
                ancestors=ancestors | {type_name},
            )
            schema = {"type": "array", "items": child} if collection else child
            if nullable and not collection and schema.get("type") == "object":
                schema = dict(schema)
                schema["type"] = ["object", "null"]
        else:
            schema = _edm_schema(prop_type, nullable=nullable)
        properties[name] = schema
        if not nullable:
            required.append(name)

    result: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": True,
    }
    if required:
        result["required"] = required
    return result


def _field_specs(
    entity_type_name: str,
    types: dict[str, ET.Element],
) -> tuple[list[FieldSpec], dict[str, str]]:
    entity_type = types[entity_type_name]
    keys = _key_names(entity_type)
    fields: list[FieldSpec] = []
    field_map: dict[str, str] = []

    def visit_type(
        type_name: str,
        *,
        prefix: tuple[str, ...],
        depth: int,
        ancestors: frozenset[str],
    ) -> None:
        if depth >= 8 or type_name in ancestors:
            return
        node = types.get(type_name)
        if node is None:
            return

        for prop in node.findall(f"{{{_EDM_NS}}}Property"):
            name = prop.get("Name")
            prop_type = prop.get("Type")
            if not name or not prop_type:
                continue

            path = (*prefix, name)
            field_name = ".".join(path)
            selector = "/".join(path)
            nullable = prop.get("Nullable", "true").lower() != "false"
            collection = _COLLECTION_RE.match(prop_type)
            inner_type = collection.group(1) if collection else prop_type

            if inner_type in types:
                child_schema = _object_schema(
                    inner_type,
                    types,
                    depth=depth + 1,
                    ancestors=ancestors | {type_name},
                )
                json_schema = (
                    {"type": "array", "items": child_schema}
                    if collection
                    else child_schema
                )
                if (
                    nullable
                    and not collection
                    and json_schema.get("type") == "object"
                ):
                    json_schema = dict(json_schema)
                    json_schema["type"] = ["object", "null"]
            else:
                json_schema = _edm_schema(prop_type, nullable=nullable)

            fields.append(
                FieldSpec(
                    name=field_name,
                    description=_property_description(prop),
                    json_schema=json_schema,
                    aliases=[name.replace("_", " ")],
                    path=list(path) if prefix else [],
                    result_path=[field_name] if prefix else [],
                    unit=_property_unit(prop),
                    identifier=name in keys and not prefix,
                    source_type="odata",
                )
            )
            field_map[field_name] = selector

            if inner_type in types and collection is None:
                visit_type(
                    inner_type,
                    prefix=path,
                    depth=depth + 1,
                    ancestors=ancestors | {type_name},
                )

    visit_type(
        entity_type_name,
        prefix=(),
        depth=0,
        ancestors=frozenset(),
    )
    return fields, field_map


def tool_from_odata_metadata(
    name: str,
    metadata_xml: bytes,
    *,
    namespace: str | None = None,
) -> ToolSpec:
    root = _safe_xml_root(metadata_xml)
    types = _qualified_types(root)
    if not types:
        raise SchemaSourceError("OData metadata declares no entity/complex types")

    endpoints: list[EndpointSpec] = []
    containers = root.findall(f".//{{{_EDM_NS}}}EntityContainer")
    for container in containers:
        for entity_set in container.findall(f"{{{_EDM_NS}}}EntitySet"):
            set_name = entity_set.get("Name")
            entity_type_name = entity_set.get("EntityType")
            if not set_name or not entity_type_name or entity_type_name not in types:
                continue

            fields, field_map = _field_specs(entity_type_name, types)
            item_schema = _object_schema(entity_type_name, types)
            endpoint_name = f"list_{_slug(set_name)}"
            endpoints.append(
                EndpointSpec(
                    name=endpoint_name,
                    description=f"Read OData entity set {set_name}.",
                    method="GET",
                    path=f"/{set_name}",
                    read_only=True,
                    destructive=False,
                    parameters=[
                        ParameterSpec(
                            name="filter",
                            wire_name="$filter",
                            location="query",
                            json_schema={"type": "string"},
                        ),
                        ParameterSpec(
                            name="orderby",
                            wire_name="$orderby",
                            location="query",
                            json_schema={"type": "string"},
                        ),
                        ParameterSpec(
                            name="top",
                            wire_name="$top",
                            location="query",
                            json_schema={"type": "integer", "minimum": 1},
                        ),
                        ParameterSpec(
                            name="skip",
                            wire_name="$skip",
                            location="query",
                            json_schema={"type": "integer", "minimum": 0},
                        ),
                    ],
                    output_fields=fields,
                    output_schema={"type": "array", "items": item_schema},
                    server_projection=ServerProjectionSpec(
                        parameter="$select",
                        field_map=field_map,
                    ),
                    execution_metadata={
                        "transport": "odata",
                        "entity_set": set_name,
                        "entity_type": entity_type_name,
                    },
                )
            )

    if not endpoints:
        raise SchemaSourceError("OData metadata declares no usable entity sets")

    return ToolSpec(
        name=name,
        namespace=namespace,
        description="OData service metadata surface",
        remote=True,
        source_type="odata",
        endpoints=endpoints,
        execution_metadata={"adapter": "odata"},
        metadata={"adapter": "odata", "remote": True},
    )


class ODataRemoteInvoker:
    """Call-aware OData reader with native $select projection."""

    projects_fields = True

    def __init__(
        self,
        tool: ToolSpec,
        service_url: str,
        *,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
        max_response_bytes: int = _MAX_RESPONSE_BYTES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.tool = tool
        self.service_url = _validate_base_url(service_url)
        self.trusted_headers = dict(trusted_headers or {})
        self.timeout = timeout
        self.max_response_bytes = max_response_bytes
        self.http_client = http_client

    async def invoke_call(self, call: ToolCall) -> Any:
        endpoint = self.tool.endpoint(call.endpoint)
        entity_set = endpoint.execution_metadata.get("entity_set")
        if not isinstance(entity_set, str) or not entity_set:
            raise NonRetryableInvocationError("OData endpoint is missing entity_set metadata")

        field_specs = {field.name: field for field in endpoint.output_fields}
        query: dict[str, str] = {}
        for parameter in endpoint.parameters:
            if parameter.name not in call.arguments:
                continue
            wire_name = parameter.wire_name or parameter.name
            query[wire_name] = str(call.arguments[parameter.name])

        if call.fields and endpoint.server_projection is not None:
            selectors = list(
                dict.fromkeys(
                    endpoint.server_projection.selector_for(field_specs[name])
                    for name in call.fields
                    if name in field_specs
                )
            )
            if selectors:
                query["$select"] = ",".join(selectors)

        url = f"{self.service_url}/{quote(entity_set, safe='')}"
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
                    max_bytes=self.max_response_bytes,
                    params=query,
                )
            except httpx.TimeoutException as exc:
                raise InvocationUnavailableError("OData request timed out") from exc
            except httpx.TransportError as exc:
                raise InvocationUnavailableError("OData transport failed") from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {408, 425, 429} or status >= 500:
                    raise InvocationUnavailableError(
                        f"OData transport temporarily unavailable: HTTP {status}"
                    ) from exc
                raise NonRetryableInvocationError(
                    f"OData request failed with HTTP {status}"
                ) from exc
            except SchemaSourceError as exc:
                raise NonRetryableInvocationError(str(exc)) from exc

            try:
                body = response.json()
            except json.JSONDecodeError as exc:
                raise NonRetryableInvocationError(
                    "OData response was not valid JSON"
                ) from exc
            if not isinstance(body, dict):
                raise NonRetryableInvocationError("OData response must be a JSON object")
            value = body.get("value")
            if not isinstance(value, list):
                raise NonRetryableInvocationError("OData collection response is missing value[]")
            return value
        finally:
            if owns_client:
                await client.aclose()


class ODataSourceAdapter:
    kind = "odata"
    priority = 85

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        if context.base_url is not None:
            raise SchemaSourceError(
                "base_url is not valid for OData; pass the service root or $metadata URL"
            )

        service_url, metadata_url = _service_and_metadata_urls(context.url)
        owns_client = context.http_client is None
        client = context.http_client or httpx.AsyncClient(
            timeout=context.timeout,
            follow_redirects=False,
        )
        try:
            try:
                response = await _bounded_get(
                    client,
                    metadata_url,
                    headers=context.schema_headers,
                    max_bytes=_MAX_METADATA_BYTES,
                )
            except SchemaSourceError:
                raise
            except Exception:  # noqa: BLE001
                return None

            try:
                tool = tool_from_odata_metadata(
                    context.name
                    or _slug(urlparse(service_url).hostname or "odata"),
                    response.content,
                    namespace=context.namespace,
                )
            except SchemaSourceError:
                raise
            except Exception:  # noqa: BLE001
                return None

            tool.execution_metadata.update(
                {
                    "execution_bound": True,
                    "approved_base_url": service_url,
                }
            )
            tool.metadata.update(
                {
                    "source_url": safe_provenance_url(metadata_url),
                    "service_url": safe_provenance_url(service_url),
                }
            )
            invoker = ODataRemoteInvoker(
                tool,
                service_url,
                trusted_headers=context.trusted_headers,
                timeout=context.timeout,
                http_client=context.http_client,
            )
            return AdapterLoadResult(tool=tool, invoker=invoker)
        finally:
            if owns_client:
                await client.aclose()
