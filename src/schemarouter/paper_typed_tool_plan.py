"""Opt-in Algorithm 1 field receipts compiled into non-executing typed calls.

This is a *planning diagnostic*, not an ExecutionPlan or an execution grant.
In particular, a dependent call never receives a fabricated producer ID.
"""
from __future__ import annotations

import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from .authorization import PrincipalContext
from .canonical_json import canonical_json_bytes
from .concept_retrieval import NativeConceptCatalog
from .errors import PolicyViolationError
from .evidence import available_evidence
from .field_group_retrieval import _response_contract, _scalar_contract
from .host_field_contract import _policy_contents_digest
from .models import EndpointSpec, PlanCoverage, ToolCall, ToolSpec
from .native_graph_index import (
    NativeSchemaGraphIndex,
    _host_source_input_names,
    _native_required_inputs,
)
from .paper_field_retrieval import PaperFieldRoute, retrieve_paper_field_coverage
from .validation import canonical_unit_value_schema, validate_json_schema_value

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
    """Current scoped paths/contracts; policy may flatten or redact source metadata."""

    name: str
    semantic_id: str | None
    source_unit: str | None
    unit: str | None
    source_type: str | None
    license: str | None
    qualifiers: tuple[tuple[str, str], ...]
    source_path: tuple[str, ...] = ()
    result_path: tuple[str, ...] = ()
    json_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaperPlanParameterMeta:
    """Minimal current-source input shape; no raw provider annotations.

    `json_types` is a conservative label tuple, not an executable schema.
    Empty means the source has no safely exposable basic JSON type label.
    """

    name: str
    required: bool
    location: str
    json_types: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PaperPlanCall:
    """One original route and its standard, explicitly incomplete ToolCall."""

    route_id: str
    call: ToolCall
    source_type: str | None
    license: str | None
    fields_meta: tuple[PaperPlanFieldMeta, ...]
    parameters_meta: tuple[PaperPlanParameterMeta, ...] = ()
    # Validated model proposals, NOT ToolCall.arguments or permission.
    parameter_proposals: tuple[tuple[str, Any], ...] = field(
        default=(), repr=False,
    )


@dataclass(frozen=True, slots=True)
class PaperTypedToolPlan:
    """Non-executable planning receipt; never pass it to SchemaRouter.execute."""

    status: Literal[
        "ready", "requires_arguments", "requires_observation",
        "no_proven_hit", "over_k_unranked", "budget_unsatisfied",
        "ambiguous_paths",
    ]
    snapshot_id: str
    registry_version: int
    requested_k: int
    calls: tuple[PaperPlanCall, ...] = ()
    bindings: tuple[PaperPlanBinding, ...] = ()
    executable_authority: bool = False
    ranked_unverified: bool = False
    coverage: PlanCoverage | None = None
    understanding_hints: dict[str, Any] | None = field(default=None, compare=False)


def compile_paper_typed_tool_plan(
    router: SchemaRouter,
    query: str,
    *,
    principal: PrincipalContext,
    catalog: NativeConceptCatalog,
    index: NativeSchemaGraphIndex,
    alternative_index: int = 0,
    k: int = 5,
    host_source_arguments: dict[str, dict[str, Any]] | None = None,
) -> PaperTypedToolPlan:
    """Compile ONE source-proven K5 alternative without executing or binding data.

    `ready` means the typed shape has no missing arguments; it is NOT an
    authorization decision. Actual values, tool calls and evidence must still
    pass the ordinary executor's current security and validation boundaries.
    """
    if type(alternative_index) is not int or alternative_index < 0:
        raise ValueError("invalid paper alternative index")
    if host_source_arguments is not None and (
        type(host_source_arguments) is not dict
        or any(
            type(route) is not str or type(values) is not dict
            for route, values in host_source_arguments.items()
        )
    ):
        raise ValueError("invalid explicit host source argument declaration")
    host_inputs = {
        route: dict(values) for route, values in (host_source_arguments or {}).items()
    }
    proof = retrieve_paper_field_coverage(
        router, query, principal=principal, catalog=catalog, index=index, k=k,
    )
    if proof.status != "complete":
        if host_inputs:
            raise ValueError("explicit host arguments require a proven source route")
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
    if not host_inputs.keys() <= positions.keys():
        raise ValueError("explicit host arguments name an unproved source route")
    receipts_by_route = {route.route_id: route for route in chosen.routes}
    calls: list[PaperPlanCall] = []
    edges: list[PaperPlanBinding] = []
    try:
        for i, route in enumerate(chosen.routes):
            calls.append(_compile_one_route(
                router, principal, index, route, i, positions,
                receipts_by_route, edges, permitted, host_inputs.get(route.route_id),
            ))
        _check_current_call_scopes(router, principal, calls)
        # End-of-compilation second observation of the SAME complete proof,
        # not a substitute for atomic provider snapshots or execution checks.
        if retrieve_paper_field_coverage(
            router, query, principal=principal, catalog=catalog, index=index, k=k,
        ) != proof:
            raise PolicyViolationError("paper field proof changed during compilation")
        # The P1 proof rechecks visible OUTPUTS, not argument-specific scope.
        # Re-evaluate the actual typed calls after the final source observation.
        _check_current_call_scopes(router, principal, calls)
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


def _check_current_call_scopes(
    router: SchemaRouter,
    principal: PrincipalContext,
    calls: list[PaperPlanCall],
) -> None:
    """Reapply the executor's call-specific data-scope preflight to receipts."""
    policy = router.authorization_policy
    if policy is None:
        raise PolicyViolationError("paper typed call lost its source policy")
    for item in calls:
        tool = router.registry.get(item.call.tool)
        endpoint = tool.endpoint(item.call.endpoint)
        if (
            tool.fingerprint != item.call.tool_fingerprint
            or endpoint.fingerprint != item.call.schema_fingerprint
        ):
            raise PolicyViolationError("paper typed call source fingerprint changed")
        visible = router._data_scope_endpoint_view(principal, tool, endpoint)
        if visible is None:
            raise PolicyViolationError("paper typed call source scope hidden")
        if item.parameters_meta != _paper_public_parameters(visible):
            raise PolicyViolationError("paper typed call parameter scope changed")
        policy.validate_data_scope(principal, tool, endpoint, item.call)
        if item.call.arguments:
            validate_json_schema_value(
                item.call.arguments, visible.input_schema,
                context="original paper current scoped host inputs",
            )


_SAFE_JSON_TYPES = frozenset({
    "array", "boolean", "integer", "null", "number", "object", "string",
})


def _paper_public_parameters(
    visible: EndpointSpec,
) -> tuple[PaperPlanParameterMeta, ...]:
    """Project only safe type labels from the current scoped endpoint.

    Never copy provider JSON Schema, wire/header aliases, semantic IDs,
    enums, defaults, descriptions or nested metadata into public receipts.
    """
    declared_required = visible.input_schema.get("required", ())
    required = (
        set(declared_required)
        if type(declared_required) in (list, tuple)
        else set()
    )
    projected: list[PaperPlanParameterMeta] = []
    seen: set[str] = set()
    for parameter in visible.parameters:
        if parameter.name in seen:
            raise PolicyViolationError("duplicate original paper input parameter")
        seen.add(parameter.name)
        raw_type = parameter.json_schema.get("type")
        if type(raw_type) is str and raw_type in _SAFE_JSON_TYPES:
            json_types = (raw_type,)
        elif (
            type(raw_type) is list
            and 1 <= len(raw_type) <= len(_SAFE_JSON_TYPES)
            and all(type(item) is str and item in _SAFE_JSON_TYPES
                    for item in raw_type)
        ):
            json_types = tuple(dict.fromkeys(raw_type))
        else:
            json_types = ()
        projected.append(PaperPlanParameterMeta(
            name=parameter.name,
            required=parameter.required or parameter.name in required,
            location=parameter.location,
            json_types=json_types,
        ))
    return tuple(projected)


def _bounded_parameter_value(value: Any, *, string_limit: int = 4096) -> bool:
    """Small strict JSON values, never a transport or execution permission."""
    nodes = 0

    def walk(item: Any, depth: int) -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > 128 or depth > 4:
            return False
        if type(item) is str:
            return len(item.encode("utf-8")) <= string_limit
        if type(item) is bool:
            return True
        if type(item) is int:
            return -(2**63) <= item < 2**63
        if type(item) is float:
            return math.isfinite(item)
        if type(item) is list:
            return len(item) <= 32 and all(walk(child, depth + 1) for child in item)
        if type(item) is dict:
            return len(item) <= 32 and all(
                type(key) is str and 1 <= len(key) <= 160
                and not any(ord(char) < 32 or ord(char) == 127 for char in key)
                and walk(child, depth + 1) for key, child in item.items()
            )
        # No arbitrary Python objects, coercion, null or recursive structures.
        return False

    try:
        return walk(value, 0) and len(canonical_json_bytes(value)) <= 16_384
    except (ValueError, TypeError, OverflowError, RecursionError):
        return False


def _direct_input_shape(schema: Any, depth: int = 0) -> bool:
    """Prove explicit scalar/array/closed-object alternatives, not open JSON."""
    if depth > 4 or type(schema) is not dict:
        return False
    if _scalar_contract(schema):
        return True
    if set(schema) in ({"anyOf"}, {"oneOf"}):
        options = schema.get("anyOf", schema.get("oneOf"))
        return (
            type(options) is list and 2 <= len(options) <= 8
            and all(_direct_input_shape(option, depth + 1) for option in options)
        )
    kind = schema.get("type")
    if type(kind) is list:
        return (
            set(schema) == {"type"} and 2 <= len(kind) <= 4
            and all(type(part) is str and part in {"string", "integer", "number", "boolean"}
                    for part in kind)
            and len(kind) == len(set(kind))
        )
    if kind == "array":
        return (
            schema.keys() <= {"type", "items", "minItems", "maxItems", "uniqueItems"}
            and _direct_input_shape(schema.get("items"), depth + 1)
        )
    if kind == "object":
        properties = schema.get("properties")
        required = schema.get("required", [])
        return (
            schema.keys() <= {
                "type", "properties", "required", "additionalProperties",
                "minProperties", "maxProperties",
            }
            and schema.get("additionalProperties") is False
            and type(properties) is dict and len(properties) <= 32
            and type(required) is list and all(type(key) is str for key in required)
            and len(set(required)) == len(required) and set(required) <= properties.keys()
            and all(_direct_input_shape(child, depth + 1) for child in properties.values())
        )
    return False


def _bounded_direct_parameter_fit(schema: dict[str, Any], value: Any) -> bool:
    """Validate a literal direct input against the entire source-native contract.

    Every alternative must declare its shape. Require an actual compatible
    branch, exact primitive types, homogeneous arrays or closed objects, and
    full validation (including union exclusivity). No G5 root/edge expansion.
    """
    if (
        not _bounded_parameter_value(value)
        or not _direct_input_shape(schema)
        or not _response_contract(schema)
    ):
        return False

    def fits(node: dict[str, Any], item: Any) -> bool:
        if "anyOf" in node or "oneOf" in node:
            options = node.get("anyOf", node.get("oneOf"))
            if type(options) is not list:
                return False
            matches = sum(fits(option, item) for option in options)
            return matches == 1 if "oneOf" in node else matches > 0
        kinds = {
            str: ("string",), bool: ("boolean",),
            int: ("integer", "number"), float: ("number",),
            list: ("array",), dict: ("object",),
        }
        kind = node["type"]
        declared = kind if type(kind) is list else [kind]
        if not set(kinds.get(type(item), ())) & set(declared):
            return False
        if kind == "array" and not all(fits(node["items"], child) for child in item):
            return False
        if kind == "object" and (
            not item.keys() <= node["properties"].keys()
            or any(not fits(node["properties"][key], child) for key, child in item.items())
        ):
            return False
        try:
            validate_json_schema_value(item, node, context="direct parameter native branch")
        except Exception:
            return False
        return True

    try:
        if not fits(schema, value):
            return False
        validate_json_schema_value(value, schema, context="direct parameter native contract")
        return True
    except Exception:
        # Never expose private schema contents or validation diagnostics.
        return False


def _approved_direct_input_names(
    endpoint: EndpointSpec,
    visible: EndpointSpec,
    host_values: dict[str, Any],
    required_names: set[str],
) -> tuple[str, ...] | None:
    """Closed direct-only envelope with explicit bounded native host values.

    Unused optional undeclared shapes may remain in the source schema.
    No inference, partial required arguments, credential/header/body-root input,
    open envelope, dependency binding or conversion is authorized here.
    """
    parameters = {param.name: param for param in endpoint.parameters}
    scoped = {param.name: param for param in visible.parameters}
    schema = endpoint.input_schema
    if (
        endpoint.auth_requirements
        or not 1 <= len(parameters) <= 32
        or not 1 <= len(host_values) <= 4
        or len(parameters) != len(endpoint.parameters)
        or set(schema) != {"type", "properties", "required", "additionalProperties"}
        or schema.get("type") != "object"
        or schema.get("additionalProperties") is not False
        or schema.get("properties") != {
            name: param.json_schema for name, param in parameters.items()
        }
        or type(schema.get("required")) is not list
        or len(schema["required"]) != len(required_names)
        or set(schema["required"]) != required_names
        or not required_names <= host_values.keys() <= parameters.keys()
        or not host_values.keys() <= scoped.keys()
    ):
        return None
    for name in host_values:
        parameter = parameters[name]
        if (
            parameter.location in {"header", "body_root"}
            or scoped[name].json_schema != parameter.json_schema
            or not _bounded_direct_parameter_fit(parameter.json_schema, host_values[name])
        ):
            return None
    return tuple(host_values)


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
    host_values: dict[str, Any] | None,
    *,
    allow_direct_host_inputs: bool = False,
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
    availability = router._source_availability_predicate()
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
        source_unit=f.unit,
        unit=(
            f.unit_normalization.canonical_unit
            if f.unit_normalization is not None else f.unit
        ),
        source_type=f.source_type or tool.source_type,
        license=f.license or tool.license,
        qualifiers=tuple(sorted(f.qualifiers.items())),
        source_path=f.projection_path,
        result_path=f.result_projection_path,
        json_schema=canonical_unit_value_schema(f.json_schema, f.unit_normalization),
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

    # Only the original G5 root approval or a separate, snapshot-pinned
    # direct planning declaration may admit explicitly HOST supplied values.
    # Model proposals never flow into arguments.
    arguments: dict[str, Any] = {}
    if host_values is not None:
        if allow_direct_host_inputs:
            names = _approved_direct_input_names(
                endpoint, visible, host_values, required_names,
            )
        else:
            names = _host_source_input_names(endpoint)
        if (
            route.input_bindings
            or not allow_direct_host_inputs and route.route_id not in index.approved_host_roots
            or names is None
            or set(host_values) != set(names)
        ):
            raise PolicyViolationError("unapproved original source arguments")
        if not allow_direct_host_inputs:
            # Preserve the original G5/legacy host scalar type contract.
            by_name = {param.name: param for param in endpoint.parameters}
            for name, value in host_values.items():
                expected = by_name[name].json_schema["type"]
                if (
                    type(value) not in (str, int, float, bool)
                    or expected not in ("string", "integer", "number", "boolean")
                    or type(value) is bool and expected != "boolean"
                    or type(value) is str and expected != "string"
                    or type(value) is int and expected not in ("integer", "number")
                    or type(value) is float and expected != "number"
                    or type(value) is float and not math.isfinite(value)
                    or type(value) is int and not -(2**63) <= value < 2**63
                    or type(value) is str and len(value.encode("utf-8")) > 4096
                ):
                    raise PolicyViolationError("invalid bounded host input scalar")
        validate_json_schema_value(
            host_values, endpoint.input_schema,
            context="original paper host-approved source input",
        )
        arguments = deepcopy(host_values)

    return PaperPlanCall(
        route_id=route.route_id,
        call=ToolCall(
            tool=location[0], endpoint=location[1], arguments=arguments,
            fields=list(route.output_fields),
            evidence=available_evidence(tool, visible, list(route.output_fields)),
            schema_fingerprint=route.endpoint_fingerprint,
            tool_fingerprint=route.tool_fingerprint,
            missing_required_arguments=sorted(required_names - arguments.keys()),
        ),
        source_type=tool.source_type,
        license=tool.license,
        fields_meta=metadata,
        parameters_meta=_paper_public_parameters(visible),
    )
