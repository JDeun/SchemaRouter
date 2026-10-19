"""Opt-in E0 G5 one-hop execution using the existing authorized executor.

The in-process execution return is NOT independent verification of upstream
provider identity or of a downstream agent task. No executable graph agent,
no new invoker, no LLM, no policy grants, no production default change.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .errors import PolicyViolationError, SchemaValidationError
from .field_group_retrieval import NativeDeclaredFieldGroup
from .models import ExecutionPlan, ToolCall, ToolResult
from .native_graph_index import (
    NativeIndexedGraphCandidate,
    NativeSchemaGraphIndex,
    _host_source_input_names,
)
from .native_graph_observation import materialize_native_observed_arguments
from .runs import ExecutionBudget, RunConfig
from .validation import validate_json_schema_value

if TYPE_CHECKING:
    from .runtime import SchemaRouter


@dataclass(frozen=True, slots=True)
class NativeOneHopExecutionEvidence:
    """Source-scoped read-only result, not an independently authenticated E2."""

    producer: ToolResult
    consumer: ToolResult
    producer_via_registered_executor: bool = True
    consumer_via_registered_executor: bool = True
    independent_provider_identity_verified: bool = False
    independent_agent_e2: bool = False


async def execute_native_graph_one_hop(
    index: NativeSchemaGraphIndex,
    router: SchemaRouter,
    *,
    query: str,
    group: NativeDeclaredFieldGroup,
    principal: PrincipalContext,
    candidate: NativeIndexedGraphCandidate,
    source_arguments: dict[str, Any] | None = None,
) -> NativeOneHopExecutionEvidence:
    """Execute two trusted registered read-only calls with full existing gates.

    Never accept caller-supplied ToolResult. Only an actual return from the
    registered executor is passed to the nonexecuting scalar validator.
    Each call revalidates current principal, policy, source fingerprints,
    execution budgets, output projection and input/output JSON schemas.
    """
    if not isinstance(candidate, NativeIndexedGraphCandidate):
        raise ValueError("G5 original indexed candidate required")
    current = index.lookup(router, query, group=group, principal=principal)
    if current.status != "complete" or candidate not in current.candidates:
        raise PolicyViolationError("G5 candidate no longer source-authorized")

    source_key, source_endpoint = index.field_index.route_locations[
        candidate.producer_route_id
    ]
    dest_key, dest_endpoint = index.field_index.route_locations[
        candidate.consumer_route_id
    ]
    if (
        not candidate.parameter_bindings
        or len(candidate.parameter_bindings) > 4
        or len({name for name, _ in candidate.parameter_bindings})
        != len(candidate.parameter_bindings)
    ):
        raise SchemaValidationError("G5 missing complete bounded bindings")
    output_fields = list(dict.fromkeys(
        field_name for _, field_name in candidate.parameter_bindings
    ))
    if len(output_fields) != len(candidate.parameter_bindings):
        raise SchemaValidationError("G5 duplicate source field mapping")

    # A parameterized source requires *all* arguments from the trusted host.
    # Do not guess them from the natural-language query or typed graph edge.
    approved_inputs = candidate.source_root_parameters
    if approved_inputs:
        if candidate.producer_route_id not in index.approved_host_roots:
            raise PolicyViolationError("G5 original source was not host approved")
        source_spec = router.registry.get(source_key).endpoint(source_endpoint)
        if _host_source_input_names(source_spec) != approved_inputs:
            raise PolicyViolationError("G5 host source input contract changed")
        if (
            type(source_arguments) is not dict
            or set(source_arguments) != set(approved_inputs)
        ):
            raise SchemaValidationError("G5 complete host source inputs required")
        for value in source_arguments.values():
            if (
                type(value) not in (str, int, float, bool)
                or type(value) is float and not math.isfinite(value)
                or type(value) is str and len(value.encode("utf-8")) > 4096
            ):
                raise SchemaValidationError("G5 invalid bounded host source scalar")
        validate_json_schema_value(
            source_arguments, source_spec.input_schema,
            context="G5 host-approved original source arguments",
        )
        initial_args = dict(source_arguments)
    else:
        if source_arguments is not None:
            raise SchemaValidationError("G5 no-input source rejects extra host inputs")
        initial_args = {}
    # The budget applies to each call separately; this routine cannot bypass
    # the configured executor's policy/trace/invoker validation boundary.
    config = RunConfig(
        principal=principal,
        budget=ExecutionBudget(
            max_tool_calls=1,
            max_attempts=1,
            max_remote_attempts=1,
        ),
    )

    def _plan(
        *,
        tool: str,
        endpoint: str,
        tool_fingerprint: str,
        endpoint_fingerprint: str,
        arguments: dict,
        fields: list[str],
    ) -> ExecutionPlan:
        return ExecutionPlan(
            query=query,
            registry_version=router.registry.version,
            calls=[ToolCall(
                tool=tool,
                endpoint=endpoint,
                tool_fingerprint=tool_fingerprint,
                schema_fingerprint=endpoint_fingerprint,
                arguments=arguments,
                fields=fields,
            )],
        )

    source_plan = _plan(
        tool=source_key,
        endpoint=source_endpoint,
        tool_fingerprint=candidate.producer_tool_fingerprint,
        endpoint_fingerprint=candidate.producer_endpoint_fingerprint,
        arguments=initial_args,
        fields=output_fields,
    )
    first = await router.execute(source_plan, config=config)
    if len(first) != 1 or not isinstance(first[0], ToolResult):
        raise SchemaValidationError("G5 source execution produced no single result")
    source_result = first[0]

    values = materialize_native_observed_arguments(
        index, router, query=query, group=group,
        principal=principal, candidate=candidate,
        observation=source_result,
    )
    # The observation validator is an input-data preflight, NOT authority.
    # Only the original executor can authorize and validate a second call.
    dest_plan = _plan(
        tool=dest_key,
        endpoint=dest_endpoint,
        tool_fingerprint=candidate.consumer_tool_fingerprint,
        endpoint_fingerprint=candidate.consumer_endpoint_fingerprint,
        arguments=values.arguments,
        fields=list(candidate.consumer_output_fields),
    )
    second = await router.execute(dest_plan, config=config)
    if len(second) != 1 or not isinstance(second[0], ToolResult):
        raise SchemaValidationError("G5 consumer execution produced no single result")
    return NativeOneHopExecutionEvidence(
        producer=source_result,
        consumer=second[0],
    )
