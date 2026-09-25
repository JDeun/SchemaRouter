from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ..models import ToolSpec


@dataclass(frozen=True)
class AdapterContext:
    url: str
    name: str | None = None
    namespace: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    base_url: str | None = None
    schema_headers: dict[str, str] | None = None
    trusted_headers: dict[str, str] | None = None
    mcp_client_factory: Any | None = None
    openapi_external_refs: bool = False
    openapi_ref_max_depth: int = 3
    openapi_ref_max_documents: int = 8
    openapi_ref_max_bytes: int = 10 * 1024 * 1024
    timeout: float = 20.0
    http_client: httpx.AsyncClient | None = None


@dataclass(frozen=True)
class AdapterLoadResult:
    tool: ToolSpec
    invoker: Any | None = None


class SourceAdapter(Protocol):
    kind: str
    priority: int

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None: ...


class AdapterRegistry:
    """Ordered registry for structured capability-source adapters."""

    def __init__(self, adapters: list[SourceAdapter] | None = None) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: SourceAdapter, *, replace: bool = False) -> None:
        kind = str(adapter.kind).strip().lower()
        if not kind or kind == "auto":
            raise ValueError("adapter kind must be a non-empty name other than 'auto'")
        if kind in self._adapters and not replace:
            raise ValueError(f"adapter kind already registered: {kind!r}")
        self._adapters[kind] = adapter

    def unregister(self, kind: str) -> None:
        self._adapters.pop(kind.strip().lower(), None)

    def get(self, kind: str) -> SourceAdapter:
        normalized = kind.strip().lower()
        try:
            return self._adapters[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown adapter kind: {normalized!r}") from exc

    def kinds(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def ordered(self) -> tuple[SourceAdapter, ...]:
        return tuple(
            sorted(
                self._adapters.values(),
                key=lambda adapter: (-int(adapter.priority), str(adapter.kind)),
            )
        )
