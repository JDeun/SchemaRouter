"""A5 opt-in *host-only* materialization of already proved P2 direct inputs.

This is invoked only after the scoped original-paper compiler has produced
its typed plan and the host approved the original root arguments. The frozen
agent must still choose a real offered tool; this callback never invokes it.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex, _host_source_input_names
from schemarouter.paper_typed_tool_plan import (
    PaperTypedToolPlan,
    _check_current_call_scopes,
)
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_fixed5_menu_e0 import paper_plan_fixed5_menu

ScopedHostCallBinding = Callable[
    [str, dict[str, Any]], tuple[dict[str, Any], bool],
]


def build_paper_a5_root_binding_e0(
    *,
    view: AuthorizedAgentToolSurface,
    plan: PaperTypedToolPlan | None,
    index: NativeSchemaGraphIndex,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    host_review_or_inputs_supplied: bool,
) -> ScopedHostCallBinding | None:
    """Capture ONE already-proved, source-owned ready direct call for E0.

    ``host_review_or_inputs_supplied`` is asserted by the trusted A5 host
    orchestration; the standalone plan is NOT an execution credential.
    An absent/incomplete/multi-alternative plan leaves normal agent behavior.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("A5 root binding requires scoped original source")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("A5 root binding requires current source graph")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("A5 root binding requires owner-reviewed catalog")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("A5 root binding requires owner-reviewed intent registry")
    if type(host_review_or_inputs_supplied) is not bool:
        raise ValueError("A5 source host authorization flag must be boolean")
    view.assert_source_unchanged()
    if (
        not host_review_or_inputs_supplied
        or plan is None
        or not isinstance(plan, PaperTypedToolPlan)
        or plan.status != "ready"
        or plan.executable_authority
        or len(plan.calls) != 1
        or plan.bindings
    ):
        return None

    root = plan.calls[0]
    route_id = root.route_id
    arguments = deepcopy(root.call.arguments)
    if (
        route_id not in index.approved_host_roots
        or route_id not in view.visible_route_ids
        or not arguments
        or type(arguments) is not dict
    ):
        return None

    index.field_index._assert_source(view.router)
    location = index.field_index.route_locations.get(route_id)
    if location is None:
        return None
    tool = view.router.registry.get(location[0])
    endpoint = tool.endpoint(location[1])
    names = _host_source_input_names(endpoint)
    if (
        names is None or set(arguments) != set(names)
        or (root.call.tool, root.call.endpoint) != location
        or not root.call.executable
        or root.call.missing_required_arguments
    ):
        return None

    # Verify the existing typed call, then pin the *entire* previously
    # authorized source state; a model may mutate mutable policy/index
    # contents during generation without changing Python object identity.
    _check_current_call_scopes(view.router, view._principal, [root])
    allowed = paper_plan_fixed5_menu(view, plan)
    if allowed != [route_id]:
        raise PolicyViolationError("A5 bound root is not the exact source menu")
    pinned_plan = deepcopy(plan)
    pinned_catalog = catalog.model_dump_json()
    pinned_intents = intent_registry.model_dump_json()
    pinned_graph = index.graph.model_copy(deep=True)
    pinned_contracts = deepcopy(index._source_contracts)
    pinned_host_roots = index.approved_host_roots
    pinned_edge_consumers = index.edge_consumer_routes

    def assert_source() -> None:
        view.assert_source_unchanged()
        index.field_index._assert_source(view.router)
        if (
            plan != pinned_plan
            or catalog.model_dump_json() != pinned_catalog
            or intent_registry.model_dump_json() != pinned_intents
            or index.graph != pinned_graph
            or index._source_contracts != pinned_contracts
            or index.approved_host_roots != pinned_host_roots
            or index.edge_consumer_routes != pinned_edge_consumers
        ):
            raise PolicyViolationError("A5 original source binding changed")
        if paper_plan_fixed5_menu(view, plan) != [route_id]:
            raise PolicyViolationError("A5 original direct route proof changed")
        _check_current_call_scopes(view.router, view._principal, [root])
        now_tool = view.router.registry.get(location[0])
        now_endpoint = now_tool.endpoint(location[1])
        if (
            _host_source_input_names(now_endpoint) != names
            or root.call.arguments != arguments
        ):
            raise PolicyViolationError("A5 registered host source inputs changed")
        available = view.router.planner.availability_predicate
        if available is not None and not available(now_tool, now_endpoint):
            raise PolicyViolationError("A5 approved source became unavailable")
        # Availability is host-supplied executable code. It may mutate
        # separate owner declarations while returning True. Recheck the FULL
        # captured source set after the final mutable probe, not merely the
        # plan/graph subset, before materializing any argument.
        view.assert_source_unchanged()
        index.field_index._assert_source(view.router)
        if (
            plan != pinned_plan
            or catalog.model_dump_json() != pinned_catalog
            or intent_registry.model_dump_json() != pinned_intents
            or index.graph != pinned_graph
            or index._source_contracts != pinned_contracts
            or index.approved_host_roots != pinned_host_roots
            or index.edge_consumer_routes != pinned_edge_consumers
            or _host_source_input_names(now_endpoint) != names
            or root.call.arguments != arguments
        ):
            raise PolicyViolationError("A5 direct input changed during source probe")

    assert_source()

    def bind(route: str, model_arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        assert_source()
        if route != route_id:
            return deepcopy(model_arguments), False
        bound = deepcopy(arguments)
        assert_source()
        return bound, True

    return bind
