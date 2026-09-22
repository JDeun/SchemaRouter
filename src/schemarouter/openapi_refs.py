from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Awaitable, Callable
from urllib.parse import unquote, urldefrag, urljoin, urlparse

from .adapters.base import OpenAPIRefPolicy
from .adapters.openapi import same_origin
from .errors import SchemaSourceError

_EXTERNAL_COMPONENT_KEY = "x-schemarouter-external-documents"

OpenAPIRefFetcher = Callable[[str], Awaitable[tuple[str, Any, int]]]


@dataclass(frozen=True)
class OpenAPIRefResolutionStats:
    resolved_refs: int = 0
    documents: int = 0
    bytes_loaded: int = 0
    cycles: int = 0


class _Resolver:
    def __init__(
        self,
        *,
        root_url: str,
        policy: OpenAPIRefPolicy,
        fetcher: OpenAPIRefFetcher,
    ) -> None:
        self.root_resource = urldefrag(root_url)[0]
        self.policy = policy
        self.fetcher = fetcher
        self.documents: dict[str, str] = {}
        self.aliases: dict[str, str] = {}
        self.processing: set[str] = set()
        self.embedded: dict[str, Any] = {}
        self.resolved_refs = 0
        self.bytes_loaded = 0
        self.cycles = 0

    @staticmethod
    def _validate_resource_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SchemaSourceError(
                "external OpenAPI $ref must resolve to an absolute http(s) URL"
            )
        if parsed.username or parsed.password:
            raise SchemaSourceError(
                "external OpenAPI $ref URLs must not contain credentials"
            )

    @staticmethod
    def _fragment(ref: str) -> str:
        fragment = unquote(urldefrag(ref)[1])
        if fragment and not fragment.startswith("/"):
            raise SchemaSourceError(
                "external OpenAPI $ref fragments must use JSON Pointer syntax"
            )
        return fragment

    @staticmethod
    def _document_id(resource: str) -> str:
        return sha256(resource.encode("utf-8")).hexdigest()[:20]

    @staticmethod
    def _prefix(document_id: str) -> str:
        return (
            "#/components/"
            + _EXTERNAL_COMPONENT_KEY
            + "/"
            + document_id
        )

    def _canonical_known_resource(self, resource: str) -> str:
        return self.aliases.get(resource, resource)

    async def _load_document(self, resource: str, *, depth: int) -> tuple[str, str]:
        if depth > self.policy.max_depth:
            raise SchemaSourceError(
                "external OpenAPI $ref exceeded the configured depth limit"
            )

        self._validate_resource_url(resource)
        if not same_origin(self.root_resource, resource):
            raise SchemaSourceError(
                "cross-origin external OpenAPI $ref is not allowed"
            )

        known_resource = self._canonical_known_resource(resource)
        existing_id = self.documents.get(known_resource)
        if existing_id is not None:
            if known_resource in self.processing:
                self.cycles += 1
            return known_resource, existing_id

        if len(self.documents) >= self.policy.max_documents:
            raise SchemaSourceError(
                "external OpenAPI $ref exceeded the configured document limit"
            )

        final_url, raw_document, size = await self.fetcher(resource)
        final_resource = urldefrag(final_url)[0]
        self._validate_resource_url(final_resource)
        if not same_origin(self.root_resource, final_resource):
            raise SchemaSourceError(
                "external OpenAPI $ref redirect crossed the root schema origin"
            )

        self.aliases[resource] = final_resource
        existing_id = self.documents.get(final_resource)
        if existing_id is not None:
            return final_resource, existing_id

        self.bytes_loaded += size
        if self.bytes_loaded > self.policy.max_bytes:
            raise SchemaSourceError(
                "external OpenAPI $ref exceeded the configured byte limit"
            )

        document_id = self._document_id(final_resource)
        self.documents[final_resource] = document_id
        self.embedded[document_id] = deepcopy(raw_document)
        self.processing.add(final_resource)
        try:
            self.embedded[document_id] = await self._rewrite(
                self.embedded[document_id],
                current_resource=final_resource,
                current_prefix=self._prefix(document_id),
                depth=depth,
            )
        finally:
            self.processing.discard(final_resource)

        return final_resource, document_id

    async def _rewrite_ref(
        self,
        ref: str,
        *,
        current_resource: str,
        current_prefix: str,
        depth: int,
    ) -> str:
        absolute = urljoin(current_resource, ref)
        resource, _ = urldefrag(absolute)
        fragment = self._fragment(absolute)

        if resource == current_resource:
            if current_prefix == "#":
                return "#" + fragment
            return current_prefix + fragment

        if resource == self.root_resource:
            return "#" + fragment

        self._validate_resource_url(resource)
        if not same_origin(self.root_resource, resource):
            raise SchemaSourceError(
                "cross-origin external OpenAPI $ref is not allowed"
            )

        _, document_id = await self._load_document(
            resource,
            depth=depth + 1,
        )
        self.resolved_refs += 1
        return self._prefix(document_id) + fragment

    async def _rewrite(
        self,
        value: Any,
        *,
        current_resource: str,
        current_prefix: str,
        depth: int,
    ) -> Any:
        if isinstance(value, list):
            return [
                await self._rewrite(
                    item,
                    current_resource=current_resource,
                    current_prefix=current_prefix,
                    depth=depth,
                )
                for item in value
            ]

        if not isinstance(value, dict):
            return value

        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                result[key] = await self._rewrite_ref(
                    item,
                    current_resource=current_resource,
                    current_prefix=current_prefix,
                    depth=depth,
                )
                continue
            result[key] = await self._rewrite(
                item,
                current_resource=current_resource,
                current_prefix=current_prefix,
                depth=depth,
            )
        return result

    async def resolve(
        self,
        document: dict[str, Any],
    ) -> tuple[dict[str, Any], OpenAPIRefResolutionStats]:
        resolved = deepcopy(document)
        components = resolved.setdefault("components", {})
        if not isinstance(components, dict):
            raise SchemaSourceError("OpenAPI components must be an object")

        if _EXTERNAL_COMPONENT_KEY in components:
            raise SchemaSourceError(
                f"OpenAPI components reserves {_EXTERNAL_COMPONENT_KEY!r} "
                "when external ref resolution is enabled"
            )

        components[_EXTERNAL_COMPONENT_KEY] = self.embedded
        resolved = await self._rewrite(
            resolved,
            current_resource=self.root_resource,
            current_prefix="#",
            depth=0,
        )

        components = resolved.get("components")
        if isinstance(components, dict):
            external = components.get(_EXTERNAL_COMPONENT_KEY)
            if isinstance(external, dict) and not external:
                components.pop(_EXTERNAL_COMPONENT_KEY, None)

        return resolved, OpenAPIRefResolutionStats(
            resolved_refs=self.resolved_refs,
            documents=len(self.documents),
            bytes_loaded=self.bytes_loaded,
            cycles=self.cycles,
        )


async def resolve_external_openapi_refs(
    document: dict[str, Any],
    *,
    source_url: str,
    policy: OpenAPIRefPolicy,
    fetcher: OpenAPIRefFetcher,
) -> tuple[dict[str, Any], OpenAPIRefResolutionStats]:
    if not policy.enabled:
        return deepcopy(document), OpenAPIRefResolutionStats()

    resolver = _Resolver(
        root_url=source_url,
        policy=policy,
        fetcher=fetcher,
    )
    return await resolver.resolve(document)
