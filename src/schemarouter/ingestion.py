from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urldefrag, urljoin, urlparse

import httpx
import yaml

from .adapters.base import AdapterContext, AdapterLoadResult, AdapterRegistry, SourceAdapter
from .adapters.mcp import MCPRemoteInvoker, inspect_mcp_url
from .adapters.openapi import (
    OpenAPIRemoteInvoker,
    normalize_same_document_refs,
    resolve_openapi_base_url,
    same_origin,
    tool_from_openapi,
)
from .adapters.optimade import OPTIMADESourceAdapter
from .errors import SchemaSourceError, UnsupportedSchemaSourceError
from .executor import RegistryExecutor
from .models import ToolSpec
from .registry import ToolRegistry

SourceKind = str

_MAX_SCHEMA_BYTES = 5 * 1024 * 1024
_DEFAULT_OPENAPI_REF_MAX_DEPTH = 3
_DEFAULT_OPENAPI_REF_MAX_DOCUMENTS = 8
_DEFAULT_OPENAPI_REF_MAX_BYTES = 10 * 1024 * 1024
_OPENAPI_EXTERNAL_REFS_KEY = "x-schemarouter-external-refs"


class _OpenAPIYAMLLoader(yaml.SafeLoader):
    """Safe YAML loader that keeps timestamp-looking scalars JSON-compatible strings."""


_OpenAPIYAMLLoader.yaml_implicit_resolvers = {
    key: [
        resolver
        for resolver in resolvers
        if resolver[0] != "tag:yaml.org,2002:timestamp"
    ]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _safe_yaml_load(text: str) -> Any:
    return yaml.load(text, Loader=_OpenAPIYAMLLoader)


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


def _parse_openapi_text(text: str) -> dict[str, Any] | None:
    value: object
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            value = _safe_yaml_load(text)
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


async def _fetch_with_safe_redirects(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None,
    max_redirects: int = 5,
    max_bytes: int = _MAX_SCHEMA_BYTES,
) -> httpx.Response:
    current = url
    initial = url
    for _ in range(max_redirects + 1):
        async with client.stream(
            "GET",
            current,
            headers=headers,
            follow_redirects=False,
        ) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise SchemaSourceError("schema redirect response is missing Location")
                target = urljoin(current, location)
                _validate_url(target)
                if not same_origin(initial, target):
                    raise SchemaSourceError("cross-origin schema redirects are not allowed")
                current = target
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
                        f"schema document exceeds {max_bytes} byte safety limit"
                    )

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise SchemaSourceError(
                        f"schema document exceeds {max_bytes} byte safety limit"
                    )
                chunks.append(chunk)

            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=b"".join(chunks),
                request=response.request,
            )

    raise SchemaSourceError("schema URL exceeded the redirect limit")


def _parse_reference_text(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        try:
            value = _safe_yaml_load(text)
        except yaml.YAMLError:
            return None
    if isinstance(value, dict):
        return value
    return None


def _contains_schema_id(value: Any) -> bool:
    if isinstance(value, dict):
        if "$id" in value:
            return True
        return any(_contains_schema_id(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_schema_id(item) for item in value)
    return False


def _contains_dynamic_schema_reference(value: Any) -> bool:
    if isinstance(value, dict):
        if any(
            key in value
            for key in ("$dynamicRef", "$dynamicAnchor", "$recursiveRef", "$recursiveAnchor")
        ):
            return True
        return any(
            _contains_dynamic_schema_reference(item)
            for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_dynamic_schema_reference(item) for item in value)
    return False


def _contains_external_ref(value: Any) -> bool:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            return True
        return any(_contains_external_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_external_ref(item) for item in value)
    return False


def _contains_schema_ref(value: Any) -> bool:
    if isinstance(value, dict):
        if isinstance(value.get("$ref"), str):
            return True
        return any(_contains_schema_ref(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_schema_ref(item) for item in value)
    return False


_STATIC_ANCHOR_RE = re.compile(r"^[A-Za-z][A-Za-z0-9._:-]*$")


@dataclass(frozen=True)
class _SchemaResourceLocation:
    document_key: str | None
    path: tuple[str, ...]


class _OpenAPIRefBundler:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        root_url: str,
        headers: dict[str, str] | None,
        max_depth: int,
        max_documents: int,
        max_bytes: int,
    ) -> None:
        self.client = client
        self.root_url = urldefrag(root_url)[0]
        self.headers = headers
        self.max_depth = max_depth
        self.max_documents = max_documents
        self.max_bytes = max_bytes
        self.total_bytes = 0
        self.documents: dict[str, str] = {}
        self.bundle: dict[str, Any] = {}
        self.root_document: dict[str, Any] | None = None
        self.resources: dict[str, _SchemaResourceLocation] = {}
        self.anchors: dict[tuple[str, str], _SchemaResourceLocation] = {}
        self.same_document_refs_normalized = 0
        self.schema_ids_indexed = 0
        self.anchors_indexed = 0

    async def resolve(self, document: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
        if _contains_dynamic_schema_reference(document):
            raise SchemaSourceError(
                "bounded external OpenAPI refs do not support dynamic or recursive schema refs"
            )
        if not _contains_schema_ref(document):
            return deepcopy(document), {
                "documents": 0,
                "bytes": 0,
                "same_document_refs": 0,
                "schema_ids": 0,
                "anchors": 0,
            }
        if _OPENAPI_EXTERNAL_REFS_KEY in document:
            raise SchemaSourceError(
                "OpenAPI document uses the reserved external-ref bundle key"
            )

        resolved = deepcopy(document)
        self.root_document = resolved
        root_location = _SchemaResourceLocation(document_key=None, path=())
        self._register_resource(self.root_url, root_location)
        self._index_node(
            resolved,
            base_url=self.root_url,
            document_key=None,
            path=(),
        )
        await self._rewrite(
            resolved,
            base_url=self.root_url,
            depth=0,
        )

        self._strip_resolution_keywords(resolved)
        for bundled in self.bundle.values():
            self._strip_resolution_keywords(bundled)
        if self.bundle:
            resolved[_OPENAPI_EXTERNAL_REFS_KEY] = deepcopy(self.bundle)

        return resolved, {
            "documents": len(self.bundle),
            "bytes": self.total_bytes,
            "same_document_refs": self.same_document_refs_normalized,
            "schema_ids": self.schema_ids_indexed,
            "anchors": self.anchors_indexed,
        }

    def _schema_base_uri(self, base_url: str, schema_id: Any) -> str:
        if not isinstance(schema_id, str) or not schema_id.strip():
            raise SchemaSourceError("JSON Schema $id must be a non-empty URI string")

        absolute = urljoin(base_url, schema_id)
        resource_url, fragment = urldefrag(absolute)
        if fragment:
            raise SchemaSourceError(
                "bounded external OpenAPI refs do not support $id values with fragments"
            )
        _validate_url(resource_url)
        if not same_origin(self.root_url, resource_url):
            raise SchemaSourceError(
                "cross-origin JSON Schema $id base URIs are not allowed"
            )
        return resource_url

    def _register_resource(
        self,
        resource_url: str,
        location: _SchemaResourceLocation,
    ) -> None:
        existing = self.resources.get(resource_url)
        if existing is not None and existing != location:
            raise SchemaSourceError(
                f"duplicate JSON Schema resource URI: {resource_url}"
            )
        self.resources[resource_url] = location

    def _register_anchor(
        self,
        resource_url: str,
        anchor: Any,
        location: _SchemaResourceLocation,
    ) -> None:
        if not isinstance(anchor, str) or not _STATIC_ANCHOR_RE.fullmatch(anchor):
            raise SchemaSourceError("JSON Schema $anchor has an invalid name")
        key = (resource_url, anchor)
        existing = self.anchors.get(key)
        if existing is not None and existing != location:
            raise SchemaSourceError(
                f"duplicate JSON Schema $anchor {anchor!r} for {resource_url}"
            )
        self.anchors[key] = location

    def _index_node(
        self,
        value: Any,
        *,
        base_url: str,
        document_key: str | None,
        path: tuple[str, ...],
    ) -> None:
        if isinstance(value, list):
            for index, item in enumerate(value):
                self._index_node(
                    item,
                    base_url=base_url,
                    document_key=document_key,
                    path=(*path, str(index)),
                )
            return
        if not isinstance(value, dict):
            return

        location = _SchemaResourceLocation(document_key=document_key, path=path)
        effective_base = base_url
        if "$id" in value:
            effective_base = self._schema_base_uri(base_url, value["$id"])
            self._register_resource(effective_base, location)
            self.schema_ids_indexed += 1

        if "$anchor" in value:
            self._register_anchor(effective_base, value["$anchor"], location)
            self.anchors_indexed += 1

        for key, item in value.items():
            self._index_node(
                item,
                base_url=effective_base,
                document_key=document_key,
                path=(*path, str(key)),
            )

    def _document_root(self, document_key: str | None) -> Any:
        if document_key is None:
            if self.root_document is None:
                raise SchemaSourceError("OpenAPI reference resolver has no root document")
            return self.root_document
        return self.bundle[document_key]

    @staticmethod
    def _decode_pointer(fragment: str) -> list[str]:
        if not fragment:
            return []
        if not fragment.startswith("/"):
            raise SchemaSourceError("JSON Schema reference is not a JSON Pointer")
        return [
            part.replace("~1", "/").replace("~0", "~")
            for part in fragment[1:].split("/")
        ]

    def _pointer_location(
        self,
        resource: _SchemaResourceLocation,
        fragment: str,
    ) -> _SchemaResourceLocation:
        parts = self._decode_pointer(fragment)
        node = self._document_root(resource.document_key)
        for part in resource.path:
            if isinstance(node, dict):
                if part not in node:
                    raise SchemaSourceError("JSON Schema resource path is invalid")
                node = node[part]
            elif isinstance(node, list) and part.isdigit():
                index = int(part)
                if index >= len(node):
                    raise SchemaSourceError("JSON Schema resource path is invalid")
                node = node[index]
            else:
                raise SchemaSourceError("JSON Schema resource path is invalid")

        resolved_path = list(resource.path)
        for part in parts:
            if isinstance(node, dict):
                if part not in node:
                    raise SchemaSourceError("JSON Schema $ref pointer target does not exist")
                node = node[part]
            elif isinstance(node, list) and part.isdigit():
                index = int(part)
                if index >= len(node):
                    raise SchemaSourceError("JSON Schema $ref pointer target does not exist")
                node = node[index]
            else:
                raise SchemaSourceError("JSON Schema $ref pointer target does not exist")
            resolved_path.append(part)

        return _SchemaResourceLocation(
            document_key=resource.document_key,
            path=tuple(resolved_path),
        )

    def _resolve_fragment(
        self,
        resource_url: str,
        fragment: str,
    ) -> _SchemaResourceLocation:
        resource = self.resources.get(resource_url)
        if resource is None:
            raise SchemaSourceError(
                f"JSON Schema resource URI was not indexed: {resource_url}"
            )

        decoded = unquote(fragment)
        if not decoded:
            return resource
        if decoded.startswith("/"):
            return self._pointer_location(resource, decoded)

        anchor = self.anchors.get((resource_url, decoded))
        if anchor is None:
            raise SchemaSourceError(
                f"JSON Schema $anchor {decoded!r} was not found for {resource_url}"
            )
        return anchor

    @staticmethod
    def _pointer_ref(location: _SchemaResourceLocation) -> str:
        parts: list[str] = []
        if location.document_key is not None:
            parts.extend((_OPENAPI_EXTERNAL_REFS_KEY, location.document_key))
        parts.extend(location.path)
        if not parts:
            return "#"
        encoded = [
            part.replace("~", "~0").replace("/", "~1")
            for part in parts
        ]
        return "#/" + "/".join(encoded)

    async def _rewrite(
        self,
        value: Any,
        *,
        base_url: str,
        depth: int,
    ) -> None:
        if isinstance(value, list):
            for item in value:
                await self._rewrite(
                    item,
                    base_url=base_url,
                    depth=depth,
                )
            return
        if not isinstance(value, dict):
            return

        effective_base = base_url
        if "$id" in value:
            effective_base = self._schema_base_uri(base_url, value["$id"])

        ref = value.get("$ref")
        if isinstance(ref, str):
            absolute = urljoin(effective_base, ref)
            resource_url, fragment = urldefrag(absolute)
            _validate_url(resource_url)
            if not same_origin(self.root_url, resource_url):
                raise SchemaSourceError(
                    "cross-origin external OpenAPI $ref targets are not allowed"
                )

            if resource_url not in self.resources:
                if depth + 1 > self.max_depth:
                    raise SchemaSourceError(
                        "external OpenAPI $ref exceeded the configured depth limit"
                    )
                await self._load_document(
                    resource_url,
                    depth=depth + 1,
                )

            location = self._resolve_fragment(resource_url, fragment)
            if not ref.startswith("#") and location.document_key is None:
                self.same_document_refs_normalized += 1
            value["$ref"] = self._pointer_ref(location)

        for item in list(value.values()):
            await self._rewrite(
                item,
                base_url=effective_base,
                depth=depth,
            )

    async def _load_document(self, resource_url: str, *, depth: int) -> str:
        cached = self.documents.get(resource_url)
        if cached is not None:
            return cached
        if len(self.bundle) >= self.max_documents:
            raise SchemaSourceError(
                "external OpenAPI $ref exceeded the configured document limit"
            )

        remaining = self.max_bytes - self.total_bytes
        if remaining <= 0:
            raise SchemaSourceError(
                "external OpenAPI $ref exceeded the configured byte budget"
            )
        response = await _fetch_with_safe_redirects(
            self.client,
            resource_url,
            headers=self.headers,
            max_bytes=min(_MAX_SCHEMA_BYTES, remaining),
        )
        body = response.content
        self.total_bytes += len(body)
        if self.total_bytes > self.max_bytes:
            raise SchemaSourceError(
                "external OpenAPI $ref exceeded the configured byte budget"
            )

        final_url = urldefrag(str(response.url))[0]
        existing = self.documents.get(final_url)
        if existing is not None:
            self.documents[resource_url] = existing
            location = self.resources.get(final_url)
            if location is None:
                raise SchemaSourceError("cached schema document is missing its resource index")
            self._register_resource(resource_url, location)
            return existing

        parsed = _parse_reference_text(response.text)
        if parsed is None:
            raise SchemaSourceError(
                "external OpenAPI $ref target is not structured JSON/YAML"
            )
        if _contains_dynamic_schema_reference(parsed):
            raise SchemaSourceError(
                "bounded external OpenAPI refs do not support dynamic or recursive schema refs"
            )

        document_key = f"doc{len(self.bundle)}"
        self.documents[resource_url] = document_key
        self.documents[final_url] = document_key
        self.bundle[document_key] = deepcopy(parsed)

        location = _SchemaResourceLocation(document_key=document_key, path=())
        self._register_resource(resource_url, location)
        self._register_resource(final_url, location)
        self._index_node(
            self.bundle[document_key],
            base_url=final_url,
            document_key=document_key,
            path=(),
        )

        await self._rewrite(
            self.bundle[document_key],
            base_url=final_url,
            depth=depth,
        )
        return document_key

    @classmethod
    def _strip_resolution_keywords(cls, value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                cls._strip_resolution_keywords(item)
            return
        if not isinstance(value, dict):
            return
        value.pop("$id", None)
        value.pop("$anchor", None)
        for item in value.values():
            cls._strip_resolution_keywords(item)


class OpenAPISourceAdapter:
    kind = "openapi"
    priority = 100

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        owns_client = context.http_client is None
        client = context.http_client or httpx.AsyncClient(
            timeout=context.timeout,
            follow_redirects=False,
        )
        ref_stats = {
            "documents": 0,
            "bytes": 0,
            "same_document_refs": 0,
            "schema_ids": 0,
            "anchors": 0,
        }
        resolved_schema_url = context.url
        normalized_ref_count = 0
        try:
            response = await _fetch_with_safe_redirects(
                client,
                context.url,
                headers=context.schema_headers,
            )
            document = _parse_openapi_text(response.text)
            if document is not None:
                resolved_schema_url = str(response.url)
                if context.openapi_external_refs:
                    bundler = _OpenAPIRefBundler(
                        client,
                        root_url=resolved_schema_url,
                        headers=context.schema_headers,
                        max_depth=context.openapi_ref_max_depth,
                        max_documents=context.openapi_ref_max_documents,
                        max_bytes=context.openapi_ref_max_bytes,
                    )
                    document, ref_stats = await bundler.resolve(document)
                    normalized_ref_count = ref_stats["same_document_refs"]
                else:
                    document, normalized_ref_count = normalize_same_document_refs(
                        document,
                        resolved_schema_url,
                    )
        except SchemaSourceError:
            raise
        except Exception:  # noqa: BLE001
            return None
        finally:
            if owns_client:
                await client.aclose()

        if document is None:
            return None

        inferred_name = context.name or _slug(
            str((document.get("info") or {}).get("title") or _name_from_url(context.url))
        )
        tool = tool_from_openapi(inferred_name, document, namespace=context.namespace)
        try:
            suggested_base_url = resolve_openapi_base_url(document, resolved_schema_url)
        except ValueError as exc:
            if context.base_url is None:
                raise SchemaSourceError(
                    "OpenAPI document declared an unsafe or unsupported server URL"
                ) from exc
            suggested_base_url = None

        tool.execution_metadata.update(
            {
                "adapter": "openapi",
                "source_url": context.url,
                "resolved_schema_url": resolved_schema_url,
                "suggested_base_url": suggested_base_url,
            }
        )
        tool.metadata.update(
            {
                "source_url": context.url,
                "resolved_schema_url": resolved_schema_url,
                "suggested_base_url": suggested_base_url,
                "same_document_refs_normalized": normalized_ref_count,
                "external_refs_enabled": context.openapi_external_refs,
                "external_ref_documents_resolved": ref_stats["documents"],
                "external_ref_bytes_fetched": ref_stats["bytes"],
                "external_ref_schema_ids_resolved": ref_stats["schema_ids"],
                "external_ref_anchors_resolved": ref_stats["anchors"],
                "external_ref_limits": {
                    "max_depth": context.openapi_ref_max_depth,
                    "max_documents": context.openapi_ref_max_documents,
                    "max_bytes": context.openapi_ref_max_bytes,
                },
                "remote": True,
            }
        )

        selected_base_url = context.base_url or suggested_base_url
        auto_bind_allowed = context.base_url is not None or (
            suggested_base_url is not None
            and same_origin(suggested_base_url, resolved_schema_url)
        )
        invoker = None
        if auto_bind_allowed:
            if selected_base_url is None:
                raise SchemaSourceError("no approved OpenAPI base URL is available")
            try:
                invoker = OpenAPIRemoteInvoker(
                    tool,
                    selected_base_url,
                    trusted_headers=context.trusted_headers,
                    timeout=context.timeout,
                )
            except ValueError as exc:
                raise SchemaSourceError(
                    "OpenAPI execution base URL or trusted headers are invalid"
                ) from exc

        if invoker is not None:
            tool.execution_metadata.update(
                {
                    "execution_bound": True,
                    "approved_base_url": selected_base_url,
                    "requires_explicit_base_url": False,
                }
            )
            tool.metadata.update(
                {
                    "execution_bound": True,
                    "approved_base_url": selected_base_url,
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
                    "execution_bound": False,
                    "requires_explicit_base_url": True,
                }
            )

        return AdapterLoadResult(tool=tool, invoker=invoker)


class MCPSourceAdapter:
    kind = "mcp"
    priority = 80

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        if context.base_url is not None:
            raise SchemaSourceError("base_url is not valid for MCP sources")
        try:
            tool = await inspect_mcp_url(
                context.url,
                server_name=context.name,
                namespace=context.namespace,
                trusted_headers=context.trusted_headers,
                timeout=context.timeout,
                client_factory=context.mcp_client_factory,
            )
        except Exception:  # noqa: BLE001
            return None

        tool.remote = True
        tool.metadata["remote"] = True
        return AdapterLoadResult(
            tool=tool,
            invoker=MCPRemoteInvoker(
                context.url,
                trusted_headers=context.trusted_headers,
                timeout=context.timeout,
                client_factory=context.mcp_client_factory,
            ),
        )


def default_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry(
        [
            OpenAPISourceAdapter(),
            OPTIMADESourceAdapter(),
            MCPSourceAdapter(),
        ]
    )


class URLSchemaLoader:
    """Resolve structured URL sources through a pluggable adapter registry."""

    def __init__(
        self,
        registry: ToolRegistry,
        executor: RegistryExecutor,
        *,
        http_client: httpx.AsyncClient | None = None,
        adapters: AdapterRegistry | None = None,
    ) -> None:
        self.registry = registry
        self.executor = executor
        self.http_client = http_client
        self.adapters = adapters if adapters is not None else default_adapter_registry()

    def register_adapter(self, adapter: SourceAdapter, *, replace: bool = False) -> None:
        self.adapters.register(adapter, replace=replace)

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
        mcp_client_factory: Any | None = None,
        openapi_external_refs: bool = False,
        openapi_ref_max_depth: int = _DEFAULT_OPENAPI_REF_MAX_DEPTH,
        openapi_ref_max_documents: int = _DEFAULT_OPENAPI_REF_MAX_DOCUMENTS,
        openapi_ref_max_bytes: int = _DEFAULT_OPENAPI_REF_MAX_BYTES,
        timeout: float = 20.0,
    ) -> ToolSpec:
        _validate_url(url)
        if not isinstance(openapi_external_refs, bool):
            raise SchemaSourceError("openapi_external_refs must be a boolean")
        for value, label in (
            (openapi_ref_max_depth, "openapi_ref_max_depth"),
            (openapi_ref_max_documents, "openapi_ref_max_documents"),
            (openapi_ref_max_bytes, "openapi_ref_max_bytes"),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise SchemaSourceError(f"{label} must be a positive integer")

        normalized_kind = kind.strip().lower()
        context = AdapterContext(
            url=url,
            name=name,
            namespace=namespace,
            base_url=base_url,
            schema_headers=schema_headers,
            trusted_headers=trusted_headers,
            mcp_client_factory=mcp_client_factory,
            openapi_external_refs=openapi_external_refs,
            openapi_ref_max_depth=openapi_ref_max_depth,
            openapi_ref_max_documents=openapi_ref_max_documents,
            openapi_ref_max_bytes=openapi_ref_max_bytes,
            timeout=timeout,
            http_client=self.http_client,
        )

        diagnostics: list[str] = []
        if normalized_kind != "auto":
            try:
                adapter = self.adapters.get(normalized_kind)
            except KeyError as exc:
                supported = ", ".join(self.adapters.kinds())
                raise SchemaSourceError(
                    f"unsupported source kind {kind!r}; registered kinds: {supported}"
                ) from exc

            try:
                result = await adapter.load(context)
            except SchemaSourceError as exc:
                if normalized_kind == "openapi":
                    raise UnsupportedSchemaSourceError(
                        f"URL did not yield a supported OpenAPI source: {exc}"
                    ) from exc
                raise
            except Exception as exc:  # noqa: BLE001
                raise SchemaSourceError(
                    f"{normalized_kind} adapter failed for {url!r}"
                ) from exc
            if result is None:
                raise UnsupportedSchemaSourceError(
                    f"URL did not yield a supported {normalized_kind} source"
                )
            return self._commit(result, replace=replace)

        for adapter in self.adapters.ordered():
            try:
                result = await adapter.load(context)
            except Exception as exc:  # noqa: BLE001
                diagnostics.append(f"{adapter.kind}: {exc}")
                continue
            if result is not None:
                return self._commit(result, replace=replace)

        detail = "; ".join(diagnostics) or "no registered adapter recognized the source"
        raise UnsupportedSchemaSourceError(
            "URL was not recognized by any registered structured-source adapter. "
            "Human-readable documentation is intentionally not inferred in the safe path. "
            + detail
        )

    def _commit(self, result: AdapterLoadResult, *, replace: bool) -> ToolSpec:
        key = self.registry.register(result.tool, replace=replace)
        if result.invoker is not None:
            self.executor.bind(key, result.invoker)
        return self.registry.get(key)
