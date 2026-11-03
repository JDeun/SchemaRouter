"""Conservative scalar query-condition evidence over current scoped source inputs.

A hint is a requirement to account for, never permission to supply a value.
No output postfilter relation is inferred from names or identifier flags.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from .authorization import PrincipalContext
from .canonical_json import canonical_json_text
from .errors import PolicyViolationError
from .field_group_retrieval import _scalar_contract
from .host_field_contract import _policy_contents_digest
from .models import ParameterSpec, PlanCoverage, SemanticFieldRequirement
from .paper_typed_tool_plan import PaperTypedToolPlan, _check_current_call_scopes
from .validation import validate_json_schema_value

if TYPE_CHECKING:
    from .runtime import SchemaRouter


def _same_json_scalar(left: Any, right: Any) -> bool:
    """Exact JSON value equality without bool/number conflation or float coercion."""
    if type(left) not in (str, int, float, bool) or type(right) not in (str, int, float, bool):
        return False
    if type(left) is float and not math.isfinite(left):
        return False
    if type(right) is float and not math.isfinite(right):
        return False
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    # Python's mixed int/float comparison retains the exact integer boundary;
    # casting both sides to float would falsely equate integers above 2**53.
    return left == right


def _apply_query_input_conditions(
    router: SchemaRouter,
    plan: PaperTypedToolPlan,
    *,
    principal: PrincipalContext,
    parameter_hints: dict[str, Any],
) -> PaperTypedToolPlan:
    """Add original-question scalar conditions without changing any ToolCall.

    Only one explicitly named/aliased/semantic source parameter may witness
    each global hint. A publicly validated proposal can prove the mapping
    while remaining pending in the coverage ledger and requires_arguments;
    source-required metadata and actual arguments stay unchanged. Multiple
    targets have no proven per-need scope in this DTO, so neither broadcasting
    nor a guessed output filter is allowed.
    """
    if not parameter_hints:
        return plan
    if plan.coverage is None or plan.executable_authority:
        raise PolicyViolationError("query conditions require original nonexecuting coverage")
    witness = router._retrieval_authority_witness()
    policy = router.authorization_policy
    if policy is None or router.registry.version != plan.registry_version:
        raise PolicyViolationError("query input source eligibility changed")
    try:
        claims = principal.model_dump_json()
        policy_digest = _policy_contents_digest(policy)
        original_calls = tuple(item.call.model_dump_json() for item in plan.calls)
        hints = dict(parameter_hints)
        hint_contents = canonical_json_text(hints)
    except Exception:
        raise PolicyViolationError("query input source eligibility changed") from None

    def verify() -> None:
        router._check_retrieval_authority_witness(witness)
        if (
            router.authorization_policy is None
            or _policy_contents_digest(router.authorization_policy) != policy_digest
            or principal.model_dump_json() != claims
            or tuple(item.call.model_dump_json() for item in plan.calls) != original_calls
            or canonical_json_text(parameter_hints) != hint_contents
        ):
            raise PolicyViolationError("query input source eligibility changed")

    def scoped_inputs() -> tuple[tuple[int, ParameterSpec, bool], ...]:
        _check_current_call_scopes(router, principal, list(plan.calls))
        permitted = router._authorization_predicate(principal)
        if permitted is None:
            raise PolicyViolationError("query input source eligibility changed")
        available = router.planner.availability_predicate
        parameters = []
        for position, item in enumerate(plan.calls):
            tool = router.registry.get(item.call.tool)
            endpoint = tool.endpoint(item.call.endpoint)
            if (
                tool.fingerprint != item.call.tool_fingerprint
                or endpoint.fingerprint != item.call.schema_fingerprint
                or not permitted(tool.model_copy(deep=True), endpoint.model_copy(deep=True))
                or available is not None and not available(
                    tool.model_copy(deep=True), endpoint.model_copy(deep=True),
                )
            ):
                raise PolicyViolationError("query input source eligibility changed")
            scoped = router._data_scope_endpoint_view(principal, tool, endpoint)
            if scoped is None:
                raise PolicyViolationError("query input source eligibility changed")
            # Equality only: never test a proposed value against assertions
            # removed from this principal's descriptor (a membership oracle).
            original = {parameter.name: parameter for parameter in endpoint.parameters}
            parameters.extend((position, parameter.model_copy(deep=True),
                canonical_json_text(parameter.json_schema)
                == canonical_json_text(original[parameter.name].json_schema),
            ) for parameter in scoped.parameters)
        verify()
        return tuple(parameters)

    try:
        parameters = scoped_inputs()
        required = list(plan.coverage.required)
        covered = list(plan.coverage.covered)
        uncovered = list(plan.coverage.uncovered)
        pending = False
        for key, proposed in hints.items():
            matches = [(position, parameter, exposed)
                       for position, parameter, exposed in parameters if (
                key == parameter.name or key in parameter.aliases or key == parameter.semantic_id
            )]
            present = False
            proof = "unproven_source_relation"
            if len(matches) > 1:
                proof = "ambiguous_source_input"
            elif matches:
                position, parameter, exposed = matches[0]
                call = plan.calls[position].call
                if parameter.name not in call.arguments:
                    proof = "unproven_scoped_input_fit"
                    if exposed:
                        proof = "invalid_proposed_input"
                        try:
                            if _scalar_contract(parameter.json_schema):
                                validate_json_schema_value(
                                    proposed, parameter.json_schema,
                                    context="query proposed input",
                                )
                                proof = "pending_host_input"
                                present = True
                                pending = True
                        except Exception:
                            # Never turn a private schema/validator diagnostic
                            # into a hint membership oracle or value echo.
                            pass
                elif _same_json_scalar(proposed, call.arguments[parameter.name]):
                    proof = "matching_host_input"
                    present = True
                else:
                    proof = "conflicting_host_input"
            qualifiers = ["query_input_condition=true", f"proof={proof}"]
            if len(matches) == 1:
                position, parameter, _ = matches[0]
                qualifiers.extend((f"route={plan.calls[position].route_id}",
                                   f"parameter={parameter.name}"))
            requirement = SemanticFieldRequirement(semantic_id=key, qualifiers=qualifiers)
            required.append(requirement)
            (covered if present else uncovered).append(requirement)
        # Reobserve the same scoped declarations after callbacks and refuse
        # actor/source/policy/argument mutation, without private diagnostics.
        if scoped_inputs() != parameters:
            raise PolicyViolationError("query input source eligibility changed")
        verify()
    except Exception:
        raise PolicyViolationError("query input source eligibility changed") from None
    complete = plan.coverage.complete and not uncovered
    status = plan.status
    if status == "ready":
        status = "no_proven_hit" if not complete else "requires_arguments" if pending else "ready"
    return replace(
        plan,
        status=status,
        coverage=PlanCoverage(required=required, covered=covered, uncovered=uncovered,
                              complete=complete),
    )
