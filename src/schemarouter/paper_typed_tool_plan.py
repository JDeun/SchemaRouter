"""Opt-in Algorithm 1 field receipts compiled into non-executing typed calls.

This is a *planning diagnostic*, not an ExecutionPlan or an execution grant.
In particular, a dependent call never receives a fabricated producer ID.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError
from .evidence import available_evidence
from .host_field_contract import _policy_contents_digest
from .models import EndpointSpec, ToolCall, ToolSpec
from .native_graph_index import NativeSchemaGraphIndex, _native_required_inputs
from .paper_field_retrieval import PaperFieldRoute, retrieve_paper_field_coverage

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class PaperPlanBinding:
    """An unmaterialized original output -> required input dependency."""

    consumer_call_index: int
    parameter: str
    producer_call_index: int
    producer_field: str


@dataclass(frozen=True, slots=True)
class PaperPlanFieldMeta:
    """Field metadata copied only from the currently scoped source view."""

    name: str
    semantic_id: str | None
    unit: str | None
    source_type: str | None
    license: str | None
    qualifiers: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class PaperPlanCall:
    """One original route and its standard, explicitly incomplete ToolCall."""

    route_id: str
    call: ToolCall
    source_type: str | None
    license: str | None
    fields_meta: tuple[PaperPlanFieldMeta, ...]


@dataclass(frozen=True, slots=True)
class PaperTypedToolPlan:
    """Non-executable planning receipt; never pass it to SchemaRouter.execute."""

    status: Literal[
        "ready", "requires_arguments", "requires_observation",
        "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
    ]
    snapshot_id: str
    registry_version: int
    requested_k: int
    calls: tuple[PaperPlanCall, ...] = ()
    bindings: tuple[PaperPlanBinding, ...] = ()
    executable_authority: bool = False


def compile_paper_typed_tool_plan(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    alternative_index: int = 0,
    k: int = 5,
) -> PaperTypedToolPlan:
    """Compile ONE source-proven K5 alternative without executing or binding data.

    `ready` means the typed shape has no missing arguments; it is NOT an
    authorization decision. Actual values, tool calls and evidence must still
    pass the ordinary executor's current security and validation boundaries.
    """
    if type(alternative_index) is not int or alternative_index < 0:
        raise ValueError("invalid paper alternative index")
    proof = retrieve_paper_field_coverage(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if proof.status != "complete":
        if alternative_index:
            raise ValueError("paper alternative index is out of range")
        return PaperTypedToolPlan(
            status=proof.status,
            snapshot_id=proof.snapshot_id,
            registry_version=proof.registry_version,
            requested_k=proof.requested_k,
        )
    if alternative_index >= len(proof.alternatives):
        raise ValueError("paper alternative index is out of range")

    chosen = proof.alternatives[alternative_index]
    if len(chosen.routes) > k or len({r.route_id for r in chosen.routes}) != len(chosen.routes):
        raise PolicyViolationError("paper typed plan has invalid original routes")

    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper typed plan requires original source policy")
    witness = router._retrieval_authority_witness()
    policy_digest = _policy_contents_digest(policy)
    declared_principal = principal.model_dump_json()
    declared_catalog = catalog.model_dump_json()
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("paper typed plan requires original source policy")

    positions = {route.route_id: i for i, route in enumerate(chosen.routes)}
    receipts_by_route = {route.route_id: route for route in chosen.routes}
    calls: list[PaperPlanCall] = []
    edges: list[PaperPlanBinding] = []
    try:
        for i, route in enumerate(chosen.routes):
            calls.append(_compile_one_route(
                router, principal, index, route, i, positions,
                receipts_by_route, edges, permitted,
            ))
        # End-of-compilation second observation of the SAME complete proof,
        # not a substitute for atomic provider snapshots or execution checks.
        if retrieve_paper_field_coverage(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        ) != proof:
            raise PolicyViolationError("paper field proof changed during compilation")
    except Exception:
        # A data scope / health / host callback may include private diagnostics.
        raise PolicyViolationError("paper typed plan source eligibility changed") from None

    index.field_index._assert_source(router)
    router._check_retrieval_authority_witness(witness)
    if (
        router.authorization_policy is None
        or _policy_contents_digest(router.authorization_policy) != policy_digest
        or principal.model_dump_json() != declared_principal
        or catalog.model_dump_json() != declared_catalog
    ):
        raise PolicyViolationError("paper typed plan source declaration changed")

    status = (
        "requires_observation" if edges else
        "requires_arguments" if any(
            item.call.missing_required_arguments for item in calls
        ) else "ready"
    )
    return PaperTypedToolPlan(
        status=status,
        snapshot_id=proof.snapshot_id,
        registry_version=proof.registry_version,
        requested_k=k,
        calls=tuple(calls),
        bindings=tuple(edges),
    )


def _compile_one_route(
    router: SchemaRouter,
    principal: PrincipalContext,
    index: NativeSchemaGraphIndex,
    route: PaperFieldRoute,
    position: int,
    positions: dict[str, int],
    receipts_by_route: dict[str, PaperFieldRoute],
    edges: list[PaperPlanBinding],
    permitted: Callable[[ToolSpec, EndpointSpec], bool],
) -> PaperPlanCall:
    location = index.field_index.route_locations.get(route.route_id)
    if location is None:
        raise PolicyViolationError("paper typed route missing from original source")
    tool = router.registry.get(location[0])
    endpoint = tool.endpoint(location[1])
    if (
        (tool.fingerprint, endpoint.fingerprint)
        != (route.tool_fingerprint, route.endpoint_fingerprint)
        or index.field_index.route_fingerprints.get(route.route_id)
        != (route.tool_fingerprint, route.endpoint_fingerprint)
        or not permitted(tool, endpoint)
        or endpoint.read_only is not True
        or endpoint.destructive is True
    ):
        raise PolicyViolationError("paper typed route is not currently permitted")
    availability = router.planner.availability_predicate
    if availability is not None and not availability(tool, endpoint):
        raise PolicyViolationError("paper typed route is currently unavailable")
    visible = router._data_scope_endpoint_view(principal, tool, endpoint)
    if visible is None:
        raise PolicyViolationError("paper typed route has no currently visible fields")
    visible_names = {field.name for field in visible.output_fields}
    if not route.output_fields or not set(route.output_fields).issubset(visible_names):
        raise PolicyViolationError("paper typed route exposes an invisible field")
    selected = set(route.output_fields)
    metadata = tuple(PaperPlanFieldMeta(
        name=f.name,
        semantic_id=f.semantic_id,
        unit=f.unit,
        source_type=f.source_type or tool.source_type,
        license=f.license or tool.license,
        qualifiers=tuple(sorted(f.qualifiers.items())),
    ) for f in visible.output_fields if f.name in selected)
    if len(metadata) != len(route.output_fields):
        raise PolicyViolationError("paper typed route field metadata incomplete")

    input_names = {param.name for param in endpoint.parameters}
    required_names = {
        param.name for param in endpoint.parameters if param.required
    }
    required_names.update(endpoint.input_schema.get("required", []))
    if (
        not required_names.issubset(input_names)
        or not required_names.issubset({p.name for p in visible.parameters})
    ):
        raise PolicyViolationError("paper typed route has unknown required inputs")

    if route.input_bindings:
        original_inputs = _native_required_inputs(endpoint)
        bindings = {param: (from_route, source_field)
                    for param, from_route, source_field in route.input_bindings}
        if (
            original_inputs is None
            or len(bindings) != len(route.input_bindings)
            or set(bindings) != {name for name, _ in original_inputs}
            or set(bindings) != required_names
        ):
            raise PolicyViolationError("paper typed route lacks exact source bindings")
        for name, from_route, field in route.input_bindings:
            earlier = positions.get(from_route)
            producer = receipts_by_route.get(from_route)
            if (
                earlier is None or earlier >= position or producer is None
                or field not in producer.output_fields
            ):
                raise PolicyViolationError("paper typed route depends on future producer")
            edges.append(PaperPlanBinding(
                consumer_call_index=position, parameter=name,
                producer_call_index=earlier, producer_field=field,
            ))
    else:
        bindings = {}

    return PaperPlanCall(
        route_id=route.route_id,
        call=ToolCall(
            tool=location[0], endpoint=location[1], arguments={},
            fields=list(route.output_fields),
            evidence=available_evidence(tool, visible, list(route.output_fields)),
            schema_fingerprint=route.endpoint_fingerprint,
            tool_fingerprint=route.tool_fingerprint,
            missing_required_arguments=sorted(required_names),
        ),
        source_type=tool.source_type,
        license=tool.license,
        fields_meta=metadata,
    )
