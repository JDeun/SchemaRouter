from __future__ import annotations

import importlib.util
from collections.abc import Collection, Iterable
from importlib import metadata
from typing import Any, Literal

from pydantic import Field, model_validator

from .models import StrictModel

PROVIDER_PROFILE_ENTRY_POINT_GROUP = "schemarouter.providers"

ProviderMethodResolutionStatus = Literal[
    "available",
    "dependency_missing",
    "manual_binding_required",
    "disabled",
]
ProviderMethodRegistrationStatus = Literal[
    "registered",
    "auth_required",
    "dependency_missing",
    "manual_binding_required",
    "disabled",
    "unavailable",
]


def _normalize_provider_name(value: str) -> str:
    normalized = "-".join(value.strip().lower().replace("_", "-").split())
    if not normalized:
        raise ValueError("provider identifier must be non-empty")
    return normalized


class ProviderAccessMethod(StrictModel):
    """Declarative description of one known way to reach a provider."""

    method_id: str
    kind: str
    access_mode: str
    url: str | None = None
    optional_dependency: str | None = None
    credential_names: tuple[str, ...] = ()
    enabled_by_default: bool = True
    auto_register: bool = True
    description: str = ""

    @model_validator(mode="after")
    def validate_method(self) -> ProviderAccessMethod:
        if not self.method_id.strip():
            raise ValueError("provider access method_id must be non-empty")
        if not self.kind.strip():
            raise ValueError("provider access method kind must be non-empty")
        if not self.access_mode.strip():
            raise ValueError("provider access method access_mode must be non-empty")
        if self.auto_register and self.url is None:
            raise ValueError("auto-registerable provider methods require a URL")
        if self.optional_dependency is not None and not self.optional_dependency.strip():
            raise ValueError("optional_dependency must be non-empty when supplied")
        if any(not name.strip() for name in self.credential_names):
            raise ValueError("credential names must be non-empty")
        return self


class ProviderProfile(StrictModel):
    """Provider-level identity resolved into existing SchemaRouter ingestion methods."""

    provider_id: str
    display_name: str
    aliases: tuple[str, ...] = ()
    profile_version: str = "1"
    profile_source: str = "builtin"
    homepage: str | None = None
    methods: tuple[ProviderAccessMethod, ...] = ()

    @model_validator(mode="after")
    def validate_profile(self) -> ProviderProfile:
        canonical = _normalize_provider_name(self.provider_id)
        method_ids = [method.method_id for method in self.methods]
        if len(method_ids) != len(set(method_ids)):
            raise ValueError("provider access method IDs must be unique")
        names = [canonical, *(_normalize_provider_name(alias) for alias in self.aliases)]
        if len(names) != len(set(names)):
            raise ValueError("provider ID and aliases must be unique within a profile")
        if not self.display_name.strip():
            raise ValueError("provider display_name must be non-empty")
        return self


class ProviderMethodResolution(StrictModel):
    method_id: str
    kind: str
    access_mode: str
    status: ProviderMethodResolutionStatus
    url: str | None = None
    credential_names: tuple[str, ...] = ()
    optional_dependency: str | None = None
    detail: str = ""


class ProviderResolution(StrictModel):
    requested_provider: str
    provider_id: str
    display_name: str
    profile_version: str
    profile_source: str
    methods: tuple[ProviderMethodResolution, ...] = ()


class ProviderMethodRegistration(StrictModel):
    method_id: str
    kind: str
    access_mode: str
    status: ProviderMethodRegistrationStatus
    tool_key: str | None = None
    error_type: str | None = None
    detail: str = ""


class ProviderRegistrationResult(StrictModel):
    provider_id: str
    registered_tool_keys: tuple[str, ...] = ()
    methods: tuple[ProviderMethodRegistration, ...] = ()


class ProviderProfileRegistry:
    """Deterministic provider/alias resolver.

    Profiles are convenience metadata only. They never contain credentials or executable
    Python objects and they compile into the existing source-adapter/binding surfaces.
    """

    def __init__(self) -> None:
        self._profiles: dict[str, ProviderProfile] = {}
        self._aliases: dict[str, str] = {}

    def register(self, profile: ProviderProfile, *, replace: bool = False) -> str:
        canonical = _normalize_provider_name(profile.provider_id)
        aliases = {
            _normalize_provider_name(alias)
            for alias in profile.aliases
        }
        aliases.add(canonical)

        collision_ids = {
            self._aliases[name]
            for name in aliases
            if name in self._aliases and self._aliases[name] != canonical
        }
        if collision_ids:
            raise ValueError(
                "provider aliases collide with existing profile(s): "
                + ", ".join(sorted(collision_ids))
            )

        if canonical in self._profiles and not replace:
            raise ValueError(f"provider profile {canonical!r} is already registered")

        if replace and canonical in self._profiles:
            previous = self._profiles[canonical]
            for name in {
                _normalize_provider_name(previous.provider_id),
                *(_normalize_provider_name(alias) for alias in previous.aliases),
            }:
                if self._aliases.get(name) == canonical:
                    self._aliases.pop(name, None)

        self._profiles[canonical] = profile.model_copy(deep=True)
        for name in aliases:
            self._aliases[name] = canonical
        return canonical

    def get(self, identifier: str) -> ProviderProfile:
        normalized = _normalize_provider_name(identifier)
        canonical = self._aliases.get(normalized)
        if canonical is None:
            raise KeyError(f"unknown provider profile: {identifier}")
        return self._profiles[canonical].model_copy(deep=True)

    def profiles(self) -> tuple[ProviderProfile, ...]:
        return tuple(
            self._profiles[key].model_copy(deep=True)
            for key in sorted(self._profiles)
        )

    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._profiles))

    def resolve(
        self,
        identifier: str,
        *,
        methods: Collection[str] | None = None,
    ) -> ProviderResolution:
        profile = self.get(identifier)
        selected = (
            {method.method_id for method in profile.methods if method.enabled_by_default}
            if methods is None
            else {str(method).strip() for method in methods if str(method).strip()}
        )
        known = {method.method_id for method in profile.methods}
        unknown = sorted(selected - known)
        if unknown:
            raise KeyError(
                f"unknown access method(s) for {profile.provider_id}: "
                + ", ".join(unknown)
            )

        resolved: list[ProviderMethodResolution] = []
        for method in profile.methods:
            if method.method_id not in selected:
                continue

            status: ProviderMethodResolutionStatus
            detail = ""
            if not method.enabled_by_default and methods is None:
                status = "disabled"
                detail = "method is disabled by default"
            elif method.optional_dependency is not None:
                try:
                    dependency_found = (
                        importlib.util.find_spec(method.optional_dependency) is not None
                    )
                except (ImportError, ModuleNotFoundError, ValueError):
                    dependency_found = False
                if not dependency_found:
                    status = "dependency_missing"
                    detail = (
                        "optional dependency is not installed: "
                        + method.optional_dependency
                    )
                elif not method.auto_register:
                    status = "manual_binding_required"
                    detail = (
                        "dependency is installed but this method requires an explicit "
                        "trusted binding/plugin"
                    )
                else:
                    status = "available"
            elif not method.auto_register:
                status = "manual_binding_required"
                detail = "method requires an explicit trusted binding/plugin"
            else:
                status = "available"

            resolved.append(
                ProviderMethodResolution(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status=status,
                    url=method.url,
                    credential_names=method.credential_names,
                    optional_dependency=method.optional_dependency,
                    detail=detail,
                )
            )

        return ProviderResolution(
            requested_provider=identifier,
            provider_id=profile.provider_id,
            display_name=profile.display_name,
            profile_version=profile.profile_version,
            profile_source=profile.profile_source,
            methods=tuple(resolved),
        )


class ProviderProfilePluginInfo(StrictModel):
    name: str
    value: str
    distribution: str | None = None
    version: str | None = None


def _provider_entry_points() -> tuple[Any, ...]:
    entry_points = metadata.entry_points()
    if hasattr(entry_points, "select"):
        selected = entry_points.select(group=PROVIDER_PROFILE_ENTRY_POINT_GROUP)
    else:  # pragma: no cover - compatibility with older importlib.metadata surfaces.
        selected = entry_points.get(PROVIDER_PROFILE_ENTRY_POINT_GROUP, ())
    return tuple(selected)


def discover_provider_profile_plugins() -> tuple[ProviderProfilePluginInfo, ...]:
    """Discover provider-profile plugins without importing executable plugin code."""

    plugins: list[ProviderProfilePluginInfo] = []
    for entry_point in _provider_entry_points():
        distribution = getattr(entry_point, "dist", None)
        distribution_name = None
        version = None
        if distribution is not None:
            try:
                distribution_name = distribution.metadata.get("Name")
            except Exception:  # pragma: no cover - third-party metadata may be incomplete.
                distribution_name = None
            version = getattr(distribution, "version", None)
        plugins.append(
            ProviderProfilePluginInfo(
                name=str(entry_point.name),
                value=str(entry_point.value),
                distribution=(
                    str(distribution_name)
                    if distribution_name is not None
                    else None
                ),
                version=str(version) if version is not None else None,
            )
        )
    return tuple(sorted(plugins, key=lambda item: item.name))


def _coerce_profiles(value: Any) -> tuple[ProviderProfile, ...]:
    candidate = value() if callable(value) and not isinstance(value, type) else value
    if isinstance(candidate, ProviderProfile):
        return (candidate,)
    if isinstance(candidate, Iterable) and not isinstance(candidate, (str, bytes, dict)):
        profiles = tuple(candidate)
        if profiles and all(isinstance(item, ProviderProfile) for item in profiles):
            return profiles
    raise TypeError(
        "provider-profile plugin must expose a ProviderProfile or iterable of ProviderProfile"
    )


def load_provider_profile_plugins(
    registry: ProviderProfileRegistry,
    *,
    allowlist: Collection[str],
    replace: bool = False,
) -> tuple[str, ...]:
    """Import only explicitly allowlisted installed provider-profile plugins."""

    requested = {str(name).strip() for name in allowlist if str(name).strip()}
    if not requested:
        raise ValueError(
            "provider profile plugin loading requires a non-empty explicit allowlist"
        )

    available: dict[str, list[Any]] = {}
    for entry_point in _provider_entry_points():
        available.setdefault(str(entry_point.name), []).append(entry_point)

    missing = sorted(requested - set(available))
    if missing:
        raise KeyError("unknown provider profile plugin(s): " + ", ".join(missing))
    ambiguous = sorted(name for name in requested if len(available[name]) != 1)
    if ambiguous:
        raise RuntimeError(
            "ambiguous provider profile plugin name(s): " + ", ".join(ambiguous)
        )

    registered: list[str] = []
    for name in sorted(requested):
        profiles = _coerce_profiles(available[name][0].load())
        for profile in profiles:
            registered.append(registry.register(profile, replace=replace))
    return tuple(registered)


def built_in_provider_profile_registry() -> ProviderProfileRegistry:
    registry = ProviderProfileRegistry()
    registry.register(
        ProviderProfile(
            provider_id="materials-project",
            display_name="Materials Project",
            aliases=("materials project", "materialsproject", "mp"),
            profile_version="1",
            profile_source="schemarouter:builtin",
            homepage="https://materialsproject.org",
            methods=(
                ProviderAccessMethod(
                    method_id="optimade",
                    kind="optimade",
                    access_mode="optimade",
                    url="https://optimade.materialsproject.org",
                    description=(
                        "Public OPTIMADE endpoint for interoperable materials structure data."
                    ),
                ),
                ProviderAccessMethod(
                    method_id="openapi",
                    kind="openapi",
                    access_mode="openapi",
                    url="https://api.materialsproject.org/openapi.json",
                    credential_names=("X-API-KEY",),
                    description="Materials Project REST API OpenAPI document.",
                ),
                ProviderAccessMethod(
                    method_id="python-sdk",
                    kind="python",
                    access_mode="python",
                    optional_dependency="mp_api",
                    auto_register=False,
                    description=(
                        "Official mp-api Python client. Automatic binding is intentionally "
                        "not inferred from package introspection."
                    ),
                ),
            ),
        )
    )
    return registry
