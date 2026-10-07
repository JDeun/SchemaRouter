from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from .adapters.http_json import build_http_json_invoker, prepare_http_json_tool
from .errors import BindingDriftError, RegistrationError
from .executor import BoundEndpointInvoker, RegistryExecutor
from .ingestion import URLSchemaLoader
from .models import ToolSpec
from .provider_profiles import (
    ProviderMethodRegistration,
    ProviderRegistrationResult,
)
from .provider_service import ProviderProfileService
from .registry import (
    ToolRegistry,
    restore_many_if_current,
    update_many_if_current,
)

AddHttpTool = Callable[..., str]
AddUrl = Callable[..., Awaitable[ToolSpec]]


class ProviderRegistrationService:
    """Own provider access-method preparation and publication orchestration."""

    def __init__(
        self,
        *,
        profiles: ProviderProfileService,
        registry: ToolRegistry,
        executor: RegistryExecutor,
        loader: URLSchemaLoader,
    ) -> None:
        self._profiles = profiles
        self._registry = registry
        self._executor = executor
        self._loader = loader

    async def register(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None,
        trusted_headers_by_method: Mapping[str, Mapping[str, str]] | None,
        replace: bool,
        timeout: float,
        require_all: bool,
        add_http_tool: AddHttpTool,
        add_url: AddUrl,
    ) -> ProviderRegistrationResult:
        """Register provider access methods using best-effort or atomic semantics."""

        if not isinstance(require_all, bool):
            raise TypeError("require_all must be a bool")
        if require_all:
            return await self._register_require_all(
                provider,
                methods=methods,
                trusted_headers_by_method=trusted_headers_by_method,
                replace=replace,
                timeout=timeout,
            )
        return await self._register_best_effort(
            provider,
            methods=methods,
            trusted_headers_by_method=trusted_headers_by_method,
            replace=replace,
            timeout=timeout,
            add_http_tool=add_http_tool,
            add_url=add_url,
        )

    async def _register_require_all(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None,
        trusted_headers_by_method: Mapping[str, Mapping[str, str]] | None,
        replace: bool,
        timeout: float,
    ) -> ProviderRegistrationResult:
        """Stage and publish one provider topology as an all-or-nothing batch."""

        resolution = self._profiles.resolve(provider, methods=methods)
        profile = self._profiles.registry.get(provider)
        profile_methods = {item.method_id: item for item in profile.methods}
        headers_by_method = trusted_headers_by_method or {}
        expected_version = self._registry.version

        staged: dict[str, tuple[ToolSpec, BoundEndpointInvoker]] = {}
        outcomes: dict[str, ProviderMethodRegistration] = {}
        blocked = False

        for method in resolution.methods:
            if method.status != "available":
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status=method.status,
                    detail=method.detail,
                )
                blocked = True
                continue

            trusted_headers = dict(headers_by_method.get(method.method_id, {}))
            provided_header_names = {name.lower() for name in trusted_headers}
            missing_credentials = tuple(
                name
                for name in method.credential_names
                if name.lower() not in provided_header_names
            )
            if missing_credentials:
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="auth_required",
                    detail=(
                        "credential header(s) required: "
                        + ", ".join(missing_credentials)
                    ),
                )
                blocked = True
                continue

            if method.url is None:
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="manual_binding_required",
                    detail="method has no declarative URL source",
                )
                blocked = True
                continue

            profile_method = profile_methods[method.method_id]
            try:
                if method.kind == "http_json":
                    if profile_method.tool is None:
                        raise RegistrationError(
                            "http_json provider method has no trusted ToolSpec"
                        )
                    tool = prepare_http_json_tool(
                        profile_method.tool,
                        base_url=method.url,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                    )
                    invoker = build_http_json_invoker(
                        tool,
                        base_url=method.url,
                        trusted_headers=trusted_headers or None,
                        timeout=timeout,
                        http_client=self._loader.http_client,
                        network_policy=self._loader.network_policy,
                    )
                else:
                    inspected = await self._loader.inspect(
                        method.url,
                        kind=method.kind,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                        trusted_headers=trusted_headers or None,
                        timeout=timeout,
                    )
                    tool = inspected.tool
                    invoker = inspected.invoker
                    if invoker is None:
                        raise RegistrationError(
                            "provider access method has no executable binding"
                        )
                staged[method.method_id] = (tool, invoker)
            except Exception as exc:  # noqa: BLE001
                outcomes[method.method_id] = ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="unavailable",
                    error_type=type(exc).__name__,
                    detail="provider access method could not be prepared atomically",
                )
                blocked = True

        if blocked:
            for method in resolution.methods:
                if method.method_id not in outcomes:
                    outcomes[method.method_id] = ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="aborted",
                        detail=(
                            "atomic provider registration aborted because another "
                            "requested method could not be prepared"
                        ),
                    )
            return ProviderRegistrationResult(
                provider_id=resolution.provider_id,
                registered_tool_keys=(),
                methods=tuple(outcomes[item.method_id] for item in resolution.methods),
            )

        staged_items = tuple(
            (method, *staged[method.method_id])
            for method in resolution.methods
        )
        tool_keys = tuple(tool.key for _, tool, _ in staged_items)
        if len(tool_keys) != len(set(tool_keys)):
            raise RegistrationError(
                "atomic provider registration produced duplicate tool keys"
            )

        if self._registry.version != expected_version:
            raise RegistrationError(
                "registry changed concurrently while provider methods were staged"
            )

        previous_tools: dict[str, ToolSpec | None] = {}
        previous_bindings: dict[str, Any] = {}
        for _, tool, _ in staged_items:
            try:
                previous = self._registry.get(tool.key)
            except KeyError:
                previous = None
            if previous is not None and not replace:
                outcomes = {
                    method.method_id: ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="unavailable",
                        error_type="RegistrationError",
                        detail=(
                            "atomic provider registration requires replace=True "
                            f"for existing tool {tool.key!r}"
                        ),
                    )
                    for method, staged_tool, _ in staged_items
                    if staged_tool.key == tool.key
                }
                for method, _staged_tool, _ in staged_items:
                    if method.method_id not in outcomes:
                        outcomes[method.method_id] = ProviderMethodRegistration(
                            method_id=method.method_id,
                            kind=method.kind,
                            access_mode=method.access_mode,
                            status="aborted",
                            detail=(
                                "atomic provider registration aborted because another "
                                "requested method collided with an existing tool"
                            ),
                        )
                return ProviderRegistrationResult(
                    provider_id=resolution.provider_id,
                    registered_tool_keys=(),
                    methods=tuple(
                        outcomes[item.method_id] for item in resolution.methods
                    ),
                )
            previous_tools[tool.key] = previous
            previous_bindings[tool.key] = self._executor._binding_snapshot(tool.key)

        if self._registry.version != expected_version:
            raise RegistrationError(
                "registry changed concurrently before provider batch publication"
            )

        new_keys = tuple(
            key for key, previous in previous_tools.items() if previous is None
        )
        self._executor.ensure_tool_runtime_state_empty(new_keys)

        keys = update_many_if_current(
            self._registry,
            (tool for _, tool, _ in staged_items),
            expected_version=expected_version,
            replace=replace,
        )
        published_version = expected_version + (1 if keys else 0)
        expected_current = {
            tool.key: tool.fingerprint for _, tool, _ in staged_items
        }
        published_generations: dict[str, int] = {}

        try:
            for _, tool, invoker in staged_items:
                published_generations[tool.key] = self._executor.bind(
                    tool.key,
                    invoker,
                    expected_fingerprint=tool.fingerprint,
                )

            if self._registry.version != published_version:
                raise BindingDriftError(
                    "registry changed concurrently while publishing provider bindings"
                )
            for _, tool, _ in staged_items:
                if self._registry.get(tool.key).fingerprint != tool.fingerprint:
                    raise BindingDriftError(
                        f"tool {tool.key!r} changed during atomic provider publication"
                    )
        except Exception as exc:
            try:
                restore_many_if_current(
                    self._registry,
                    previous_tools,
                    expected_current=expected_current,
                    expected_version=published_version,
                )
            except Exception as rollback_exc:
                for key, generation in published_generations.items():
                    self._executor._remove_binding_if_generation(key, generation)
                raise BindingDriftError(
                    "atomic provider registration failed and registry rollback "
                    "could not preserve concurrent state"
                ) from rollback_exc

            runtime_conflict = False
            for key, generation in published_generations.items():
                if not self._executor._restore_binding_if_generation(
                    key,
                    generation,
                    previous_bindings[key],
                ):
                    runtime_conflict = True
            if runtime_conflict:
                raise BindingDriftError(
                    "atomic provider registration rolled back registry state but "
                    "newer executor state prevented binding rollback"
                ) from exc
            raise

        registrations = tuple(
            ProviderMethodRegistration(
                method_id=method.method_id,
                kind=method.kind,
                access_mode=method.access_mode,
                status="registered",
                tool_key=tool.key,
            )
            for method, tool, _ in staged_items
        )
        for key in keys:
            self._loader.remember_tool_schema_http_validators(
                self._registry.get(key)
            )
        return ProviderRegistrationResult(
            provider_id=resolution.provider_id,
            registered_tool_keys=keys,
            methods=registrations,
        )

    async def _register_best_effort(
        self,
        provider: str,
        *,
        methods: set[str] | list[str] | tuple[str, ...] | None,
        trusted_headers_by_method: Mapping[str, Mapping[str, str]] | None,
        replace: bool,
        timeout: float,
        add_http_tool: AddHttpTool,
        add_url: AddUrl,
    ) -> ProviderRegistrationResult:
        resolution = self._profiles.resolve(provider, methods=methods)
        profile = self._profiles.registry.get(provider)
        profile_methods = {item.method_id: item for item in profile.methods}
        headers_by_method = trusted_headers_by_method or {}
        registrations: list[ProviderMethodRegistration] = []
        registered_keys: list[str] = []

        for method in resolution.methods:
            if method.status != "available":
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status=method.status,
                        detail=method.detail,
                    )
                )
                continue

            trusted_headers = dict(headers_by_method.get(method.method_id, {}))
            provided_header_names = {name.lower() for name in trusted_headers}
            missing_credentials = tuple(
                name
                for name in method.credential_names
                if name.lower() not in provided_header_names
            )
            if missing_credentials:
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="auth_required",
                        detail=(
                            "credential header(s) required: "
                            + ", ".join(missing_credentials)
                        ),
                    )
                )
                continue

            if method.url is None:
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="manual_binding_required",
                        detail="method has no declarative URL source",
                    )
                )
                continue

            profile_method = profile_methods[method.method_id]
            try:
                if method.kind == "http_json":
                    if profile_method.tool is None:
                        raise RegistrationError(
                            "http_json provider method has no trusted ToolSpec"
                        )
                    tool_key = add_http_tool(
                        profile_method.tool,
                        base_url=method.url,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                        trusted_headers=trusted_headers or None,
                        timeout=timeout,
                        replace=replace,
                    )
                    tool = self._registry.get(tool_key)
                else:
                    tool = await add_url(
                        method.url,
                        kind=method.kind,
                        provider=resolution.provider_id,
                        access_mode=method.access_mode,
                        trusted_headers=trusted_headers or None,
                        replace=replace,
                        timeout=timeout,
                    )
            except Exception as exc:  # noqa: BLE001
                registrations.append(
                    ProviderMethodRegistration(
                        method_id=method.method_id,
                        kind=method.kind,
                        access_mode=method.access_mode,
                        status="unavailable",
                        error_type=type(exc).__name__,
                        detail="provider access method could not be registered",
                    )
                )
                continue

            registered_keys.append(tool.key)
            registrations.append(
                ProviderMethodRegistration(
                    method_id=method.method_id,
                    kind=method.kind,
                    access_mode=method.access_mode,
                    status="registered",
                    tool_key=tool.key,
                )
            )

        return ProviderRegistrationResult(
            provider_id=resolution.provider_id,
            registered_tool_keys=tuple(registered_keys),
            methods=tuple(registrations),
        )
