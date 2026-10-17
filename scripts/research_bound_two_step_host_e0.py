"""Two actual Router.execute host-bound reads with state handoff, E0 only.

Unlike FrozenCorpusExecutor, both steps dispatch through SchemaRouter's
real production planner/executor/authorization paths. The bound functions
are synthetic in-process read providers, NOT external native provider traffic
or independent E2 cases. No model or untrusted host-intent oracle is used.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from scripts.research_authorized_agent_tool_surface import (
    AuthorizedAgentToolSurface,
    capture_authorized_agent_tool_surface,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call
from scripts.research_trusted_host_intent_preflight_e0 import (
    preflight_trusted_host_intent_e0,
)

LANGUAGES = ("en", "ko", "ja")
QUERIES = {
    "en": "Look up the public marine record, then verify its paper citation",
    "ko": "해양 공개 기록을 찾은 뒤 그 문헌 인용을 검증해 주세요",
    "ja": "海洋公開資料を調べてから論文の引用を確認してください",
}
CANARY = "PRIVATE-BOUND-PROVIDER-KEY-NEVER-PUBLISH"
PRINCIPAL = PrincipalContext(subject="synthetic-reader", roles=("reader",))


def build_bound_two_step_source(
    seen: list[tuple[str, dict[str, Any]]],
) -> SchemaRouter:
    """Register read-only tools and independently bind each host provider."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="vault.*", roles_any=("reader",),
            ),
            AuthorizationRule(
                effect="allow", operation="*.*", roles_any=("reader",),
            ),
        ),
        data_rules=(DataScopeRule(
            operation="*.*", roles_any=("reader",),
            hidden_fields=("secret",),
        ),),
    ))
    for tool_name, param, output in (
        ("marine", "place", "record_id"),
        ("papers", "record_id", "verified"),
        ("vault", "place", "secret"),
    ):
        router.add_tool(ToolSpec(
            name=tool_name,
            description=f"Public source {tool_name}; secret {CANARY}",
            endpoints=[EndpointSpec(
                name="read",
                description=f"Read authorized metadata; never return {CANARY}",
                read_only=True, destructive=False,
                parameters=[ParameterSpec(
                    name=param, location="query", required=True,
                    json_schema={"type": "string", "minLength": 2},
                )],
                output_fields=[FieldSpec(name=output)] + (
                    [] if output == "secret" else [FieldSpec(name="secret")]
                ),
            )],
        ))

    def marine_read(endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
        seen.append(("marine.read", dict(arguments)))
        return {"record_id": "record-321", "secret": CANARY}

    def papers_read(endpoint: str, arguments: dict[str, Any]) -> dict[str, Any]:
        seen.append(("papers.read", dict(arguments)))
        return {
            "verified": arguments.get("record_id") == "record-321",
            "secret": CANARY,
        }

    for tool_name, invoker in (("marine", marine_read), ("papers", papers_read)):
        tool = router.registry.get(tool_name)
        router.executor.bind(
            tool.key, invoker, expected_fingerprint=tool.fingerprint,
        )
    return router


async def execute_bound_two_step_e0(
    router: SchemaRouter,
    *,
    query: str,
    principal: PrincipalContext,
    first_fields: dict[str, Any] | None = None,
    on_second_capture: Callable[[AuthorizedAgentToolSurface], None] | None = None,
) -> dict[str, Any]:
    """Real in-process executor twice; recapture and reauthorize each step.

    The host fixes the two authorized route hypotheses. The agent/model never
    supplies them; untrusted inference, if added later, must be independently
    validated. No report carries provider args, private keys or raw text.
    """
    if type(query) is not str or not query.strip():
        raise ValueError("nonempty host request required")
    step_one = capture_authorized_agent_tool_surface(
        router, query, principal=principal,
    )
    if "vault.read" in step_one.visible_route_ids:
        raise PolicyViolationError("unexpected private source visibility")
    first_args = {"place": "Seoul"} if first_fields is None else first_fields
    first = preflight_trusted_host_intent_e0(
        step_one, query=query, host_candidate_routes=("marine.read",),
        host_supplied_fields=first_args,
    )
    if first.disposition != "ready" or first.executable_authority:
        raise PolicyViolationError("trusted host inputs incomplete or inaccessible")
    first_result = await execute_scoped_host_call(
        step_one, selected_route_ids=["marine.read"],
        route_id="marine.read", arguments=first_args,
    )
    if (
        type(first_result) is not dict
        or first_result.get("status") != "ok"
        or type(first_result.get("record_id")) is not str
        or not first_result["record_id"]
    ):
        raise PolicyViolationError("first host result did not provide public state")
    if "secret" in first_result:
        raise PolicyViolationError("host redaction invariant violated")
    # Capture a FRESH authorized view for the next call; do not reuse the
    # earlier first-step receipt or raw observation from a host provider.
    step_two = capture_authorized_agent_tool_surface(
        router, query, principal=principal,
    )
    if on_second_capture is not None:
        on_second_capture(step_two)
    second_args = {"record_id": first_result["record_id"]}
    second = preflight_trusted_host_intent_e0(
        step_two, query=query, host_candidate_routes=("papers.read",),
        host_supplied_fields=second_args,
    )
    if second.disposition != "ready" or second.executable_authority:
        raise PolicyViolationError("second-stage host inputs unavailable")
    final = await execute_scoped_host_call(
        step_two, selected_route_ids=["papers.read"],
        route_id="papers.read", arguments=second_args,
    )
    if (
        type(final) is not dict
        or final.get("status") != "ok"
        or type(final.get("verified")) is not bool
    ):
        raise PolicyViolationError("second stage did not return a typed result")
    if "secret" in final:
        raise PolicyViolationError("second-stage redaction invariant violated")
    return {
        "evidence_tier": "E0_SYNTHETIC_BOUND_REAL_ROUTER_EXECUTOR",
        "router_execute_invocations": 2,
        "state_dependent_read_steps": 2,
        "host_field_preflights": 2,
        "host_result_oracle_confirmed": final["verified"],
        "real_router_execution_path_used": True,
        "real_external_native_provider_execution": False,
        "actual_model_inference_measured": False,
        "actual_model_final_answer_correctness_measured": False,
        "independent_e2_qualified": False,
        "release_safety_gate_passed": False,
        "model_default_promoted": False,
    }
