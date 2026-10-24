"""Opt-in Algorithm 1 ToolCall recipe from proved original required-field routes.

This compiles *field and argument-dependency metadata*, never executes calls
or substitutes graph edges for observed output values or host authorization.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import TYPE_CHECKING, Any, Literal

from .authorization import PrincipalContext
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError
from .field_group_retrieval import _root_envelope_empty
from .host_field_contract import _policy_contents_digest
from .models import ToolCall
from .native_graph_index import NativeSchemaGraphIndex, _host_source_input_names
from .paper_field_retrieval import retrieve_paper_field_coverage
from .validation import effective_input_schema, validate_json_schema_value

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class PaperFieldArgumentDependency:
    """An UNBOUND original producer output needed by a later call."""

    consumer_call_index: int
    parameter: str
    producer_call_index: int
    producer_field: str


@dataclass(frozen=True, slots=True)
class PaperFieldCallAlternative:
    """Ordered source-native ToolCalls plus unresolved typed dependencies."""

    calls: tuple[ToolCall, ...]
    dependencies: tuple[PaperFieldArgumentDependency, ...]
    required_semantic_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PaperFieldToolCallPlan:
    """Host-only recipe, not an ExecutionPlan or an execution grant."""

    status: Literal[
        "complete", "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
    ]
    snapshot_id: str
    registry_version: int
    requested_k: int
    alternatives: tuple[PaperFieldCallAlternative, ...] = ()
    independent_quality_evidence: bool = False
    executable_authority: bool = False


def compile_paper_field_toolcalls(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    k: int = 5,
) -> PaperFieldToolCallPlan:
    """Project a fresh P1 proof onto existing ``ToolCall`` contracts.

    Input-free roots need no arguments. Explicitly approved typed G5 source
    roots expose missing host inputs, never guessed values; graph consumers
    must wait for original producer observations.
    A returned ToolCall is descriptive: the existing executor still owns
    authorization, validation, budgets, and any later invocation.
    """
    witness = router._retrieval_authority_witness()
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("original ToolCall source authorization changed")
    policy_digest = _policy_contents_digest(policy)
    try:
        principal_digest = principal.model_dump_json()
        catalog_digest = catalog.model_dump_json()
    except (TypeError, ValueError, OverflowError, AttributeError):
        raise PolicyViolationError("invalid original ToolCall owner declaration") from None
    proof = retrieve_paper_field_coverage(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if proof.registry_version != witness[1]:
        raise PolicyViolationError("original ToolCall source revision changed")
    permitted = router._authorization_predicate(principal)
    if permitted is None:
        raise PolicyViolationError("original ToolCall source authorization missing")

    alternatives: list[PaperFieldCallAlternative] = []
    try:
        for alternative in proof.alternatives:
            route_indexes = {
                route.route_id: position
                for position, route in enumerate(alternative.routes)
            }
            if len(route_indexes) != len(alternative.routes):
                raise PolicyViolationError("duplicate original ToolCall route")
            calls: list[ToolCall] = []
            deps: list[PaperFieldArgumentDependency] = []
            for position, route in enumerate(alternative.routes):
                location = index.field_index.route_locations.get(route.route_id)
                if location is None:
                    raise PolicyViolationError("original ToolCall route missing")
                tool = router.registry.get(location[0])
                endpoint = tool.endpoint(location[1])
                if (
                    (tool.fingerprint, endpoint.fingerprint) != (
                        route.tool_fingerprint, route.endpoint_fingerprint,
                    )
                    or not permitted(tool, endpoint)
                    or endpoint.read_only is not True
                    or endpoint.destructive is True
                ):
                    raise PolicyViolationError("original ToolCall source changed")
                availability = router.planner.availability_predicate
                if availability is not None and not availability(tool, endpoint):
                    raise PolicyViolationError("original ToolCall source unavailable")
                visible = router._data_scope_endpoint_view(principal, tool, endpoint)
                if visible is None:
                    raise PolicyViolationError("original ToolCall source hidden")
                visible_fields = {field.name for field in visible.output_fields}
                if (
                    not route.output_fields
                    or len(set(route.output_fields)) != len(route.output_fields)
                    or not set(route.output_fields).issubset(visible_fields)
                ):
                    raise PolicyViolationError("original ToolCall output hidden")

                bound_parameters: set[str] = set()
                declared_parameters = {param.name: param for param in visible.parameters}
                for parameter, producer_id, producer_field in route.input_bindings:
                    producer_position = route_indexes.get(producer_id)
                    if (
                        producer_position is None
                        or producer_position >= position
                        or parameter in bound_parameters
                        or parameter not in declared_parameters
                        or producer_field not in alternative.routes[
                            producer_position
                        ].output_fields
                    ):
                        raise PolicyViolationError("original ToolCall dependency invalid")
                    bound_parameters.add(parameter)
                    deps.append(PaperFieldArgumentDependency(
                        consumer_call_index=position,
                        parameter=parameter,
                        producer_call_index=producer_position,
                        producer_field=producer_field,
                    ))
                required_parameters = {
                    parameter.name for parameter in visible.parameters
                    if parameter.required
                }
                if position == 0:
                    if route.input_bindings:
                        raise PolicyViolationError("original ToolCall root bound to source")
                    if _root_envelope_empty(endpoint):
                        missing_parameters: set[str] = set()
                    else:
                        approved = _host_source_input_names(endpoint)
                        if (
                            route.route_id not in index.approved_host_roots
                            or approved is None
                            or set(approved) != required_parameters
                        ):
                            raise PolicyViolationError(
                                "original ToolCall root inputs not host approved"
                            )
                        missing_parameters = set(approved)
                elif required_parameters != bound_parameters:
                    raise PolicyViolationError("original ToolCall required input unbound")
                else:
                    missing_parameters = bound_parameters
                # No argument value has been observed. Even a technically
                # optional graph-bound input is unresolved in this recipe.
                calls.append(ToolCall(
                    tool=tool.key,
                    endpoint=endpoint.name,
                    arguments={},
                    fields=list(route.output_fields),
                    evidence=router.planner._evidence(
                        tool, visible, list(route.output_fields),
                    ),
                    schema_fingerprint=endpoint.fingerprint,
                    tool_fingerprint=tool.fingerprint,
                    missing_required_arguments=sorted(missing_parameters),
                ))
            alternatives.append(PaperFieldCallAlternative(
                calls=tuple(calls), dependencies=tuple(deps),
                required_semantic_ids=alternative.required_semantic_ids,
            ))

        # The second proof checks the same entire original route set, current
        # source-visible projection, policy, data scope, health and catalog.
        # A different observation is a failure, never an updated best effort.
        renewed = retrieve_paper_field_coverage(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        )
        index.field_index._assert_source(router)
        router._check_retrieval_authority_witness(witness)
        if (
            renewed != proof
            or router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or principal.model_dump_json() != principal_digest
            or catalog.model_dump_json() != catalog_digest
        ):
            raise PolicyViolationError("original ToolCall proof changed")
    except Exception:
        # Original provider callbacks may contain route/private-field text.
        raise PolicyViolationError("original ToolCall source eligibility changed") from None

    return PaperFieldToolCallPlan(
        status=proof.status,
        snapshot_id=proof.snapshot_id,
        registry_version=proof.registry_version,
        requested_k=proof.requested_k,
        alternatives=tuple(alternatives),
    )


def bind_paper_field_host_inputs(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    plan: PaperFieldToolCallPlan,
    alternative_index: int,
    host_arguments: dict[str, Any],
    k: int = 5,
) -> PaperFieldToolCallPlan:
    """Validate owner-approved root inputs without binding dependent calls.

    The host supplies every value explicitly. No provider call is made and
    this immutable *outer* receipt is never an executor authorization token.
    This does not resolve producer-output dependencies or make the whole
    alternative executable. The existing executor still validates live
    policy, scope, parameters and source fingerprints at invocation time.
    """
    try:
        original = compile_paper_field_toolcalls(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        )
        if (
            type(plan) is not PaperFieldToolCallPlan
            or plan != original
            or original.status != "complete"
            or type(alternative_index) is not int
            or not 0 <= alternative_index < len(original.alternatives)
            or type(host_arguments) is not dict
        ):
            raise PolicyViolationError("untrusted original ToolCall input receipt")
        alternative = original.alternatives[alternative_index]
        root = alternative.calls[0]
        route_id = f"{root.tool}.{root.endpoint}"
        endpoint = router.registry.get(root.tool).endpoint(root.endpoint)
        approved = _host_source_input_names(endpoint)
        if (
            route_id not in index.approved_host_roots
            or approved is None
            or not approved
            or set(root.missing_required_arguments) != set(approved)
            or set(host_arguments) != set(approved)
        ):
            raise PolicyViolationError("unapproved original ToolCall input contract")

        # Use the *original* owner schema, never a synthetic/scoped one.
        # Exact-key and typed validation rejects guessed, partial, optional,
        # unknown and incorrectly typed input values before publication.
        # The G5 root envelope permits only scalar host values; isolate them
        # from caller mutation before any owner/probe callbacks can run.
        validated_arguments = dict(host_arguments)
        for parameter in endpoint.parameters:
            value = validated_arguments[parameter.name]
            kind = parameter.json_schema["type"]
            valid = (
                (kind == "string" and type(value) is str)
                or (kind == "integer" and type(value) is int)
                or (kind == "number" and type(value) in {int, float})
                or (kind == "boolean" and type(value) is bool)
            )
            if not valid or (type(value) is float and not isfinite(value)):
                raise PolicyViolationError("non-JSON original ToolCall host input")
        validate_json_schema_value(
            validated_arguments, effective_input_schema(endpoint),
            context="original ToolCall host arguments",
        )
        scoped_root = root.model_copy(deep=True)
        scoped_root.arguments = validated_arguments
        scoped_root.missing_required_arguments = []
        policy = router.authorization_policy
        if policy is None:
            raise PolicyViolationError("original ToolCall input authorization missing")
        policy.validate(
            principal, router.registry.get(root.tool), endpoint, scoped_root,
        )
        # Verify the whole proof/source/permission surface once more after
        # validation, since external callbacks may revoke owner contracts.
        if compile_paper_field_toolcalls(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        ) != original or host_arguments != validated_arguments:
            raise PolicyViolationError("original ToolCall input proof changed")

        updated: list[PaperFieldCallAlternative] = []
        for position, item in enumerate(original.alternatives):
            copies = [call.model_copy(deep=True) for call in item.calls]
            if position == alternative_index:
                copies[0].arguments = validated_arguments
                copies[0].missing_required_arguments = []
            updated.append(replace(item, calls=tuple(copies)))
        return replace(original, alternatives=tuple(updated))
    except Exception:
        # Do not leak source-private route names or rejected user values.
        raise PolicyViolationError("original ToolCall host input binding rejected") from None
