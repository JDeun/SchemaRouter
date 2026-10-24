"""Opt-in G5 E0 validation of observed scalar values against a current typed edge.

Do NOT treat caller-supplied ToolResult data as provider authenticity, executor
authority, or independent task evidence. No invocations, policy grants or storage.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .errors import PolicyViolationError, SchemaValidationError
from .field_group_retrieval import NativeDeclaredFieldGroup
from .models import ToolResult
from .native_graph_index import (
    NativeIndexedGraphCandidate,
    NativeSchemaGraphIndex,
    _flat_same_record_source_contract,
    _native_required_inputs,
)
from .validation import validate_json_schema_value

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class NativeObservedArgumentEvidence:
    """Validated values only; no authenticated origin or execution authority."""

    producer_route_id: str
    consumer_route_id: str
    parameter_values: tuple[tuple[str, str | int | float | bool], ...]
    provider_provenance_verified: bool = False
    executable_authority: bool = False
    independent_e2: bool = False

    @property
    def arguments(self) -> dict[str, str | int | float | bool]:
        """Return a fresh copy; no references to the caller's original dict."""
        return dict(self.parameter_values)


def materialize_native_observed_arguments(
    index: NativeSchemaGraphIndex,
    router: SchemaRouter,
    *,
    query: str,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    candidate: NativeIndexedGraphCandidate,
    observation: ToolResult,
) -> NativeObservedArgumentEvidence:
    """Validate non-null, per-argument observed data against CURRENT authority.

    Only a caller-constructed/offline ToolResult is required. Its claimed
    identity is NOT cryptographically authenticated and is NEVER sufficient
    to grant execution. A real executor must separately revalidate the call.
    """
    if not isinstance(candidate, NativeIndexedGraphCandidate):
        raise ValueError("expected original indexed G5 edge candidate")
    if not isinstance(observation, ToolResult):
        raise ValueError("expected a locally projected ToolResult")
    current = index.lookup(
        router, query, group=group, principal=principal,
    )
    if current.status != "complete" or candidate not in current.candidates:
        raise PolicyViolationError("G5 current permitted graph edge changed")
    values = _materialize_original_observed_edge(index, router, candidate, observation)
    # A concurrent registry/scope/policy change invalidates an observed edge.
    check = index.lookup(router, query, group=group, principal=principal)
    if check.status != "complete" or candidate not in check.candidates:
        raise PolicyViolationError("G5 authority changed during value validation")
    return values


def _materialize_original_observed_edge(
    index: NativeSchemaGraphIndex,
    router: SchemaRouter,
    candidate: NativeIndexedGraphCandidate,
    observation: ToolResult,
) -> NativeObservedArgumentEvidence:
    """Scalar checks shared by the public and private source-verified paths.

    INTERNAL ONLY. Caller MUST first and finally prove the exact original
    native graph edge under the current principal, policy, K5 and source.
    This helper alone has NO authorization/provenance/execution authority.
    """
    producer_key, producer_endpoint_name = index.field_index.route_locations[
        candidate.producer_route_id
    ]
    consumer_key, consumer_endpoint_name = index.field_index.route_locations[
        candidate.consumer_route_id
    ]
    if (observation.tool, observation.endpoint) != (
        producer_key, producer_endpoint_name
    ):
        raise SchemaValidationError("G5 observation route does not match producer")
    producer_tool = router.registry.get(producer_key)
    producer = producer_tool.endpoint(producer_endpoint_name)
    consumer_tool = router.registry.get(consumer_key)
    consumer = consumer_tool.endpoint(consumer_endpoint_name)
    if (
        producer_tool.fingerprint != candidate.producer_tool_fingerprint
        or producer.fingerprint != candidate.producer_endpoint_fingerprint
        or consumer_tool.fingerprint != candidate.consumer_tool_fingerprint
        or consumer.fingerprint != candidate.consumer_endpoint_fingerprint
    ):
        raise PolicyViolationError("G5 schema identity changed before observation")
    required = _native_required_inputs(consumer)
    expected_names = tuple(param for param, _ in required) if required else ()
    given_names = tuple(param for param, _ in candidate.parameter_bindings)
    if not expected_names or expected_names != given_names:
        raise SchemaValidationError("G5 incomplete observation binding contract")
    source_field_names = tuple(field for _, field in candidate.parameter_bindings)
    if len(set(source_field_names)) != len(source_field_names):
        raise SchemaValidationError("G5 repeated source identifier")
    if (
        len(expected_names) > 1
        and not _flat_same_record_source_contract(
            producer, producer, source_field_names,
        )
    ):
        raise SchemaValidationError("G5 source values do not share a required object")
    if type(observation.data) is not dict:
        raise SchemaValidationError("G5 observation must be a single projected object")
    projected = observation.data
    if not set(source_field_names).issubset(observation.projected_fields):
        raise SchemaValidationError("G5 observation lacks explicitly projected fields")

    produced = {field.name: field for field in producer.output_fields}
    consumes = {param.name: param for param in consumer.parameters}
    values: list[tuple[str, str | int | float | bool]] = []
    for parameter, source_name in candidate.parameter_bindings:
        field = produced.get(source_name)
        target = consumes.get(parameter)
        contract = observation.field_contracts.get(source_name)
        if (
            field is None or target is None
            or field.projection_path != (source_name,)
            or field.result_projection_path != (source_name,)
            or source_name not in projected
            or contract is None
            or contract.has_observed_value is not True
            or contract.semantic_id != field.semantic_id
        ):
            raise SchemaValidationError("G5 observation lacks verified field presence")
        value: Any = projected[source_name]
        if type(value) not in (str, int, float, bool):
            raise SchemaValidationError("G5 observed identifier is not a JSON scalar")
        if type(value) is float and not math.isfinite(value):
            raise SchemaValidationError("G5 observed identifier is non-finite")
        if type(value) is str and len(value.encode("utf-8")) > 4096:
            raise SchemaValidationError("G5 observed identifier exceeds bounded size")
        validate_json_schema_value(
            value, field.json_schema,
            context=f"G5 produced field {source_name}",
        )
        validate_json_schema_value(
            value, target.json_schema,
            context=f"G5 required consumer parameter {parameter}",
        )
        values.append((parameter, value))
    # Revalidate the complete consumer input envelope, including required
    # flags, against original source-native constraints.
    args = dict(values)
    if consumer.input_schema:
        validate_json_schema_value(
            args, consumer.input_schema, context="G5 entire consumer arguments",
        )
    return NativeObservedArgumentEvidence(
        producer_route_id=candidate.producer_route_id,
        consumer_route_id=candidate.consumer_route_id,
        parameter_values=tuple(values),
    )
