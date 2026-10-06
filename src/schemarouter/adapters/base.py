from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

import httpx

from .._http_headers import validate_trusted_headers
from ..models import ToolSpec
from ..network_policy import TRUSTED_INTERNAL_NETWORK_POLICY, NetworkPolicy


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
    mcp_discovery_limits: Any | None = None
    openapi_external_refs: bool = False
    openapi_ref_max_depth: int = 3
    openapi_ref_max_documents: int = 8
    openapi_ref_max_bytes: int = 10 * 1024 * 1024
    timeout: float = 20.0
    http_client: httpx.AsyncClient | None = None
    network_policy: NetworkPolicy = TRUSTED_INTERNAL_NETWORK_POLICY

    def __post_init__(self) -> None:
        if self.schema_headers is not None:
            object.__setattr__(
                self,
                "schema_headers",
                validate_trusted_headers(
                    self.schema_headers,
                    label="schema_headers",
                ),
            )
        if self.trusted_headers is not None:
            object.__setattr__(
                self,
                "trusted_headers",
                validate_trusted_headers(
                    self.trusted_headers,
                    label="trusted_headers",
                ),
            )


ProbeOutcome = Literal[
    "recognized",
    "not_recognized",
    "unreachable",
    "authentication_failed",
    "not_found",
    "invalid_schema",
    "unsupported_feature",
    "protocol_error",
]


@dataclass(frozen=True)
class AdapterProbeDiagnostic:
    """Credential-free outcome from one structured-source adapter probe."""

    adapter_kind: str
    activity: Literal["passive", "active"]
    outcome: ProbeOutcome
    error_type: str | None = None


@dataclass(frozen=True)
class AdapterLoadResult:
    tool: ToolSpec
    invoker: Any | None = None
    probe_diagnostics: tuple[AdapterProbeDiagnostic, ...] = ()


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


@dataclass(frozen=True)
class RefreshProfile:
    """Trusted local declaration of one adapter's schema-lifecycle support."""

    mode: Literal["unsupported", "url", "url_or_bound_mcp"] = "unsupported"
    source_key: str | None = None
    source_location: Literal["metadata", "execution_metadata", "either"] = "metadata"
    http_validators: bool = False
    identity_metadata_keys: tuple[str, ...] = ()
    identity_execution_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.mode not in {"unsupported", "url", "url_or_bound_mcp"}:
            raise ValueError("unsupported refresh mode")
        if self.source_location not in {
            "metadata",
            "execution_metadata",
            "either",
        }:
            raise ValueError(
                "refresh source_location must be metadata, execution_metadata, or either"
            )
        if self.mode == "url" and not self.source_key:
            raise ValueError("URL refresh requires a source_key")
        if self.source_key is not None and (
            not self.source_key or self.source_key != self.source_key.strip()
        ):
            raise ValueError("refresh source_key must be non-empty and trimmed")
        if self.http_validators and self.mode != "url":
            raise ValueError("HTTP validators require URL refresh mode")
        for key in (*self.identity_metadata_keys, *self.identity_execution_keys):
            if not key or key != key.strip():
                raise ValueError("refresh identity keys must be non-empty and trimmed")
            normalized = key.casefold().replace("-", "_")
            if any(
                marker in normalized
                for marker in (
                    "authorization",
                    "credential",
                    "password",
                    "secret",
                    "token",
                    "cookie",
                    "api_key",
                    "apikey",
                )
            ):
                raise ValueError(
                    "refresh identity keys must never name credential-bearing fields"
                )
        if len(self.identity_metadata_keys) != len(set(self.identity_metadata_keys)):
            raise ValueError("refresh identity metadata keys must be unique")
        if len(self.identity_execution_keys) != len(set(self.identity_execution_keys)):
            raise ValueError("refresh identity execution keys must be unique")

    @property
    def supported(self) -> bool:
        return self.mode != "unsupported"

    def source_url(self, tool: ToolSpec) -> str | None:
        if self.source_key is None:
            return None
        sources: tuple[dict[str, Any], ...]
        if self.source_location == "metadata":
            sources = (tool.metadata,)
        elif self.source_location == "execution_metadata":
            sources = (tool.execution_metadata,)
        else:
            sources = (tool.execution_metadata, tool.metadata)
        for source in sources:
            value = source.get(self.source_key)
            if isinstance(value, str) and value:
                return value
        return None


class SourceAdapter(Protocol):
    kind: str
    priority: int
    discovery: DiscoveryProfile
    refresh: RefreshProfile

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None: ...


class AdapterRegistry:
    """Ordered registry for structured capability-source adapters."""

    def __init__(self, adapters: list[SourceAdapter] | None = None) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        self._discovery_profiles: dict[str, DiscoveryProfile] = {}
        self._refresh_profiles: dict[str, RefreshProfile] = {}
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
        refresh = getattr(adapter, "refresh", None)
        if refresh is None:
            # Legacy plugins remain ingestible, but refresh/watch is opt-in only.
            refresh = RefreshProfile()
        if not isinstance(refresh, RefreshProfile):
            raise ValueError(
                "adapter refresh must be a RefreshProfile declared by trusted local code"
            )
        self._adapters[kind] = adapter
        self._discovery_profiles[kind] = profile
        self._refresh_profiles[kind] = refresh

    def unregister(self, kind: str) -> None:
        normalized = kind.strip().lower()
        self._adapters.pop(normalized, None)
        self._discovery_profiles.pop(normalized, None)
        self._refresh_profiles.pop(normalized, None)

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

    def refresh_profile(self, kind: str) -> RefreshProfile:
        normalized = kind.strip().lower()
        try:
            return self._refresh_profiles[normalized]
        except KeyError as exc:
            raise KeyError(f"unknown adapter kind: {normalized!r}") from exc

    def is_refreshable(self, kind: str) -> bool:
        try:
            return self.refresh_profile(kind).supported
        except KeyError:
            return False

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
