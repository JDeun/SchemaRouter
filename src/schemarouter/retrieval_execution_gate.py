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
    PlanRequest,
    ToolCall,
    ToolResult,
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
    if type(registry_version) is not int or registry_version < 0:
        _deny("invalid active registry version")

    # Check identity before interpreting the score. model_copy(update=...)
    # may bypass Pydantic validation of the trusted host's plan envelope.
    if (
        type(retrieval.registry_version) is not int
        or type(plan.registry_version) is not int
        or retrieval.registry_version != registry_version
        or plan.registry_version != registry_version
        or not isinstance(retrieval.query, str)
        or not retrieval.query.strip()
        or plan.query != retrieval.query
    ):
        _deny("stale registry or mismatched query/plan provenance")

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
            _deny("plan references a route outside selected shortlist")
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
) -> list[ToolResult]:
    """Execute only a selected, in-scope plan; never call on abstention.

    Host code must obtain `retrieval` and `plan` from the *same* trusted
    authorization/principal scope. A model-supplied retrieval or plan is not
    an authorization source. The underlying runtime retains the final policy
    and execution checks; callers must opt into this method deliberately.
    """
    validate_selective_execution(
        retrieval,
        plan,
        policy=policy,
        registry_version=router.registry.version,
    )
    # All guards run before this first/only execution entrypoint.
    return await router.execute(plan, config=config)


async def ainvoke_selective(
    router: SchemaRouter,
    request: PlanRequest | str,
    *,
    policy: RetrievalAbstentionPolicy,
    k: int = 5,
    config: RunConfig | dict[str, Any] | None = None,
) -> list[ToolResult]:
    """Opt-in atomic host workflow: same-principal retrieval, plan, execution.

    Unlike the lower-level bridge, this function obtains both the scored
    shortlist and the executable plan itself using the *same trusted request*
    and one validated RunConfig principal. No caller-supplied ranking, plan
    or candidate permission is accepted. Ordinary `ainvoke` is unchanged.
    """
    from .runs import RunConfig

    run_config = (
        RunConfig()
        if config is None
        else RunConfig.model_validate(config)
    )
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    if run_config.principal is None:
        retrieval = await router.aretrieve_executable(request, k=k)
        plan = await router.aplan_executable(request)
    else:
        retrieval = await router.aretrieve_executable_authorized(
            request, principal=run_config.principal, k=k,
        )
        plan = await router.aplan_executable_authorized(
            request, principal=run_config.principal,
        )
    return await execute_selective_plan(
        router, retrieval, plan, policy=policy, config=run_config,
    )
