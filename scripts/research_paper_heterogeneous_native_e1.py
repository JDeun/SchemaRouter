"""Opt-in A5 E1 source-native direct matrix over ONE registered heterogeneous catalog.

Each case uses the original reviewed P2 direct proof, agent ToolCall parser,
host-bound arguments and registered SchemaRouter executor. This is not E2.
"""

from __future__ import annotations

import inspect
import math
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from schemarouter import PolicyViolationError
from schemarouter.concept_retrieval import NativeConceptCatalog
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.paper_understood_direct_plan import (
    PaperIntentRegistry,
    PaperUnderstanding,
    compile_paper_understood_direct_plan,
)
from schemarouter.validation import effective_input_schema, validate_json_schema_value
from scripts.agent_utility_generated_common import GeneratedEpisodeAgent
from scripts.research_authorized_agent_tool_surface import AuthorizedAgentToolSurface
from scripts.research_paper_scoped_native_direct_e1 import (
    PaperScopedNativeDirectE1,
    run_paper_scoped_native_direct_e1,
)
from scripts.research_paper_scoped_understand_e0 import PaperScopedModel

MAX_E1_SOURCES = 5


def _accepts_inputs(callback: Any, *args: Any) -> bool:
    """Check later cases without invoking user-supplied model/agent code."""
    if not callable(callback):
        return False
    try:
        inspect.signature(callback).bind(*args)
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True, slots=True)
class PaperNativeSourceCase:
    case_id: str
    route_id: str
    intent_id: str
    concept_id: str
    host_arguments: dict[str, Any] | None
    model: PaperScopedModel
    agent: GeneratedEpisodeAgent


@dataclass(frozen=True, slots=True)
class PaperHeterogeneousNativeE1:
    """Host-only completed native results; no model or E2 quality attestation."""

    receipts: tuple[PaperScopedNativeDirectE1, ...]
    executed_routes: tuple[str, ...]
    registered_source_types: tuple[str, ...]
    heterogeneous_sources: bool
    host_bound_tool_calls: int
    independent_e2: bool = False


def _checked_host_inputs(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if type(value) is not dict or not 1 <= len(value) <= 4:
        raise ValueError("E1 source case requires bounded explicit host arguments")
    if any(
        type(name) is not str or not name.isidentifier()
        or type(item) not in (str, int, float, bool)
        or type(item) is str and (not item.strip() or len(item.encode("utf-8")) > 4096)
        or type(item) is float and not math.isfinite(item)
        for name, item in value.items()
    ):
        raise ValueError("E1 source case host arguments must be bounded scalars")
    return deepcopy(value)


async def run_paper_heterogeneous_native_e1(
    *,
    cases: tuple[PaperNativeSourceCase, ...],
    view: AuthorizedAgentToolSurface,
    index: NativeSchemaGraphIndex,
    catalog: NativeConceptCatalog,
    intent_registry: PaperIntentRegistry,
) -> PaperHeterogeneousNativeE1:
    """Run up to K5 independently source-proved A5 direct native calls.

    Every case's original typed readiness is proved up front, before model
    generation or provider I/O. Previously executed reads are not atomic.
    """
    if (
        type(cases) is not tuple
        or not 1 <= len(cases) <= MAX_E1_SOURCES
        or any(not isinstance(case, PaperNativeSourceCase) for case in cases)
        or not isinstance(view, AuthorizedAgentToolSurface)
        or not isinstance(index, NativeSchemaGraphIndex)
        or not isinstance(catalog, NativeConceptCatalog)
        or not isinstance(intent_registry, PaperIntentRegistry)
    ):
        raise ValueError("original heterogeneous A5 source manifest required")
    ids: set[str] = set()
    routes: set[str] = set()
    original_cases: list[tuple[PaperNativeSourceCase, dict[str, Any] | None]] = []
    registered_source_types: list[str] = []
    concepts = {item.concept_id: item for item in catalog.concepts}
    intents = {item.intent_id: item for item in intent_registry.intents}

    # Pin the full shared owner graph, not just the registry version. The
    # single-call bridge checks its own snapshot, but a changed graph between
    # two calls must not silently become the matrix's new trusted baseline.
    catalog_pinned = catalog.model_dump_json()
    intents_pinned = intent_registry.model_dump_json()
    graph_pinned = index.graph.model_copy(deep=True)
    contracts_pinned = deepcopy(index._source_contracts)
    roots_pinned = index.approved_host_roots
    consumers_pinned = index.edge_consumer_routes
    native_executor = view.router.executor
    binding_pinned: dict[str, Any] = {}

    def check_matrix_source() -> None:
        view.assert_source_unchanged()
        index.field_index._assert_source(view.router)
        if (
            catalog.model_dump_json() != catalog_pinned
            or intent_registry.model_dump_json() != intents_pinned
            or index.graph != graph_pinned
            or index._source_contracts != contracts_pinned
            or index.approved_host_roots != roots_pinned
            or index.edge_consumer_routes != consumers_pinned
            or view.router.executor is not native_executor
            or any(native_executor._binding_snapshot(tool_key) != snapshot
                   for tool_key, snapshot in binding_pinned.items())
        ):
            raise PolicyViolationError("E1 heterogeneous source or native binding changed")

    check_matrix_source()
    # Pin every advertised route's native binding *before* the P2 compiler
    # can invoke a stateful host availability callback for the first case.
    # An incrementally collected snapshot would bless a replacement binding
    # for a later provider as the new baseline during this same preflight.
    for case in cases:
        if (
            type(case.route_id) is not str
            or case.route_id not in view.visible_route_ids
        ):
            raise ValueError("E1 heterogeneous source route is not authorized")
        tool_name, separator, endpoint_name = case.route_id.rpartition(".")
        if not separator or not tool_name or not endpoint_name:
            raise ValueError("E1 native route must be original tool.endpoint")
        tool = view.router.registry.get(tool_name)
        binding = native_executor._binding_snapshot(tool_name)
        if (
            binding.invoker is None or binding.generation is None
            or binding.fingerprint != tool.fingerprint
            or tool_name in binding_pinned and binding_pinned[tool_name] != binding
        ):
            raise PolicyViolationError("E1 heterogeneous native invoker binding unavailable")
        binding_pinned[tool_name] = binding
    check_matrix_source()
    for case in cases:
        if (
            type(case.case_id) is not str
            or not 1 <= len(case.case_id) <= 128
            or case.case_id in ids
            or type(case.route_id) is not str
            or case.route_id in routes
            or case.route_id not in view.visible_route_ids
            or case.intent_id not in intents
            or case.concept_id not in concepts
            or case.concept_id not in intents[case.intent_id].required_concept_ids
            or not _accepts_inputs(case.model, {})
            or not _accepts_inputs(getattr(case.agent, "generate", None), [], [])
        ):
            raise ValueError("E1 heterogeneous source/generator is invalid or unauthorized")
        ids.add(case.case_id)
        routes.add(case.route_id)
        tool_name, separator, endpoint_name = case.route_id.rpartition(".")
        if not separator or not tool_name or not endpoint_name:
            raise ValueError("E1 native route must be original tool.endpoint")
        tool = view.router.registry.get(tool_name)
        endpoint = tool.endpoint(endpoint_name)
        concept = concepts[case.concept_id]
        if (
            tool.source_type is None
            or tool.license is None
            or tool.source_type != concept.source_type
            or tool.license != concept.license
            or endpoint.read_only is not True
            or endpoint.destructive is True
            or endpoint.auth_requirements
        ):
            raise PermissionError("E1 heterogeneous source proof or read-only review missing")
        approved = _checked_host_inputs(case.host_arguments)
        host_inputs = {case.route_id: approved} if approved is not None else None
        if approved is not None:
            declared = {param.name for param in endpoint.parameters}
            properties = endpoint.input_schema.get("properties", {})
            if isinstance(properties, dict):
                declared.update(properties)
            if not set(approved) <= declared:
                raise ValueError("E1 host input is not source-declared")
            validate_json_schema_value(
                approved, effective_input_schema(endpoint), context="E1 scenario input",
            )
        # This runs the genuine original direct P2 compiler, not a surrogate
        # query/field matcher or a synthetic execution plan.
        checked_plan = compile_paper_understood_direct_plan(
            view.router, PaperUnderstanding(
                intent_id=case.intent_id,
                concept_ids=(case.concept_id,),
                named_tools=(tool_name,),
            ), principal=view._principal, catalog=catalog,
            intent_registry=intent_registry, index=index,
            host_source_arguments=host_inputs,
        )
        if (
            checked_plan.status != "ready"
            or len(checked_plan.calls) != 1
            or checked_plan.calls[0].route_id != case.route_id
            or checked_plan.bindings
        ):
            raise ValueError("E1 original P2 source direct plan not ready")
        original_cases.append((case, approved))
        registered_source_types.append(tool.source_type)
        check_matrix_source()
    # All of the trusted scenario manifest is valid before any model/tool.
    pinned_inputs = tuple(deepcopy(inputs) for _, inputs in original_cases)
    receipts: list[PaperScopedNativeDirectE1] = []
    for i, (case, approved) in enumerate(original_cases):
        check_matrix_source()
        if any(other.host_arguments != saved
               for (other, _), saved in zip(original_cases, pinned_inputs, strict=True)):
            raise PolicyViolationError("E1 native host scenario inputs changed")
        decision, receipt = await run_paper_scoped_native_direct_e1(
            case.model, case.agent,
            view=view, index=index, catalog=catalog,
            intent_registry=intent_registry,
            model_visible_intent_ids=(case.intent_id,),
            model_visible_concept_ids=(case.concept_id,),
            expected_route_id=case.route_id,
            host_source_arguments=({case.route_id: deepcopy(approved)}
                                   if approved is not None else None),
        )
        if decision != "offer" or receipt is None or receipt.route_id != case.route_id:
            raise ValueError(f"E1 native source case {i} direct selection abstained")
        check_matrix_source()
        receipts.append(receipt)
    check_matrix_source()
    return PaperHeterogeneousNativeE1(
        receipts=tuple(receipts),
        executed_routes=tuple(item.route_id for item in receipts),
        registered_source_types=tuple(registered_source_types),
        heterogeneous_sources=len(set(registered_source_types)) > 1,
        host_bound_tool_calls=sum(item.host_bound_tool_calls for item in receipts),
    )
