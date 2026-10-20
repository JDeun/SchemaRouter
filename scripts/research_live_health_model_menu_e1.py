"""Isolated #1618 E1: trusted health and actual principal-scoped model menu.

Host-owned probes only: no inferred data endpoint health checks, no model-driven
health overrides, no production default or change to previous real E1 studies.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from schemarouter import (
    InvocationUnavailableError,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
)
from schemarouter.health import HealthProbe
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    capture_authorized_agent_tool_surface,
)
from scripts.research_open_meteo_live_two_hop_e1 import (
    OpenMeteoBoundInvoker,
    build_live_router,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call
from scripts.research_source_ready_native_tool_menu_e1 import (
    source_ready_visible_routes,
)

GEO = "open_meteo_geocoding.search"
WEATHER = "open_meteo_weather.current"
ROUTES = (GEO, WEATHER)
MenuStatus = Literal["ready", "inputs_missing", "temporary_unavailable"]


class AvailabilityClassifiedInvoker:
    """Strictly read-only opt-in wrapper over the ORIGINAL trusted invoker.

    Only remote transport failures or selected retryable statuses become
    InvocationUnavailableError. Source/payload/policy/malformed JSON errors
    retain their previous classification and NEVER mark a route unhealthy.
    """

    def __init__(self, delegate: OpenMeteoBoundInvoker) -> None:
        if not isinstance(delegate, OpenMeteoBoundInvoker):
            raise ValueError("trusted original Open-Meteo bound invoker required")
        self.delegate = delegate

    async def __call__(
        self, endpoint: str, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return await self.delegate(endpoint, arguments)
        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.ProxyError,
        ):
            raise InvocationUnavailableError(
                "trusted read-only provider transport temporarily unavailable"
            ) from None
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or 500 <= status <= 599:
                raise InvocationUnavailableError(
                    "trusted read-only provider HTTP temporarily unavailable"
                ) from None
            raise


def build_health_aware_router(
    client: httpx.AsyncClient, *,
    trusted_health_probes: Mapping[str, HealthProbe],
    transport_retry_budget: int = 0,
) -> SchemaRouter:
    """Opt-in trusted binding. No probes are invented or started implicitly."""
    if not isinstance(trusted_health_probes, Mapping) or any(
        route not in ROUTES or not callable(probe)
        for route, probe in trusted_health_probes.items()
    ):
        raise ValueError("only explicit trusted read-only probes may be registered")
    router, geocode, weather = build_live_router(
        client, transport_retry_budget=transport_retry_budget,
    )
    for route, delegate in ((GEO, geocode), (WEATHER, weather)):
        tool_key, endpoint = route.rsplit(".", 1)
        tool = router.registry.get(tool_key)
        spec = tool.endpoint(endpoint)
        if spec.read_only is not True or spec.destructive:
            raise ValueError("health-aware classification requires read-only path")
        router.executor.bind(
            tool_key, AvailabilityClassifiedInvoker(delegate),
            expected_fingerprint=tool.fingerprint,
        )
        probe = trusted_health_probes.get(route)
        if probe is not None:
            router.register_health_probe(tool_key, endpoint, probe)
    return router


@dataclass(frozen=True)
class HealthScopedModelMenu:
    """Research presentation receipt; this is NOT execution authorization."""

    view: AuthorizedAgentToolSurface
    route_ids: tuple[str, ...]
    definitions: tuple[dict[str, Any], ...]
    status: MenuStatus
    checked_at: tuple[tuple[str, datetime], ...]
    max_probe_age_seconds: float

    def assert_current(self) -> None:
        """Fail closed on cooldown, probe replacement, aging or source drift."""
        self.view.assert_source_unchanged()
        current = {
            f"{snapshot.tool}.{snapshot.endpoint}": snapshot
            for snapshot in self.view.router.health_snapshots()
        }
        expected = dict(self.checked_at)
        if set(self.route_ids) != set(expected):
            raise PolicyViolationError("model-visible health receipt inconsistent")
        for route in self.route_ids:
            record = current.get(route)
            tool_key, endpoint = route.rsplit(".", 1)
            tool = self.view.router.registry.get(tool_key)
            if (
                record is None
                or record.status != "healthy"
                or record.last_checked_at != expected[route]
                or not _fresh(record.last_checked_at, self.max_probe_age_seconds)
                or not self.view.router.executor.is_access_available_for_contract(
                    tool_key, endpoint, tool.fingerprint,
                )
            ):
                raise PolicyViolationError(
                    "model-visible tool availability changed; rebuild menu"
                )
        self.view.assert_source_unchanged()


def _fresh(checked: datetime | None, age_seconds: float) -> bool:
    if checked is None or checked.tzinfo is None:
        return False
    elapsed = (datetime.now(timezone.utc) - checked).total_seconds()
    return 0 <= elapsed <= age_seconds


def _authorized_input_ready_cooldown(
    router: SchemaRouter, principal: PrincipalContext,
    host_request_inputs: dict[str, Any],
    prior_public_observation: dict[str, Any] | None,
    executed_route_ids: tuple[str, ...],
) -> bool:
    """Host-only cause classification; never disclose denied route identity.

    Availability-filtered retrieval cannot include cooled-down operations.
    For an internal TEMPORARILY_UNAVAILABLE reason only, cross-check exact
    registered original read-only route, current principal policy, actual
    supplied required-parameter names and executor cooldown. Never infer a
    route from query text, model output, source metadata or hidden gold.
    """
    cooled = set(router.unavailable_access_paths())
    if not cooled:
        return False
    names = set(host_request_inputs)
    if prior_public_observation is not None:
        names.update(prior_public_observation)
        names.discard("status")
    authorized = router._authorization_predicate(principal)
    for route in ROUTES:
        if route in executed_route_ids:
            continue
        key, endpoint_name = route.rsplit(".", 1)
        if (key, endpoint_name) not in cooled:
            continue
        try:
            tool = router.registry.get(key)
            endpoint = tool.endpoint(endpoint_name)
        except KeyError:
            continue
        if (
            endpoint.read_only is not True
            or endpoint.destructive
            or endpoint.auth_requirements
            or authorized is not None and not authorized(tool, endpoint)
        ):
            continue
        if all(
            param.name in names for param in endpoint.parameters
            if param.required
        ):
            return True
    return False


def capture_health_scoped_model_menu(
    router: SchemaRouter, query: str, *, principal: PrincipalContext,
    host_request_inputs: dict[str, Any],
    prior_public_observation: dict[str, Any] | None = None,
    executed_route_ids: tuple[str, ...] = (),
    max_probe_age_seconds: float = 60.0,
) -> HealthScopedModelMenu:
    """Build actual model tool JSON from input readiness AND current liveness.

    No probe means UNKNOWN (not healthy). When ready candidates are all down
    the host reports temporary_unavailable, NOT semantic unsupported/no-fit.
    """
    if (
        type(max_probe_age_seconds) not in (int, float)
        or isinstance(max_probe_age_seconds, bool)
        or not 0 < max_probe_age_seconds <= 3600
    ):
        raise ValueError("bounded positive probe freshness required")
    view = capture_authorized_agent_tool_surface(
        router, query, principal=principal,
    )
    ready = source_ready_visible_routes(
        view, host_request_inputs=host_request_inputs,
        prior_public_observation=prior_public_observation,
        executed_route_ids=executed_route_ids,
    )
    snapshots = {
        f"{item.tool}.{item.endpoint}": item
        for item in router.health_snapshots()
    }
    selected: list[str] = []
    checked: list[tuple[str, datetime]] = []
    for route in ready:
        if route not in ROUTES:
            raise PolicyViolationError("unregistered health-aware native route")
        item = snapshots.get(route)
        if item is None or item.status != "healthy":
            continue
        if not _fresh(item.last_checked_at, float(max_probe_age_seconds)):
            continue
        key, endpoint = route.rsplit(".", 1)
        tool = router.registry.get(key)
        if not router.executor.is_access_available_for_contract(
            key, endpoint, tool.fingerprint,
        ):
            continue
        selected.append(route)
        # _fresh guarantees this timestamp is not None.
        assert item.last_checked_at is not None
        checked.append((route, item.last_checked_at))
    definitions = tuple(view.tool_definitions(selected, k=2)) if selected else ()
    menu: HealthScopedModelMenu = HealthScopedModelMenu(
        view=view,
        route_ids=tuple(selected),
        definitions=definitions,
        status=(
            "ready" if selected
            else "temporary_unavailable" if (
                ready or _authorized_input_ready_cooldown(
                    router, principal, host_request_inputs,
                    prior_public_observation, executed_route_ids,
                )
            )
            else "inputs_missing"
        ),
        checked_at=tuple(checked),
        max_probe_age_seconds=float(max_probe_age_seconds),
    )
    menu.assert_current()
    return menu

async def execute_health_scoped_host_call(
    menu: HealthScopedModelMenu, *,
    route_id: str, arguments: dict[str, Any],
    host_required_output_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Recheck same presented, healthy, authorized route BEFORE invocation.

    The canonical existing scoped host builder and RegistryExecutor remain the
    sole execution authority; a model-proposed route alone never grants it.
    """
    menu.assert_current()
    if route_id not in menu.route_ids:
        raise PolicyViolationError("model operation not in current healthy menu")
    return await execute_scoped_host_call(
        menu.view, selected_route_ids=list(menu.route_ids),
        route_id=route_id, arguments=arguments,
        host_required_output_fields=host_required_output_fields,
    )
