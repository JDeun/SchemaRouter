"""Read-only trusted-host invocation from opt-in principal-scoped agent view.

Actual RegistryExecutor/SchemaRouter execution, NOT a parallel or invented
invoker. Research-only: no external tenant traffic, mutations or calibrated E2.
"""
from __future__ import annotations

from typing import Any

from schemarouter import (
    ExecutionPlan,
    PlanRequest,
    PolicyViolationError,
    RunConfig,
)
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
)


def _deny() -> None:
    # Do not disclose whether an untrusted source/tool/field exists.
    raise PolicyViolationError("scoped host invocation denied")


async def execute_scoped_host_call(
    view: AuthorizedAgentToolSurface,
    *,
    selected_route_ids: list[str],
    route_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Run ONE read-only source/host-compiled call through router.execute.

    The verified host constructs the view and supplies the trusted invoker.
    route_id/arguments are untrusted model proposals; they never construct an
    ExecutionPlan/ToolCall or confer execution privilege.
    """
    view.assert_source_unchanged()
    tools = view.tool_definitions(selected_route_ids)
    if (
        type(route_id) is not str
        or route_id not in selected_route_ids
        or type(arguments) is not dict
        or any(type(key) is not str for key in arguments)
    ):
        _deny()
    selected_index = selected_route_ids.index(route_id)
    schema = tools[selected_index]["parameters"]
    exposed_parameters = schema["properties"]
    if (
        not set(arguments).issubset(exposed_parameters)
        or not set(schema["required"]).issubset(arguments)
    ):
        _deny()
    # The endpoint is a *source* fact, not a model assertion.
    matches = [
        (tool, endpoint)
        for tool in view.router.registry.tools()
        for endpoint in tool.endpoints
        if f"{tool.key}.{endpoint.name}" == route_id
    ]
    if len(matches) != 1:
        _deny()
    tool, endpoint = matches[0]
    tool_key, endpoint_name = tool.key, endpoint.name
    if endpoint.read_only is not True or endpoint.destructive:
        _deny()

    # The model does not supply fingerprints, plan, selected output scope,
    # fallback branches, authorization policy or execution configuration.
    request = PlanRequest(
        query=view.original_query,
        preferred_tools=[tool_key],
        arguments=arguments,
        max_calls=1,
        fallback_scope="disabled",
    )
    view.assert_source_unchanged()
    try:
        plan = await view.router.aplan_executable_authorized(
            request, principal=view._principal,
        )
    except Exception:
        # The planner/backend may include raw source/user data in error text.
        # An agent-facing host gate must not surface those internals.
        _deny()
    view.assert_source_unchanged()
    try:
        plan = ExecutionPlan.model_validate(
            plan.model_dump(mode="python", warnings=False),
            strict=True,
        )
    except (TypeError, ValueError, OverflowError):
        _deny()
    if (
        plan.query != view.original_query
        or plan.registry_version != view.router.registry.version
        or len(plan.calls) != 1
        or plan.fallback_routes
        or not plan.executable
    ):
        _deny()
    call = plan.calls[0]
    if (
        f"{call.tool}.{call.endpoint}" != route_id
        or call.tool_fingerprint != tool.fingerprint
        or call.schema_fingerprint != endpoint.fingerprint
        or not set(call.fields).issubset(view._visible_output_names[route_id])
        or any(type(k) is not str for k in call.arguments)
        or set(call.arguments) != set(arguments)
        or any(call.arguments[k] != value for k, value in arguments.items())
    ):
        _deny()

    view.assert_source_unchanged()
    # Real host execution policy, binding fingerprints, validated input
    # schema, approval, ABAC and response projection are entirely delegated
    # to the already-existing product path. We do not call a raw invoker.
    try:
        results = await view.router.execute(
            plan, config=RunConfig(principal=view._principal),
        )
    except Exception:
        # Even trusted bindings can return sensitive values in exceptions.
        _deny()
    view.assert_source_unchanged()
    if (
        len(results) != 1
        or results[0].tool != tool_key
        or results[0].endpoint != endpoint_name
        or type(results[0].data) is not dict
    ):
        _deny()
    return view.project_observation(
        route_id, {**results[0].data, "status": "ok"},
    )
