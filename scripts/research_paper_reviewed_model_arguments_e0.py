"""Host-reviewed model scalar proposals -> existing source-typed P2 host inputs.

Research-only opt-in. Merely parsing a model hint never authorizes any call;
the host must inspect and explicitly approve the exact source-root proposal.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.errors import SchemaValidationError
from schemarouter.native_graph_index import (
    NativeSchemaGraphIndex,
    _host_source_input_names,
)
from schemarouter.paper_typed_tool_plan import PaperTypedToolPlan
from schemarouter.paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    compile_paper_understood_direct_plan,
)
from schemarouter.paper_understood_graph_plan import compile_paper_understood_graph_plan
from schemarouter.validation import validate_json_schema_value
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface


@dataclass(frozen=True, slots=True)
class PaperRootArgumentProposal:
    """Detached untrusted input values plus the ORIGINAL root source identity."""

    route_id: str
    tool_fingerprint: str
    endpoint_fingerprint: str
    parameter_values: tuple[tuple[str, str | int | float | bool], ...]
    executable_authority: bool = False
    independent_e2: bool = False


PaperRootArgumentReviewer = Callable[
    [PaperRootArgumentProposal], bool | Awaitable[bool],
]


async def review_paper_root_model_arguments_e0(
    reviewer: PaperRootArgumentReviewer,
    *,
    view: AuthorizedAgentToolSurface,
    understanding: PaperUnderstanding,
    plan: PaperTypedToolPlan,
    index: NativeSchemaGraphIndex,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
) -> dict[str, dict[str, Any]] | None:
    """Ask host approval only for exact required parameters of a proven root.

    Returns the existing compiler's host-input shape; caller MUST recompile
    and check original authorization before offering or invoking anything.
    ``None`` means no proposal or no exact host approval, not no global fit.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("model root review requires a principal-scoped source")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("model root review requires an original graph index")
    if not isinstance(understanding, PaperUnderstanding):
        raise ValueError("model root review requires structured model hints")
    if not isinstance(plan, PaperTypedToolPlan):
        raise ValueError("model root review requires a typed paper plan")
    if not callable(reviewer):
        raise ValueError("model root review requires an explicit host callback")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("model root review requires original semantic catalog")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("model root review requires original intent declarations")

    view.assert_source_unchanged()
    index.field_index._assert_source(view.router)
    pinned_plan = deepcopy(plan)
    pinned_understanding = understanding.model_dump_json()
    pinned_catalog = catalog.model_dump_json()
    pinned_intents = intent_registry.model_dump_json()
    pinned_graph = index.graph.model_copy(deep=True)
    pinned_contracts = deepcopy(index._source_contracts)
    pinned_host_roots = index.approved_host_roots
    pinned_consumers = index.edge_consumer_routes

    def check_graph_source() -> None:
        if (
            index.graph != pinned_graph
            or index._source_contracts != pinned_contracts
            or index.approved_host_roots != pinned_host_roots
            or index.edge_consumer_routes != pinned_consumers
        ):
            raise PolicyViolationError("paper model root graph source changed")

    # PaperTypedToolPlan is publicly constructible. Never show its call or
    # parameters to a host reviewer before the ORIGINAL source independently
    # proves the identical plan in this principal's current scope.
    verified = compile_paper_understood_graph_plan(
        view.router, understanding, principal=view._principal,
        catalog=catalog, intent_registry=intent_registry, index=index,
    )
    if verified != plan:
        direct = compile_paper_understood_direct_plan(
            view.router, understanding, principal=view._principal,
            catalog=catalog, intent_registry=intent_registry, index=index,
        )
        if direct != plan:
            raise PolicyViolationError("paper model root review lacks original plan proof")
    view.assert_source_unchanged()
    check_graph_source()

    if (
        plan.status not in ("requires_arguments", "requires_observation")
        or not 1 <= len(plan.calls) <= 3
        or plan.executable_authority
        # A graph is ONE dependency plan; multiple binding-free direct calls
        # are alternatives. Approving just the first would not authorize or
        # resolve the remaining alternatives, so decline a partial review.
        or not plan.bindings and len(plan.calls) != 1
    ):
        return None
    root = plan.calls[0]
    route_id = root.route_id
    if (
        route_id not in index.approved_host_roots
        or route_id not in view.visible_route_ids
        or root.call.arguments
        or root.call.executable
        or not root.call.missing_required_arguments
        or any(binding.consumer_call_index == 0 for binding in plan.bindings)
    ):
        return None
    location = index.field_index.route_locations.get(route_id)
    if location is None:
        return None
    tool = view.router.registry.get(location[0])
    endpoint = tool.endpoint(location[1])
    names = _host_source_input_names(endpoint)
    hints = understanding.parameter_hints
    if (
        names is None
        or set(root.call.missing_required_arguments) != set(names)
        or set(hints) != set(names)
        or (tool.fingerprint, endpoint.fingerprint)
        != (root.call.tool_fingerprint, root.call.schema_fingerprint)
        or index.field_index.route_fingerprints.get(route_id)
        != (tool.fingerprint, endpoint.fingerprint)
    ):
        return None
    scalar_types = (str, int, float, bool)
    if any(
        type(hints[name]) not in scalar_types
        or type(hints[name]) is str and not hints[name]
        for name in names
    ):
        return None
    proposed = {name: hints[name] for name in names}
    try:
        validate_json_schema_value(
            proposed, endpoint.input_schema,
            context="untrusted paper root argument proposal",
        )
    except SchemaValidationError:
        return None

    proposal = PaperRootArgumentProposal(
        route_id=route_id,
        tool_fingerprint=tool.fingerprint,
        endpoint_fingerprint=endpoint.fingerprint,
        parameter_values=tuple((name, proposed[name]) for name in names),
    )
    # The host callback is the only authority to accept this exact value;
    # the proposed object is frozen and detached from mutable model storage.
    decision = reviewer(proposal)
    if inspect.isawaitable(decision):
        decision = await decision

    view.assert_source_unchanged()
    index.field_index._assert_source(view.router)
    check_graph_source()
    if (
        plan != pinned_plan
        or understanding.model_dump_json() != pinned_understanding
        or catalog.model_dump_json() != pinned_catalog
        or intent_registry.model_dump_json() != pinned_intents
    ):
        raise PolicyViolationError("model root proposal changed during host review")
    if decision is not True:
        return None
    return {route_id: deepcopy(proposed)}
