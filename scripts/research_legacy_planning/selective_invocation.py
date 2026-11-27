"""Research-only atomic lexical shortlist/plan execution bridge."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schemarouter.errors import PolicyViolationError
from schemarouter.models import CapabilityRetrieval, PlanRequest, ToolResult
from schemarouter.operation_fit import (
    DeclaredOperationFitPolicy,
    validated_declared_operation_policy,
)
from schemarouter.retrieval_abstention import RetrievalAbstentionPolicy, apply_retrieval_abstention
from schemarouter.retrieval_execution_gate import (
    _deny,
    _validated_abstention_policy,
    execute_selective_plan,
)

if TYPE_CHECKING:
    from schemarouter.runs import RunConfig
    from scripts.research_legacy_runtime import LegacySchemaRouter


async def ainvoke_selective(
    router: LegacySchemaRouter,
    request: PlanRequest | str,
    *,
    policy: RetrievalAbstentionPolicy,
    k: int = 5,
    config: RunConfig | dict[str, Any] | None = None,
    operation_fit: DeclaredOperationFitPolicy | None = None,
) -> list[ToolResult]:
    """Opt-in atomic host workflow: same-principal retrieval, plan, execution.

    Unlike the lower-level bridge, this function obtains both the scored
    shortlist and the executable plan itself using the *same trusted request*
    and one validated RunConfig principal. No caller-supplied ranking, plan
    or candidate permission is accepted. Ordinary `ainvoke` is unchanged.
    """
    from schemarouter.runs import RunConfig

    # Pydantic model_copy(update=...) bypasses validators. Validate the
    # *contents* of an already-instantiated RunConfig before allowing its
    # principal to influence authorized retrieval or planning.
    try:
        if config is None:
            run_config = RunConfig()
        elif isinstance(config, RunConfig):
            run_config = RunConfig.model_validate(
                config.model_dump(mode="python", warnings=False)
            )
        else:
            run_config = RunConfig.model_validate(config)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyViolationError(
            "selective retrieval execution denied: invalid run configuration"
        ) from exc
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    policy = _validated_abstention_policy(policy)
    if operation_fit is not None:
        operation_fit = validated_declared_operation_policy(operation_fit)

    # Validate the trusted request *before* an authorized retrieval. A caller
    # can bypass Pydantic with model_copy(update=...), including a non-string
    # query or malformed plan fields. Never pass such input into an external
    # retriever, paid backend, or downstream planner.
    expected_query: str = ""
    if isinstance(request, str):
        expected_query = request
    elif isinstance(request, PlanRequest):
        try:
            request = PlanRequest.model_validate(
                request.model_dump(mode="python", warnings=False)
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise PolicyViolationError(
                "selective retrieval execution denied: invalid request envelope"
            ) from exc
        expected_query = request.query
    else:
        _deny("invalid request type")
    if not isinstance(expected_query, str) or not expected_query.strip():
        _deny("empty or invalid request query")

    if run_config.principal is None:
        retrieval = await router.aretrieve_executable(request, k=k)
    else:
        retrieval = await router.aretrieve_executable_authorized(
            request, principal=run_config.principal, k=k,
        )
    # Preflight before any potentially remote/costly planner call. The
    # execution gate below rechecks after planning in case the registry or
    # rankings changed. This does not modify plain router.ainvoke().
    if not isinstance(retrieval, CapabilityRetrieval):
        _deny("invalid retrieval envelope")
    if (
        retrieval.executable_only is not True
        or type(retrieval.registry_version) is not int
        or retrieval.registry_version != router.registry.version
        or retrieval.query != expected_query
        or not isinstance(expected_query, str)
        or not expected_query.strip()
    ):
        _deny("non-executable retrieval, stale registry or mismatched query")
    if type(retrieval.requested_k) is not int or retrieval.requested_k != k:
        _deny("mismatched retrieval shortlist budget")
    preselection = apply_retrieval_abstention(retrieval, policy=policy)
    if preselection.abstained or not preselection.candidates:
        _deny("no-match: " + preselection.reason)

    if run_config.principal is None:
        plan = await router.aplan_executable(request)
    else:
        plan = await router.aplan_executable_authorized(
            request, principal=run_config.principal,
        )
    return await execute_selective_plan(
        router, retrieval, plan, policy=policy, config=run_config,
        operation_fit=operation_fit,
    )
