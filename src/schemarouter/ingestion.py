from __future__ import annotations

import json
import re
from typing import Literal
from urllib.parse import urlparse

import httpx
import yaml

from .adapters.mcp import MCPRemoteInvoker, inspect_mcp_url
from .adapters.openapi import (
    OpenAPIRemoteInvoker,
    resolve_openapi_base_url,
    same_origin,
    tool_from_openapi,
)
from .errors import SchemaSourceError, UnsupportedSchemaSourceError
from .executor import RegistryExecutor
from .models import ToolSpec
from .registry import InMemoryRegistry

SourceKind = Literal["auto", "openapi", "mcp"]


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("_.-").lower()
    return slug or "remote_tool"


def _name_from_url(url: str) -> str:
    parsed = urlparse(url)
    leaf = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if leaf and "." in leaf:
        leaf = leaf.rsplit(".", 1)[0]
    return _slug(leaf or parsed.hostname or "remote_tool")


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SchemaSourceError("schema URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise SchemaSourceError("schema URL must not contain credentials")


def _parse_openapi_text(text: str) -> dict | None:
    value: object
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            value = yaml.safe_load(text)
        except yaml.YAMLError:
            return None

    if not isinstance(value, dict):
        return None
    version = value.get("openapi")
    if not isinstance(version, str) or not version.startswith("3."):
        return None
    if not isinstance(value.get("paths"), dict):
        return None
    return value


class URLSchemaLoader:
    """Turn a structured URL source into a registered and, when possible, bound tool."""

    def __init__(
        self,
        registry: InMemoryRegistry,
        executor: RegistryExecutor,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.registry = registry
        self.executor = executor
        self.http_client = http_client

    async def load(
        self,
        url: str,
        *,
        kind: SourceKind = "auto",
        name: str | None = None,
        namespace: str | None = None,
        replace: bool = False,
        base_url: str | None = None,
        schema_headers: dict[str, str] | None = None,
        trusted_headers: dict[str, str] | None = None,
        timeout: float = 20.0,
    ) -> ToolSpec:
        _validate_url(url)
        if kind not in {"auto", "openapi", "mcp"}:
            raise SchemaSourceError(f"unsupported source kind: {kind!r}")
        if kind == "mcp" and base_url is not None:
            raise SchemaSourceError("base_url is only valid for OpenAPI sources")

        diagnostics: list[str] = []

        if kind in {"auto", "openapi"}:
            try:
                document, resolved_schema_url = await self._fetch_openapi(
                    url,
                    headers=schema_headers,
                    timeout=timeout,
                )
            except Exception as exc:  # noqa: BLE001
                diagnostics.append(f"OpenAPI: {exc}")
                document = None
                resolved_schema_url = url

            if document is not None:
                inferred_name = name or _slug(
                    str((document.get("info") or {}).get("title") or _name_from_url(url))
                )
                tool = tool_from_openapi(inferred_name, document, namespace=namespace)
                suggested_base_url = resolve_openapi_base_url(
                    document,
                    resolved_schema_url,
                )
                tool.metadata.update(
                    {
                        "source_url": url,
                        "resolved_schema_url": resolved_schema_url,
                        "suggested_base_url": suggested_base_url,
                    }
                )

                key = self.registry.register(tool, replace=replace)
                selected_base_url = base_url or suggested_base_url
                auto_bind_allowed = base_url is not None or same_origin(
                    suggested_base_url,
                    resolved_schema_url,
                )
                if auto_bind_allowed:
                    self.executor.bind(
                        key,
                        OpenAPIRemoteInvoker(
                            tool,
                            selected_base_url,
                            trusted_headers=trusted_headers,
                            timeout=timeout,
                        ),
                    )
                    tool.metadata.update(
                        {
                            "execution_bound": True,
                            "approved_base_url": selected_base_url,
                        }
                    )
                else:
                    tool.metadata.update(
                        {
                            "execution_bound": False,
                            "requires_explicit_base_url": True,
                        }
                    )
                return tool

            if kind == "openapi":
                detail = "; ".join(diagnostics) or "document is not OpenAPI 3.x"
                raise UnsupportedSchemaSourceError(
                    f"URL did not yield a supported OpenAPI document: {detail}"
                )

        if kind in {"auto", "mcp"}:
            if trusted_headers:
                diagnostics.append(
                    "MCP: custom trusted headers are not wired in v0.1; use an unauthenticated "
                    "endpoint or explicit transport integration"
                )
            else:
                try:
                    tool = await inspect_mcp_url(
                        url,
                        server_name=name,
                        namespace=namespace,
                    )
                    key = self.registry.register(tool, replace=replace)
                    self.executor.bind(key, MCPRemoteInvoker(url))
                    return tool
                except Exception as exc:  # noqa: BLE001
                    diagnostics.append(f"MCP: {exc}")

            if kind == "mcp":
                raise SchemaSourceError("; ".join(diagnostics))

        detail = "; ".join(diagnostics) or "no supported structured schema detected"
        raise UnsupportedSchemaSourceError(
            "URL is neither a supported OpenAPI 3.x document nor a reachable MCP server. "
            "General HTML documentation is intentionally not inferred in the safe path. "
            + detail
        )

    async def _fetch_openapi(
        self,
        url: str,
        *,
        headers: dict[str, str] | None,
        timeout: float,
    ) -> tuple[dict | None, str]:
        if self.http_client is not None:
            response = await self.http_client.get(url, headers=headers)
        else:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, headers=headers)
        response.raise_for_status()
        return _parse_openapi_text(response.text), str(response.url)
