from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

from ..errors import SchemaSourceError
from ..models import ToolSpec


ProbeFailureCategory = Literal[
    "authentication_failed",
    "invalid_schema",
    "not_found",
    "protocol_error",
    "unreachable",
    "unsupported_feature",
]


class AdapterProbeError(SchemaSourceError):
    """Sanitized, typed structured-source discovery failure."""

    def __init__(
        self,
        category: ProbeFailureCategory,
        message: str,
    ) -> None:
        super().__init__(message)
        self.category = category


def adapter_probe_error(
    adapter_kind: str,
    exc: BaseException,
) -> AdapterProbeError:
    """Classify a discovery exception without copying remote payloads or secrets."""

    if isinstance(exc, AdapterProbeError):
        return exc
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401, 403}:
            return AdapterProbeError(
                "authentication_failed",
                f"{adapter_kind} discovery was denied by the remote server (HTTP {status})",
            )
        if status == 404:
            return AdapterProbeError(
                "not_found",
                f"{adapter_kind} discovery endpoint was not found (HTTP 404)",
            )
        return AdapterProbeError(
            "protocol_error",
            f"{adapter_kind} discovery returned HTTP {status}",
        )
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return AdapterProbeError(
            "unreachable",
            f"{adapter_kind} discovery could not reach the remote source",
        )
    if isinstance(exc, SchemaSourceError):
        return AdapterProbeError(
            "invalid_schema",
            f"{adapter_kind} discovery rejected the structured source",
        )
    return AdapterProbeError(
        "protocol_error",
        f"{adapter_kind} discovery failed during protocol inspection",
    )


@dataclass(frozen=True)
class AdapterContext:
    url: str
    name: str | None = None
    namespace: str | None = None
    provider: str | None = None
    access_mode: str | None = None
    base_url: str | None = None
    schema_headers: dict[str, str] | None = None
    schema_validators: dict[str, str] | None = None
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


@dataclass(frozen=True)
class DiscoveryProfile:
    """Trusted local declaration of one adapter's discovery-side effects."""

    activity: Literal["passive", "active"] = "active"
    http_methods: tuple[str, ...] = ()
    derives_urls: bool = False
    opens_protocol_session: bool = False

    def __post_init__(self) -> None:
        if self.activity not in {"passive", "active"}:
            raise ValueError("discovery activity must be 'passive' or 'active'")
        methods = tuple(str(method).strip().upper() for method in self.http_methods)
        if any(not method for method in methods):
            raise ValueError("discovery HTTP methods must be non-empty")
        if self.activity == "passive":
            if any(method not in {"GET", "HEAD"} for method in methods):
                raise ValueError(
                    "passive discovery may declare only GET/HEAD HTTP methods"
                )
            if self.opens_protocol_session:
                raise ValueError(
                    "passive discovery cannot open a protocol session"
                )
        object.__setattr__(self, "http_methods", methods)


class SourceAdapter(Protocol):
    kind: str
    priority: int
    discovery: DiscoveryProfile

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None: ...


class AdapterRegistry:
    """Ordered registry for structured capability-source adapters."""

    def __init__(self, adapters: list[SourceAdapter] | None = None) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        self._discovery_profiles: dict[str, DiscoveryProfile] = {}
        for adapter in adapters or []:
            self.register(adapter)

    def register(self, adapter: SourceAdapter, *, replace: bool = False) -> None:
        kind = str(adapter.kind).strip().lower()
        if not kind or kind == "auto":
            raise ValueError("adapter kind must be a non-empty name other than 'auto'")
        if kind in self._adapters and not replace:
            raise ValueError(f"adapter kind already registered: {kind!r}")
        profile = getattr(adapter, "discovery", None)
        if profile is None:
            # Backward-compatible plugin registration is fail-safe for auto mode:
            # adapters without a trusted local profile are treated as active.
            profile = DiscoveryProfile(activity="active")
        if not isinstance(profile, DiscoveryProfile):
            raise ValueError(
                "adapter discovery must be a DiscoveryProfile declared by trusted local code"
            )
        self._adapters[kind] = adapter
        self._discovery_profiles[kind] = profile

    def unregister(self, kind: str) -> None:
        normalized = kind.strip().lower()
        self._adapters.pop(normalized, None)
        self._discovery_profiles.pop(normalized, None)

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


    def discovery_profile(self, kind: str) -> DiscoveryProfile:
        normalized = kind.strip().lower()
        try:
            return self._discovery_profiles[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown adapter kind: {normalized!r}") from exc

    def auto_candidates(
        self,
        *,
        allow_active_probes: bool = False,
    ) -> tuple[SourceAdapter, ...]:
        """Return adapters eligible for generic auto discovery."""

        return tuple(
            adapter
            for adapter in self.ordered()
            if (
                self.discovery_profile(str(adapter.kind)).activity == "passive"
                or allow_active_probes
            )
        )

    def skipped_active_kinds(self) -> tuple[str, ...]:
        return tuple(
            str(adapter.kind)
            for adapter in self.ordered()
            if self.discovery_profile(str(adapter.kind)).activity == "active"
        )
