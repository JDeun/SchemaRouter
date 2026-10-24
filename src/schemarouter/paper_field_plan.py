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
from .executor import _MISSING, RegistryExecutor
from .field_group_retrieval import _root_envelope_empty
from .host_field_contract import _policy_contents_digest
from .models import ToolCall, ToolResult
from .native_graph_index import NativeSchemaGraphIndex, _host_source_input_names
from .paper_field_retrieval import retrieve_paper_field_coverage
from .validation import (
    canonical_field_value_schema,
    effective_input_schema,
    validate_json_schema_value,
)

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
class PaperFieldOutputMetadata:
    """Original AttachMeta declarations for one scoped, selected output field.

    These are source-declared contracts, NOT an observed result, a verified
    license grant, or independently established provenance.
    """

    call_index: int
    field_name: str
    semantic_id: str | None
    source_unit: str | None
    declared_result_unit: str | None
    dimension: str | None
    tool_source_type: str | None
    tool_license: str | None
    field_source_type: str | None
    field_license: str | None
    provider: str | None
    qualifiers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class PaperFieldCallAlternative:
    """Ordered source-native ToolCalls plus unresolved typed dependencies."""

    calls: tuple[ToolCall, ...]
    dependencies: tuple[PaperFieldArgumentDependency, ...]
    required_semantic_ids: tuple[str, ...]
    field_metadata: tuple[PaperFieldOutputMetadata, ...] = ()


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
    scoped_tools: dict[str, bool] = {}
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
            field_metadata: list[PaperFieldOutputMetadata] = []
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
                visible_fields = {field.name: field for field in visible.output_fields}
                if (
                    not route.output_fields
                    or len(set(route.output_fields)) != len(route.output_fields)
                    or not set(route.output_fields).issubset(visible_fields)
                ):
                    raise PolicyViolationError("original ToolCall output hidden")

                # AttachMeta comes exclusively from the SAME live, scoped
                # FieldSpecs as the proved ToolCall.fields. Never rehydrate
                # broader endpoint metadata or infer a missing unit/license.
                # The analyzer suppresses shared tool provenance when ANY
                # authorized sibling endpoint is scoped. A direct route can
                # be fully visible while its sibling forbids labels echoed
                # in the provider/license fields. Mirror that tool boundary.
                if tool.key not in scoped_tools:
                    restricted = False
                    for sibling in tool.endpoints:
                        if not permitted(tool, sibling):
                            continue
                        sibling_view = router._data_scope_endpoint_view(
                            principal, tool, sibling,
                        )
                        if sibling_view is not None and sibling_view is not sibling:
                            restricted = True
                            break
                    scoped_tools[tool.key] = restricted
                scoped = scoped_tools[tool.key]
                for name in route.output_fields:
                    field = visible_fields[name]
                    normalization = field.unit_normalization
                    field_metadata.append(PaperFieldOutputMetadata(
                        call_index=position,
                        field_name=name,
                        semantic_id=field.semantic_id,
                        source_unit=field.unit,
                        declared_result_unit=(
                            normalization.canonical_unit if normalization else field.unit
                        ),
                        dimension=normalization.dimension if normalization else None,
                        tool_source_type=None if scoped else tool.source_type,
                        tool_license=None if scoped else tool.license,
                        field_source_type=field.source_type,
                        field_license=field.license,
                        provider=None if scoped else tool.provider,
                        qualifiers=tuple(sorted(field.qualifiers.items())),
                    ))

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
                field_metadata=tuple(field_metadata),
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


def bind_paper_field_producer_result(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    plan: PaperFieldToolCallPlan,
    alternative_index: int,
    producer_call_index: int,
    executed_call: ToolCall,
    result: ToolResult,
    k: int = 5,
) -> PaperFieldToolCallPlan:
    """Bind a host-supplied producer observation into dependent ToolCalls.

    The host MUST supply a result obtained from execution of ``executed_call``
    under the existing executor's authorization and budget controls. This
    method verifies the result's declared projection and value contracts, but
    cannot authenticate where a host-provided object was obtained. It never
    invokes a tool or grants execution authority. Only original one-hop
    dependencies (including same-root forks) are supported.
    """
    try:
        witness = router._retrieval_authority_witness()
        entry_policy = router.authorization_policy
        if entry_policy is None:
            raise PolicyViolationError("missing original producer authorization")
        policy_digest = _policy_contents_digest(entry_policy)
        principal_digest = principal.model_dump_json()
        catalog_digest = catalog.model_dump_json()
        original = compile_paper_field_toolcalls(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        )
        if (
            type(plan) is not PaperFieldToolCallPlan
            or original.status != "complete"
            or type(alternative_index) is not int
            or not 0 <= alternative_index < len(original.alternatives)
            or type(producer_call_index) is not int
            or type(executed_call) is not ToolCall
            or type(result) is not ToolResult
        ):
            raise PolicyViolationError("invalid original producer observation")

        # A root may already carry explicit host-approved inputs. Reconstruct
        # that receipt using the public authorizing binder, then reject every
        # other prebound or caller-modified call/alternative.
        expected = original
        submitted_root = plan.alternatives[alternative_index].calls[0]
        original_root = original.alternatives[alternative_index].calls[0]
        if submitted_root != original_root:
            if not original_root.missing_required_arguments:
                raise PolicyViolationError("untrusted original input receipt")
            expected = bind_paper_field_host_inputs(
                router, query, principal=principal, catalog=catalog, index=index,
                plan=original, alternative_index=alternative_index,
                host_arguments=dict(submitted_root.arguments), k=k,
            )
        if plan != expected:
            raise PolicyViolationError("original input receipt changed")

        alternative = expected.alternatives[alternative_index]
        dependencies = tuple(
            dep for dep in alternative.dependencies
            if dep.producer_call_index == producer_call_index
        )
        if (
            not dependencies
            or not 0 <= producer_call_index < len(alternative.calls)
            or any(dep.consumer_call_index <= producer_call_index for dep in dependencies)
            or any(dep.producer_call_index != producer_call_index
                   for dep in alternative.dependencies)
        ):
            raise PolicyViolationError("unsupported original producer dependency")

        producer = alternative.calls[producer_call_index]
        if (
            not producer.executable
            or executed_call != producer
            or result.tool != producer.tool
            or result.endpoint != producer.endpoint
            or result.projected_fields != producer.fields
        ):
            raise PolicyViolationError("unmatched original producer execution")

        producer_tool = router.registry.get(producer.tool)
        producer_endpoint = producer_tool.endpoint(producer.endpoint)
        policy = entry_policy
        policy.validate(principal, producer_tool, producer_endpoint, producer)

        # A selected field is not evidence of a present result. Recompute
        # executor-native metadata from the actual projected response; neither
        # user-declared metadata nor a structural graph edge can supply a value.
        observation = result.model_copy(deep=True)
        actual_contracts = RegistryExecutor._result_field_contracts(
            producer.fields, producer_endpoint, observation.data,
        )
        if observation.field_contracts != actual_contracts:
            raise PolicyViolationError("unmatched original result field contracts")

        updated_calls = [call.model_copy(deep=True) for call in alternative.calls]
        for dep in dependencies:
            field = next(
                (item for item in producer_endpoint.output_fields
                 if item.name == dep.producer_field), None,
            )
            contract = actual_contracts.get(dep.producer_field)
            if field is None or contract is None or contract.has_observed_value is not True:
                raise PolicyViolationError("original producer field unobserved")

            value = RegistryExecutor._extract_projection_path(
                observation.data, field.result_projection_path,
            )
            # Bound identifiers are a single native JSON scalar, not a list,
            # null, container, arbitrary Python object, or a NaN/Infinity.
            if (
                value is _MISSING or value is None
                or type(value) not in {str, int, float, bool}
                or (type(value) is float and not isfinite(value))
            ):
                raise PolicyViolationError("non-scalar original producer value")
            validate_json_schema_value(
                value, canonical_field_value_schema(
                    producer_endpoint, dep.producer_field,
                ), context="original producer observed value",
            )

            consumer = updated_calls[dep.consumer_call_index]
            consumer_tool = router.registry.get(consumer.tool)
            consumer_endpoint = consumer_tool.endpoint(consumer.endpoint)
            parameter = next(
                (item for item in consumer_endpoint.parameters
                 if item.name == dep.parameter), None,
            )
            if (
                parameter is None
                or dep.parameter not in consumer.missing_required_arguments
                or dep.parameter in consumer.arguments
            ):
                raise PolicyViolationError("original consumer input not unresolved")
            validate_json_schema_value(
                value, parameter.json_schema,
                context="original consumer bound parameter",
            )
            consumer.arguments[dep.parameter] = value
            consumer.missing_required_arguments.remove(dep.parameter)

        for dep in dependencies:
            consumer = updated_calls[dep.consumer_call_index]
            if consumer.missing_required_arguments:
                raise PolicyViolationError("incomplete original consumer binding")
            tool = router.registry.get(consumer.tool)
            endpoint = tool.endpoint(consumer.endpoint)
            validate_json_schema_value(
                consumer.arguments, effective_input_schema(endpoint),
                context="original consumer bound arguments",
            )
            policy.validate(principal, tool, endpoint, consumer)

        # No stale policy, owner catalog, source, or caller mutation may be
        # quietly accepted after the output/value validation callbacks.
        if (
            compile_paper_field_toolcalls(
                router, query, principal=principal, catalog=catalog, index=index,
                k=k,
            ) != original
            or plan != expected
            or executed_call != producer
            or result != observation
            or router.authorization_policy is not entry_policy
            or _policy_contents_digest(entry_policy) != policy_digest
            or principal.model_dump_json() != principal_digest
            or catalog.model_dump_json() != catalog_digest
        ):
            raise PolicyViolationError("original producer observation drifted")
        router._check_retrieval_authority_witness(witness)

        alternatives = list(expected.alternatives)
        alternatives[alternative_index] = replace(
            alternative, calls=tuple(updated_calls),
        )
        return replace(expected, alternatives=tuple(alternatives))
    except Exception:
        raise PolicyViolationError("original producer result binding rejected") from None
