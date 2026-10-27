"""E1 opt-in A5 original direct ToolCall → existing native registered invoker.

The model selects a source-proved route; only the trusted host may supply
actual parameters. This runs one read-only provider call, not an E2 oracle.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from schemarouter import ExecutionPlan, PolicyViolationError, ToolResult
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.errors import SchemaValidationError
from schemarouter.executor import _require_bound_invoker_generation
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_typed_tool_plan import _check_current_call_scopes
from schemarouter.paper_understood_direct_plan import PaperIntentRegistry
from schemarouter.runs import ExecutionBudget, RunConfig
from scripts.agent_utility_generated_common import GeneratedEpisodeAgent
from scripts.evaluate_agent_utility_phase_b_smollm3 import (
    SYSTEM_PROMPT,
    TOOL_CALL_RE,
    _parse_tool_calls,
)
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_a5_runtime_source_binding_e0 import (
    build_paper_a5_root_binding_e0,
)
from scripts.research_paper_fixed5_menu_e0 import paper_plan_fixed5_menu
from scripts.research_paper_refusal_eval_e0 import Decision
from scripts.research_paper_reviewed_model_arguments_e0 import PaperRootArgumentReviewer
from scripts.research_paper_scoped_plan_e0 import analyze_and_plan_paper_scoped_e0
from scripts.research_paper_scoped_understand_e0 import PaperScopedModel

MAX_LIVE_AGENT_GENERATION_BYTES = 16384


def _unique_object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject ambiguous duplicate names before the historical agent parser."""
    unique: dict[str, Any] = {}
    for name, value in pairs:
        if name in unique:
            raise ValueError("duplicate tool-call JSON field")
        unique[name] = value
    return unique


@dataclass(frozen=True, slots=True)
class PaperScopedNativeDirectE1:
    """Host-only native result; neither model text nor provider E2 evidence."""

    route_id: str
    result: ToolResult
    host_bound_tool_calls: int
    provider_provenance_verified: bool = False
    answer_verified: bool = False
    executable_authority: bool = False
    independent_e2: bool = False


async def run_paper_scoped_native_direct_e1(
    model: PaperScopedModel,
    agent: GeneratedEpisodeAgent,
    *,
    view: AuthorizedAgentToolSurface,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
    index: NativeSchemaGraphIndex,
    model_visible_intent_ids: tuple[str, ...],
    model_visible_concept_ids: tuple[str, ...],
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
    review_model_root_arguments: PaperRootArgumentReviewer | None = None,
) -> tuple[Decision, PaperScopedNativeDirectE1 | None]:
    """One source-proved direct agent call through original `router.execute`.

    This is separately opted-in by a trusted host. A non-ready P2 receipt
    never enters agent generation or native I/O, unlike the synthetic
    legacy A5 benchmark's missing-input diagnostic mode.
    """
    if not isinstance(view, AuthorizedAgentToolSurface):
        raise ValueError("E1 original direct execution requires scoped source")
    if not isinstance(index, NativeSchemaGraphIndex):
        raise ValueError("E1 original direct execution requires native graph index")
    if not isinstance(catalog, NativeConceptCatalog):
        raise ValueError("E1 original direct execution requires owner catalog")
    if not isinstance(intent_registry, PaperIntentRegistry):
        raise ValueError("E1 original direct execution requires owner intents")

    host_pinned = deepcopy(host_source_arguments)
    catalog_pinned = catalog.model_dump_json()
    intents_pinned = intent_registry.model_dump_json()
    graph_pinned = index.graph.model_copy(deep=True)
    contracts_pinned = deepcopy(index._source_contracts)
    roots_pinned = index.approved_host_roots
    consumers_pinned = index.edge_consumer_routes

    def check_declarations() -> None:
        view.assert_source_unchanged()
        index.field_index._assert_source(view.router)
        if (
            host_source_arguments != host_pinned
            or catalog.model_dump_json() != catalog_pinned
            or intent_registry.model_dump_json() != intents_pinned
            or index.graph != graph_pinned
            or index._source_contracts != contracts_pinned
            or index.approved_host_roots != roots_pinned
            or index.edge_consumer_routes != consumers_pinned
        ):
            raise PolicyViolationError("E1 original direct source declarations changed")

    check_declarations()
    decision, plan = await analyze_and_plan_paper_scoped_e0(
        model, view=view, catalog=catalog, intent_registry=intent_registry,
        index=index, model_visible_intent_ids=model_visible_intent_ids,
        model_visible_concept_ids=model_visible_concept_ids,
        host_source_arguments=host_source_arguments,
        review_model_root_arguments=review_model_root_arguments,
    )
    check_declarations()
    if decision != "offer" or plan is None or plan.status != "ready":
        return decision, None
    if (
        plan.executable_authority or plan.bindings
        or len(plan.calls) != 1 or not plan.calls[0].call.executable
    ):
        return "abstain", None
    routes = paper_plan_fixed5_menu(view, plan)
    if len(routes) != 1 or routes != [plan.calls[0].route_id]:
        return "abstain", None

    host_binding = None
    if plan.calls[0].call.arguments:
        host_binding = build_paper_a5_root_binding_e0(
            view=view, plan=plan, index=index, catalog=catalog,
            intent_registry=intent_registry,
            host_review_or_inputs_supplied=(
                host_source_arguments is not None
                or review_model_root_arguments is not None
            ),
        )
        if host_binding is None:
            return "request_arguments", None

    plan_pinned = deepcopy(plan)
    selected = plan.calls[0]
    native_executor = view.router.executor
    binding_pinned = native_executor._binding_snapshot(selected.call.tool)
    if (
        binding_pinned.invoker is None
        or binding_pinned.generation is None
        or binding_pinned.fingerprint
        != view.router.registry.get(selected.call.tool).fingerprint
    ):
        raise PolicyViolationError("E1 original direct native invoker binding unavailable")

    def check_current() -> None:
        check_declarations()
        if (
            view.router.executor is not native_executor
            or native_executor._binding_snapshot(selected.call.tool) != binding_pinned
        ):
            raise PolicyViolationError("E1 original direct native invoker binding changed")
        if plan != plan_pinned or paper_plan_fixed5_menu(view, plan) != routes:
            raise PolicyViolationError("E1 original direct P2 proof changed")
        _check_current_call_scopes(view.router, view._principal, [selected])
        tool = view.router.registry.get(selected.call.tool)
        endpoint = tool.endpoint(selected.call.endpoint)
        if endpoint.read_only is not True or endpoint.destructive is True:
            raise PolicyViolationError("E1 original direct route is not read-only")
        available = view.router.planner.availability_predicate
        if available is not None and not available(tool, endpoint):
            raise PolicyViolationError("E1 original direct source unavailable")
        # Availability predicates are executable host code, so recheck the
        # complete source proofs AFTER they return as well.
        check_declarations()
        if plan != plan_pinned:
            raise PolicyViolationError("E1 source changed during availability probe")

    check_current()
    tools = view.tool_definitions(routes)
    offered_tools_pinned = deepcopy(tools)
    generated = agent.generate(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": view.original_query},
        ],
        tools,
    )
    check_current()
    if tools != offered_tools_pinned:
        raise PolicyViolationError("E1 agent modified offered tool definition")
    if type(generated) is not dict:
        return "abstain", None
    raw = generated.get("text")
    if (
        type(raw) is not str
        or len(raw.encode("utf-8")) > MAX_LIVE_AGENT_GENERATION_BYTES
        or generated.get("context_overflow") is not False
    ):
        return "abstain", None
    try:
        # Preserve the original agent's canonical tagged JSON call format.
        # Require the whole reply to be ONE call, not surrounding instructions.
        match = TOOL_CALL_RE.fullmatch(raw.strip())
        if match is None:
            return "abstain", None
        unambiguous = json.loads(
            match.group(1), object_pairs_hook=_unique_object_pairs,
        )
        if (
            type(unambiguous) is not dict
            or type(unambiguous.get("arguments", {})) is not dict
        ):
            return "abstain", None
        calls = _parse_tool_calls(raw)
    except (ValueError, TypeError, OverflowError, RecursionError):
        return "abstain", None
    if len(calls) != 1 or calls[0]["name"] != offered_tools_pinned[0]["name"]:
        return "abstain", None
    model_args = calls[0]["arguments"]
    if (
        len(model_args) > 8
        or any(
            type(key) is not str or type(value) not in (str, int, float, bool)
            or type(value) is float and not math.isfinite(value)
            or type(value) is str and len(value.encode("utf-8")) > 4096
            for key, value in model_args.items()
        )
    ):
        # A real provider never needs the model's untrusted nested object:
        # accepted arguments come only from the original typed host proof.
        return "abstain", None
    if host_binding is None:
        if model_args:
            # An unreviewed optional input is not present in the typed P2
            # call. It cannot gain authority from an agent's own guess.
            return "abstain", None
        arguments, assisted = {}, False
    else:
        arguments, assisted = host_binding(routes[0], model_args)
        if not assisted or arguments != selected.call.arguments:
            raise PolicyViolationError("E1 direct input was not host materialized")

    check_current()
    original_call = selected.call.model_copy(deep=True, update={
        "arguments": deepcopy(arguments),
    })
    if not original_call.executable or original_call.missing_required_arguments:
        raise SchemaValidationError("E1 direct source input is not executable")
    with _require_bound_invoker_generation(
        native_executor, selected.call.tool, binding_pinned.generation,
    ):
        results = await view.router.execute(ExecutionPlan(
            query=view.original_query,
            registry_version=plan.registry_version,
            calls=[original_call],
        ), config=RunConfig(
            principal=view._principal.model_copy(deep=True),
            budget=ExecutionBudget(
                max_tool_calls=1, max_attempts=1, max_remote_attempts=1,
            ),
        ))
    check_current()
    if (
        len(results) != 1
        or not isinstance(results[0], ToolResult)
        or (results[0].tool, results[0].endpoint)
        != (original_call.tool, original_call.endpoint)
        or results[0].projected_fields != original_call.fields
        or not set(original_call.fields) <= set(results[0].field_contracts)
    ):
        raise SchemaValidationError("E1 original native execution lost typed projection")
    check_current()
    return "offer", PaperScopedNativeDirectE1(
        route_id=routes[0], result=results[0],
        host_bound_tool_calls=int(assisted),
    )
