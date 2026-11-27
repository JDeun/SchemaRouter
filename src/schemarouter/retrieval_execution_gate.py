"""Explicit opt-in execution bridge for calibrated retrieval abstention (#1291).

This guards a host-provided execution plan *after* authorized retrieval and
policy evaluation. The ordinary SchemaRouter.invoke/execute APIs are unchanged.
A ranking decision is never a grant of permission: SchemaRouter's original
runtime authorization/validation is still enforced by router.execute().
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .errors import PolicyViolationError
from .models import (
    CapabilityRetrieval,
    ExecutionPlan,
    FallbackRoute,
    ToolCall,
    ToolResult,
)
from .operation_fit import (
    DeclaredOperationFitPolicy,
    validate_declared_operation_fit,
)
from .retrieval_abstention import (
    RetrievalAbstentionPolicy,
    SelectiveCapabilityRetrieval,
    apply_retrieval_abstention,
)

if TYPE_CHECKING:
    from .runs import RunConfig
    from .runtime import SchemaRouter


def _deny(reason: str) -> None:
    raise PolicyViolationError("selective retrieval execution denied: " + reason)


def _validated_abstention_policy(
    policy: RetrievalAbstentionPolicy,
) -> RetrievalAbstentionPolicy:
    if not isinstance(policy, RetrievalAbstentionPolicy):
        _deny("invalid host-supplied no-match policy")
    try:
        # Pydantic model_copy(update=...) bypasses field validation.
        return RetrievalAbstentionPolicy.model_validate(
            policy.model_dump(mode="python", warnings=False)
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError(
            "selective retrieval execution denied: invalid calibrated policy"
        ) from exc


def validate_selective_execution(
    retrieval: CapabilityRetrieval,
    plan: ExecutionPlan,
    *,
    policy: RetrievalAbstentionPolicy,
    registry_version: int,
) -> SelectiveCapabilityRetrieval:
    """Validate the *entire* proposed plan against one scoped shortlist.

    Only a trusted host should supply the retrieval and compiled plan from the
    same authorized request/principal. This function cannot establish that an
    unsupported request is semantically detectable from a ranker's score.
    """
    if not isinstance(retrieval, CapabilityRetrieval):
        raise TypeError("retrieval must be a trusted CapabilityRetrieval")
    if not isinstance(plan, ExecutionPlan):
        raise TypeError("plan must be a trusted ExecutionPlan")
    # A forged model_copy(update=...) can smuggle list-shaped arguments,
    # non-list required-argument flags, or malformed fallback metadata into
    # an otherwise typed ExecutionPlan. Revalidate its complete nested
    # envelope before authorizing a single downstream execution.
    try:
        ExecutionPlan.model_validate(
            plan.model_dump(mode="python", warnings=False)
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError(
            "selective retrieval execution denied: invalid plan envelope"
        ) from exc
    if type(registry_version) is not int or registry_version < 0:
        _deny("invalid active registry version")
    policy = _validated_abstention_policy(policy)

    # Check identity before interpreting the score. model_copy(update=...)
    # may bypass Pydantic validation of the trusted host's plan envelope.
    if (
        retrieval.executable_only is not True
        or type(retrieval.registry_version) is not int
        or type(plan.registry_version) is not int
        or retrieval.registry_version != registry_version
        or plan.registry_version != registry_version
        or not isinstance(retrieval.query, str)
        or not retrieval.query.strip()
        or plan.query != retrieval.query
    ):
        _deny("non-executable retrieval, stale registry or mismatched query/plan provenance")

    decision = apply_retrieval_abstention(retrieval, policy=policy)
    if decision.abstained or not decision.candidates:
        _deny("no-match: " + decision.reason)

    if not isinstance(plan.calls, list) or not plan.calls:
        _deny("plan contains no executable calls")
    if not isinstance(plan.fallback_routes, list):
        _deny("invalid fallback route envelope")

    allowed = {candidate.route_id: candidate for candidate in decision.candidates}
    if len(allowed) != len(decision.candidates):
        _deny("duplicate shortlist route identity")

    def check_call(call: ToolCall) -> None:
        if not isinstance(call, ToolCall):
            _deny("non-ToolCall plan entry")
        route_id = f"{call.tool}.{call.endpoint}"
        candidate = allowed.get(route_id)
        if candidate is None:
            raise PolicyViolationError(
                "selective retrieval execution denied: "
                "plan references a route outside selected shortlist"
            )
        if (
            call.tool_fingerprint != candidate.tool_fingerprint
            or call.schema_fingerprint != candidate.endpoint_fingerprint
        ):
            _deny("plan schema/tool provenance differs from selected candidate")
        if not call.executable:
            _deny("plan includes a call with missing required arguments")
        exposed_fields = {field.name for field in candidate.output_fields}
        if not isinstance(call.fields, list) or any(
            not isinstance(field, str) or field not in exposed_fields
            for field in call.fields
        ):
            _deny("plan requests fields outside the authorized shortlist schema")

    for call in plan.calls:
        check_call(call)
    seen_fallback_indices: set[int] = set()
    for route in plan.fallback_routes:
        if not isinstance(route, FallbackRoute):
            _deny("invalid fallback route envelope")
        if not isinstance(route.alternatives, list):
            _deny("invalid fallback alternatives")
        index = route.primary_call_index
        if (
            type(index) is not int
            or index < 0
            or index >= len(plan.calls)
            or index in seen_fallback_indices
        ):
            _deny("invalid or duplicate fallback primary index")
        seen_fallback_indices.add(index)
        for fallback in route.alternatives:
            check_call(fallback)
    return decision


async def execute_selective_plan(
    router: SchemaRouter,
    retrieval: CapabilityRetrieval,
    plan: ExecutionPlan,
    *,
    policy: RetrievalAbstentionPolicy,
    config: RunConfig | dict[str, Any] | None = None,
    operation_fit: DeclaredOperationFitPolicy | None = None,
) -> list[ToolResult]:
    """Execute only a selected, in-scope plan; never call on abstention.

    Host code must obtain `retrieval` and `plan` from the *same* trusted
    authorization/principal scope. A model-supplied retrieval or plan is not
    an authorization source. The underlying runtime retains the final policy
    and execution checks; callers must opt into this method deliberately.
    """
    # The caller owns both mutable model graphs. Validate and dispatch the
    # same detached plan snapshot so later mutations of the original object
    # cannot change a route or its arguments after the no-match gate passes.
    # Deep-copy the retrieval too: its candidate list/metadata must not be
    # replaced by the caller while the selected plan is being checked.
    if not isinstance(retrieval, CapabilityRetrieval):
        raise TypeError("retrieval must be a trusted CapabilityRetrieval")
    if not isinstance(plan, ExecutionPlan):
        raise TypeError("plan must be a trusted ExecutionPlan")
    # Preserve the pre-existing provenance denial for a forged boolean,
    # non-integer or stale registry identity before strict deep validation.
    if type(plan.registry_version) is not int:
        _deny("non-executable retrieval, stale registry or mismatched query/plan provenance")
    try:
        dispatch_plan = ExecutionPlan.model_validate(
            plan.model_dump(mode="python", warnings=False),
            strict=True,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError(
            "selective retrieval execution denied: invalid plan envelope"
        ) from exc
    scoped_retrieval = retrieval.model_copy(deep=True)
    validate_selective_execution(
        scoped_retrieval,
        dispatch_plan,
        policy=policy,
        registry_version=router.registry.version,
    )
    if operation_fit is not None:
        validate_declared_operation_fit(dispatch_plan, policy=operation_fit)
    # Route the validated snapshot, never the mutable caller-supplied plan.
    return await router.execute(dispatch_plan, config=config)
