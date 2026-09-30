from __future__ import annotations

from copy import deepcopy
from urllib.parse import urlparse

import httpx

from ..errors import RegistrationError
from ..models import EndpointSpec, ToolSpec
from .openapi import OpenAPIRemoteInvoker


_SUPPORTED_PARAMETER_LOCATIONS = {
    "path",
    "query",
    "header",
    "body",
    "body_root",
}


class HTTPJSONRemoteInvoker(OpenAPIRemoteInvoker):
    """Trusted HTTP/JSON executor for locally declared ToolSpec contracts."""

    protocol_label = "HTTP JSON"


def prepare_http_json_tool(
    tool: ToolSpec,
    *,
    base_url: str,
    provider: str | None = None,
    access_mode: str | None = None,
) -> ToolSpec:
    """Stamp one trusted local ToolSpec as a remote declarative HTTP/JSON capability."""

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RegistrationError("base_url must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise RegistrationError("base_url must not contain credentials")
    if parsed.query or parsed.fragment:
        raise RegistrationError("base_url must not contain query or fragment")

    endpoints: list[EndpointSpec] = []
    for endpoint in tool.endpoints:
        if endpoint.method is None or endpoint.path is None:
            raise RegistrationError(
                f"HTTP JSON endpoint {endpoint.name!r} requires method and path"
            )
        unsupported = sorted(
            {
                parameter.location
                for parameter in endpoint.parameters
                if parameter.location not in _SUPPORTED_PARAMETER_LOCATIONS
            }
        )
        if unsupported:
            raise RegistrationError(
                "HTTP JSON endpoint "
                f"{endpoint.name!r} uses unsupported parameter locations: "
                + ", ".join(unsupported)
            )

        payload = endpoint.model_dump(mode="python")
        execution_metadata = dict(payload.get("execution_metadata") or {})
        execution_metadata.update(
            {
                "transport": "http_json",
            }
        )
        payload["execution_metadata"] = execution_metadata
        endpoints.append(EndpointSpec.model_validate(payload))

    payload = tool.model_dump(mode="python")
    payload["endpoints"] = endpoints
    payload["remote"] = True
    payload["provider"] = provider if provider is not None else tool.provider
    payload["access_mode"] = (
        access_mode
        if access_mode is not None
        else tool.access_mode or "http_json"
    )
    execution_metadata = dict(payload.get("execution_metadata") or {})
    execution_metadata.update(
        {
            "adapter": "http_json",
            "approved_base_url": base_url.rstrip("/"),
        }
    )
    payload["execution_metadata"] = execution_metadata
    metadata = deepcopy(payload.get("metadata") or {})
    metadata.update(
        {
            "adapter": "http_json",
            "approved_base_url": base_url.rstrip("/"),
        }
    )
    payload["metadata"] = metadata
    return ToolSpec.model_validate(payload)


def build_http_json_invoker(
    tool: ToolSpec,
    *,
    base_url: str,
    trusted_headers: dict[str, str] | None = None,
    timeout: float = 20.0,
    max_response_bytes: int = 10 * 1024 * 1024,
    http_client: httpx.AsyncClient | None = None,
) -> HTTPJSONRemoteInvoker:
    """Build the trusted transport binding for a prepared declarative HTTP tool."""

    return HTTPJSONRemoteInvoker(
        tool,
        base_url,
        trusted_headers=trusted_headers,
        timeout=timeout,
        max_response_bytes=max_response_bytes,
        http_client=http_client,
    )
