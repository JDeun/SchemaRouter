from __future__ import annotations

from .provider_profiles import (
    ProviderDiscoveryBackend,
    ProviderDiscoveryCandidate,
    ProviderDiscoveryProposal,
    ProviderProfile,
    ProviderProfileRegistry,
    ProviderResolution,
    built_in_provider_profile_registry,
    load_provider_profile_plugins,
)


class ProviderProfileService:
    """Own provider identity, discovery, approval, and plugin lifecycle."""

    def __init__(
        self,
        registry: ProviderProfileRegistry | None = None,
    ) -> None:
        self.registry = (
            registry
            if registry is not None
            else built_in_provider_profile_registry()
        )

    def register(
        self,
        profile: ProviderProfile,
        *,
        replace: bool = False,
    ) -> str:
        return self.registry.register(profile, replace=replace)

    def resolve(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> ProviderResolution:
        return self.registry.resolve(provider, methods=methods)

    def discover(
        self,
        provider: str,
        *,
        backend: ProviderDiscoveryBackend | None = None,
        limit: int = 8,
    ) -> ProviderDiscoveryProposal:
        external = tuple(backend(provider)) if backend is not None else ()
        return self.registry.discover(
            provider,
            external_candidates=external,
            limit=limit,
        )

    def approve(
        self,
        candidate: ProviderDiscoveryCandidate,
        *,
        expected_digest: str,
        replace: bool = False,
    ) -> str:
        return self.registry.approve_discovery_candidate(
            candidate,
            expected_digest=expected_digest,
            replace=replace,
        )

    def load_plugins(
        self,
        *,
        allowlist: set[str] | list[str] | tuple[str, ...],
        replace: bool = False,
    ) -> tuple[str, ...]:
        return load_provider_profile_plugins(
            self.registry,
            allowlist=allowlist,
            replace=replace,
        )
