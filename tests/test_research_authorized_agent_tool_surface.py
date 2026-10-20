"""No-model E0 scope/redaction controls, NOT tenant execution certification."""
from __future__ import annotations

import json

import pytest

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
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_agent_stage_evidence_e0 import E0TraceProvenance
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_scoped_host_invocation import execute_scoped_host_call

SECRET = "SECRET_HIDDEN_CANARY_1749"
VIEWER = PrincipalContext(subject="synthetic-viewer", roles=("viewer",))
OUTSIDER = PrincipalContext(subject="synthetic-outsider", roles=("outsider",))


def fixture_router() -> SchemaRouter:
    router = SchemaRouter(
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(
                AuthorizationRule(
                    name="viewer-deny-archive", effect="deny",
                    operation="archive.*", roles_any=("viewer",),
                ),
                AuthorizationRule(
                    name="viewer-can-read", effect="allow",
                    operation="*.*", roles_any=("viewer",),
                ),
            ),
            data_rules=(
                DataScopeRule(
                    operation="*.*", roles_any=("viewer",),
                    hidden_fields=("secret_field",),
                ),
            ),
        ),
    )
    for name in ("marine", "papers", "archive"):
        router.add_tool(ToolSpec(
            name=name,
            description=f"{name} public records and {SECRET} hidden field",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description=f"Read {name} values {SECRET}",
                    read_only=True,
                    parameters=[
                        ParameterSpec(
                            name="place", location="query", required=True,
                            description=f"Public location {SECRET}",
                            json_schema={
                                "type": "string", "description": SECRET,
                                "examples": [SECRET],
                            },
                        ),
                        ParameterSpec(
                            name="filter__secret_field", location="query",
                            json_schema={
                                "type": "string", "examples": [SECRET],
                            },
                        ),
                    ],
                    output_fields=[
                        FieldSpec(name="public_field"),
                        FieldSpec(name="secret_field"),
                    ],
                ),
            ],
        ))
    return router


def captured(router=None, principal=VIEWER):
    return capture_authorized_agent_tool_surface(
        router or fixture_router(),
        "marine public papers read values", principal=principal,
    )


def test_authorized_agent_view_excludes_denied_routes_and_hidden_descriptions():
    view = captured()
    assert set(view.visible_route_ids) == {"marine.read", "papers.read"}
    model_tools = view.tool_definitions(list(view.visible_route_ids), k=5)
    data = json.dumps(model_tools)
    assert SECRET not in data
    assert "secret_field" not in data
    assert "archive" not in data
    assert "public_field" in data
    assert "place" in data
    assert "filter__secret_field" not in data
    assert "examples" not in data
    assert "description" not in model_tools[0]["parameters"]["properties"]["place"]
    assert not view.executable_authority
    assert not view.independent_quality_evidence


def test_outsider_receives_empty_model_view_without_hidden_catalog_count():
    view = captured(principal=OUTSIDER)
    assert view.visible_route_ids == ()
    assert view.tool_definitions([]) == []
    summary = view.public_trace({
        "passed": False, "candidate_history": [],
        "required_routes": ["archive.read"],
    })
    public = json.dumps(summary)
    assert "archive" not in public
    assert "registered_route_count" not in public
    assert "visible_scored_route_count" in summary
    assert summary["visible_scored_route_count"] == 0


@pytest.mark.parametrize("selected,k", (
    (["archive.read"], 5),
    (["fake.read"], 5),
    (["marine.read", "marine.read"], 5),
    (["marine.read", "papers.read"], 1),
    ("marine.read", 5),
    ([None], 5),
    (["marine.read"], 0),
    (["marine.read"], 6),
))
def test_bad_source_selection_or_budget_fails_closed(selected, k):
    with pytest.raises((PolicyViolationError, ValueError)):
        captured().tool_definitions(selected, k=k)


def test_observation_only_exports_approved_scalar_fields():
    view = captured()
    outcome = view.project_observation("marine.read", {
        "status": "ok", "public_field": 4.25,
        "secret_field": SECRET, "unexpected": SECRET,
    })
    assert outcome == {"status": "ok", "public_field": 4.25}
    assert SECRET not in json.dumps(outcome)
    error = view.project_observation("marine.read", {
        "status": "error", "error": SECRET, "message": SECRET,
    })
    assert error == {"status": "error", "error": "provider_call_failed"}


def test_model_observation_json_budget_fails_closed():
    view = captured()
    with pytest.raises(PolicyViolationError, match="byte cap"):
        view.project_observation("marine.read", {
            "status": "ok", "public_field": "x" * 32769,
            "secret_field": SECRET,
        })


def test_nested_sensitive_value_cannot_flow_to_agent():
    with pytest.raises(PolicyViolationError, match="nested output"):
        captured().project_observation("marine.read", {
            "status": "ok",
            "public_field": {"safe": "ok", "secret_field": SECRET},
        })


def test_report_drops_raw_query_gold_arguments_observations_and_final_text():
    view = captured()
    source = {
        "passed": True, "supported": True, "tool_call_count": 1,
        "policy_blocks": 0, "candidate_history": [
            ["marine.read", "archive.read"]
        ],
        "query": SECRET, "final_text": SECRET,
        "required_routes": ["archive.read"],
        "attempts": [{"route_id": "archive.read", "arguments": {"key": SECRET},
                      "observation": {"secret_field": SECRET}}],
        "turn_rows": [{"tool_calls": [{"arguments": {"key": SECRET}}],
                       "visible_observations": [{"secret_field": SECRET}]}],
    }
    redacted = view.public_trace(source)
    serialized = json.dumps(redacted)
    assert SECRET not in serialized
    assert "archive.read" not in serialized
    assert redacted["visible_candidate_counts"] == [1]
    assert redacted["passed"] is True
    assert redacted["tool_call_count"] == 1
    assert source["attempts"][0]["observation"]["secret_field"] == SECRET


@pytest.mark.parametrize("mutation", ("policy", "registry", "availability"))
def test_authority_swap_between_capture_and_model_publication_fails(mutation):
    router = fixture_router()
    view = captured(router)
    if mutation == "policy":
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    elif mutation == "registry":
        router.add_tool(ToolSpec(
            name="new_source",
            endpoints=[EndpointSpec(name="read", read_only=True)],
        ))
    else:
        router.planner.availability_predicate = lambda _tool, _endpoint: False
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        view.tool_definitions(["marine.read"])
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        view.public_trace({"passed": True})


def test_research_model_inputs_do_not_trigger_planning_or_tool_execution():
    router = fixture_router()

    def forbidden(*args, **kwargs):
        raise AssertionError("source discovery cannot execute")
    router.plan = forbidden
    router.execute = forbidden
    view = captured(router)
    assert view.tool_definitions(["marine.read"])
    assert view.project_observation("marine.read", {
        "status": "ok", "public_field": 3,
    })["public_field"] == 3


class CapturingSyntheticAgent:
    """Deterministic no-model tool-call control; retains model-facing messages."""

    def __init__(self, *, attack_router=None, wrong_route=False):
        self.calls = 0
        self.snapshots = []
        self.attack_router = attack_router
        self.wrong_route = wrong_route

    def generate(self, messages, tools):
        self.snapshots.append(json.dumps({
            "messages": messages, "tools": tools,
        }, ensure_ascii=False))
        if self.attack_router is not None:
            self.attack_router.authorization_policy = AuthorizationPolicy(
                default_effect="deny",
            )
        if self.calls == 0:
            selected = "archive__read" if self.wrong_route else "marine__read"
            text = "<tool_call>" + json.dumps({
                "name": selected, "arguments": {"place": "Seoul"},
            }) + "</tool_call>"
        else:
            text = "Final answer deliberately includes " + SECRET
        self.calls += 1
        return {
            "text": text,
            "input_tokens": 13,
            "tool_tokens": 7,
            "output_tokens": 5,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def scoped_synthetic_task():
    return {
        "semantic_task_id": "host-scope-E0-only",
        "language": "ko",
        "query": "marine public papers read values",
        "supported": True,
        "required_routes": ["marine.read"],
        "executor_fixture": {
            "steps": [{
                "route_id": "marine.read",
                "argument_rules": {"place": {"eq": "Seoul"}},
                "observation": {
                    "status": "ok",
                    "public_field": "public-data",
                    "secret_field": SECRET,
                    "unexpected": SECRET,
                },
            }],
        },
    }


def test_same_existing_agent_loop_uses_scoped_schema_and_observations_only():
    router = fixture_router()
    view = captured(router)
    agent = CapturingSyntheticAgent()
    observed = []

    def select(original_query, visible_ids):
        observed.append((original_query, visible_ids))
        assert "archive.read" not in visible_ids
        return ["marine.read"]

    result = run_generated_episode(
        agent, router.registry, scoped_synthetic_task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=select,
        experimental_agent_tool_surface=view,
    )
    assert result["passed"] is True
    assert result["tool_call_count"] == 1
    assert result["visible_candidate_counts"] == [1]
    assert len(observed) == 1 and len(agent.snapshots) == 2
    for model_view in agent.snapshots:
        assert SECRET not in model_view
        assert "secret_field" not in model_view
        assert "filter__secret_field" not in model_view
        assert "archive" not in model_view
    assert SECRET not in json.dumps(result)
    assert "required_routes" not in result
    assert "attempts" not in result
    assert "turn_rows" not in result
    assert "final_text" not in result


def test_scoped_agent_view_must_match_the_original_task_query():
    router = fixture_router()
    agent = CapturingSyntheticAgent()
    task = scoped_synthetic_task()
    task["query"] = "different user request"
    with pytest.raises(ValueError, match="principal-scoped query mismatch"):
        run_generated_episode(
            agent, router.registry, task,
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, _ids: ["marine.read"],
            experimental_agent_tool_surface=captured(router),
        )
    assert agent.calls == 0


def test_authority_revoked_during_model_generation_blocks_publication():
    router = fixture_router()
    agent = CapturingSyntheticAgent(attack_router=router)
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: ["marine.read"],
            experimental_agent_tool_surface=captured(router),
        )
    assert agent.calls == 1


def test_no_unapproved_route_can_be_processed_via_scoped_agent_hook():
    router = fixture_router()
    agent = CapturingSyntheticAgent(wrong_route=True)
    with pytest.raises(PolicyViolationError, match="unavailable scoped observation route"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: ["marine.read"],
            experimental_agent_tool_surface=captured(router),
        )
    assert agent.calls == 1


def test_scoped_surface_cannot_attach_to_legacy_frozen_condition_or_other_registry():
    router = fixture_router()
    view = captured(router)
    with pytest.raises(ValueError, match="isolated fixed5"):
        run_generated_episode(
            CapturingSyntheticAgent(), router.registry, scoped_synthetic_task(),
            "FULL",
            experimental_candidate_selector=lambda _query, ids: list(ids[:5]),
            experimental_agent_tool_surface=view,
        )
    other = fixture_router()
    with pytest.raises(ValueError, match="principal-scoped registry mismatch"):
        run_generated_episode(
            CapturingSyntheticAgent(), other.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: list(ids[:5]),
            experimental_agent_tool_surface=view,
        )


@pytest.mark.parametrize("mutation", ("roles", "attributes"))
def test_principal_claims_mutated_after_capture_fail_closed(mutation):
    router = fixture_router()
    principal = PrincipalContext(
        subject="mutable-viewer", roles=("viewer",),
        attributes={"region": "public"},
    )
    view = capture_authorized_agent_tool_surface(
        router, "marine public papers read values", principal=principal,
    )
    if mutation == "roles":
        principal.roles = ("outsider",)
    else:
        principal.attributes["region"] = "secret-region"
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        view.tool_definitions(["marine.read"])
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        view.project_observation("marine.read", {
            "status": "ok", "public_field": "public",
        })
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        view.public_trace({"passed": True})


def test_principal_roles_revoked_during_agent_inference_fail_closed():
    router = fixture_router()
    principal = PrincipalContext(subject="revoke-on-model", roles=("viewer",))
    view = capture_authorized_agent_tool_surface(
        router, "marine public papers read values", principal=principal,
    )

    class RevokingAgent(CapturingSyntheticAgent):
        def generate(self, messages, tools):
            answer = super().generate(messages, tools)
            principal.roles = ("outsider",)
            return answer

    agent = RevokingAgent()
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, _ids: ["marine.read"],
            experimental_agent_tool_surface=view,
        )
    assert agent.calls == 1


def test_two_step_agent_receives_only_allowed_state_for_next_tool_argument():
    router = fixture_router()
    view = captured(router)
    source_task = {
        "semantic_task_id": "scoped-two-step-E0",
        "language": "ko",
        "query": "marine public papers read values",
        "supported": True,
        "required_routes": ["marine.read", "papers.read"],
        "executor_fixture": {
            "steps": [
                {
                    "route_id": "marine.read",
                    "argument_rules": {"place": {"eq": "Seoul"}},
                    "observation": {
                        "public_field": "record-321",
                        "secret_field": SECRET,
                    },
                },
                {
                    "route_id": "papers.read",
                    "argument_rules": {"place": {"state": "public_field"}},
                    "observation": {
                        "public_field": "verified",
                        "secret_field": SECRET,
                    },
                },
            ],
        },
    }

    class TwoStepAgent(CapturingSyntheticAgent):
        def generate(self, messages, tools):
            self.snapshots.append(json.dumps({
                "messages": messages, "tools": tools,
            }, ensure_ascii=False))
            if self.calls == 0:
                name, place = "marine__read", "Seoul"
            elif self.calls == 1:
                assert "record-321" in self.snapshots[-1]
                name, place = "papers__read", "record-321"
            else:
                name, place = None, None
            self.calls += 1
            if name is None:
                text = "Done."
            else:
                text = "<tool_call>" + json.dumps({
                    "name": name, "arguments": {"place": place},
                }) + "</tool_call>"
            return {
                "text": text, "input_tokens": 12, "tool_tokens": 5,
                "output_tokens": 5, "latency_ms": 0.0,
                "context_overflow": False,
            }

    agent = TwoStepAgent()
    result = run_generated_episode(
        agent, router.registry, source_task,
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, _ids: [
            "marine.read", "papers.read",
        ],
        experimental_agent_tool_surface=view,
    )
    assert result["passed"] is True
    assert result["task_complete"] is True
    assert result["tool_call_count"] == 2
    assert result["visible_candidate_counts"] == [2]
    assert len(agent.snapshots) == 3
    for model_snapshot in agent.snapshots:
        assert SECRET not in model_snapshot
        assert "secret_field" not in model_snapshot
    assert SECRET not in json.dumps(result)
    assert "attempts" not in result


def bind_read_fixture(router, *, seen):
    def invoker(endpoint, arguments):
        seen.append((endpoint, dict(arguments)))
        return {"public_field": "record-321", "secret_field": SECRET}

    tool = router.registry.get("marine")
    router.executor.bind(
        tool.key, invoker, expected_fingerprint=tool.fingerprint,
    )


@pytest.mark.asyncio
async def test_actual_router_execute_invokes_bound_host_once_and_projects_fields():
    """Unlike synthetic FrozenCorpusExecutor, this uses actual router.execute."""
    router = fixture_router()
    seen = []
    bind_read_fixture(router, seen=seen)
    view = captured(router)
    returned = await execute_scoped_host_call(
        view, selected_route_ids=["marine.read"],
        route_id="marine.read", arguments={"place": "Seoul"},
    )
    assert returned == {"status": "ok", "public_field": "record-321"}
    assert seen == [("read", {"place": "Seoul"})]
    assert SECRET not in json.dumps(returned)


@pytest.mark.asyncio
@pytest.mark.parametrize(("selected", "route", "args"), (
    (["marine.read"], "archive.read", {"place": "Seoul"}),
    (["archive.read"], "archive.read", {"place": "Seoul"}),
    (["marine.read"], "marine.read", {"filter__secret_field": SECRET}),
    (["marine.read"], "marine.read", {"place": "Seoul", "hidden": SECRET}),
    (["marine.read"], "marine.read", {}),
    (["marine.read", "marine.read"], "marine.read", {"place": "Seoul"}),
    (["marine.read"], "marine.read", {"place": "Seoul", "other": 1}),
))
async def test_host_invocation_rejects_unselected_hidden_or_malformed_before_io(
    selected, route, args,
):
    router = fixture_router()
    seen = []
    bind_read_fixture(router, seen=seen)
    with pytest.raises((PolicyViolationError, ValueError)):
        await execute_scoped_host_call(
            captured(router),
            selected_route_ids=selected, route_id=route,
            arguments=args,
        )
    assert seen == []


@pytest.mark.asyncio
async def test_host_invocation_rechecks_principal_revocation_before_real_io():
    router = fixture_router()
    seen = []
    bind_read_fixture(router, seen=seen)
    principal = PrincipalContext(subject="alice", roles=("viewer",))
    view = captured(router, principal=principal)
    principal.roles = ("outsider",)
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        await execute_scoped_host_call(
            view, selected_route_ids=["marine.read"],
            route_id="marine.read", arguments={"place": "Seoul"},
        )
    assert seen == []


@pytest.mark.asyncio
async def test_host_invocation_requires_actual_bound_trusted_invoker():
    router = fixture_router()
    with pytest.raises((PolicyViolationError, ValueError, RuntimeError)):
        await execute_scoped_host_call(
            captured(router), selected_route_ids=["marine.read"],
            route_id="marine.read", arguments={"place": "Seoul"},
        )


@pytest.mark.asyncio
async def test_host_invocation_denies_a_registered_mutation_before_real_io():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="actions.update", roles_any=("viewer",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="actions",
        endpoints=[EndpointSpec(
            name="update", read_only=False, destructive=True,
            parameters=[ParameterSpec(
                name="place", required=True, json_schema={"type": "string"},
            )],
            output_fields=[FieldSpec(name="public_field")],
        )],
    ))
    tool = router.registry.get("actions")
    invoked = []
    router.executor.bind(
        tool.key,
        lambda endpoint, arguments: invoked.append((endpoint, arguments)),
        expected_fingerprint=tool.fingerprint,
    )
    view = capture_authorized_agent_tool_surface(
        router, "actions update public_field", principal=VIEWER,
    )
    assert "actions.update" in view.visible_route_ids
    with pytest.raises(PolicyViolationError, match="scoped host invocation denied"):
        await execute_scoped_host_call(
            view, selected_route_ids=["actions.update"],
            route_id="actions.update", arguments={"place": "Seoul"},
        )
    assert invoked == []


@pytest.mark.asyncio
async def test_host_invocation_fails_closed_on_nested_real_provider_result():
    router = fixture_router()
    tool = router.registry.get("marine")
    invoked = []
    def invoker(endpoint, arguments):
        invoked.append((endpoint, arguments))
        return {"public_field": {"safe": 1, "secret_field": SECRET}}
    router.executor.bind(
        tool.key, invoker, expected_fingerprint=tool.fingerprint,
    )
    with pytest.raises(PolicyViolationError, match="nested output"):
        await execute_scoped_host_call(
            captured(router),
            selected_route_ids=["marine.read"],
            route_id="marine.read", arguments={"place": "Seoul"},
        )
    assert len(invoked) == 1


@pytest.mark.asyncio
async def test_host_invoker_private_exception_is_never_returned_to_agent():
    router = fixture_router()
    tool = router.registry.get("marine")
    events = []

    def forbidden(endpoint, arguments):
        events.append((endpoint, arguments))
        raise RuntimeError("provider failed: " + SECRET)

    router.executor.bind(
        tool.key, forbidden, expected_fingerprint=tool.fingerprint,
    )
    with pytest.raises(PolicyViolationError) as captured_error:
        await execute_scoped_host_call(
            captured(router),
            selected_route_ids=["marine.read"],
            route_id="marine.read",
            arguments={"place": "Seoul"},
        )
    assert len(events) == 1
    assert SECRET not in str(captured_error.value)
    assert "provider failed" not in str(captured_error.value)


@pytest.mark.asyncio
async def test_host_invocation_rejects_planner_added_registered_optional_argument():
    """Planning must not expand model-supplied args before actual host IO."""
    router = fixture_router()
    invoked = []
    bind_read_fixture(router, seen=invoked)
    original_planner = router.aplan_executable_authorized

    async def planner_with_extra_argument(request, *, principal):
        plan = await original_planner(request, principal=principal)
        # This optional parameter exists in the source schema, but was never
        # selected or disclosed to the principal-scoped model.
        plan.calls[0].arguments["filter__secret_field"] = SECRET
        return plan

    router.aplan_executable_authorized = planner_with_extra_argument
    with pytest.raises(
        PolicyViolationError, match="scoped host invocation denied",
    ):
        await execute_scoped_host_call(
            captured(router),
            selected_route_ids=["marine.read"],
            route_id="marine.read",
            arguments={"place": "Seoul"},
        )
    assert invoked == []


def test_scoped_agent_trace_is_derived_only_after_execution_and_redacted():
    router = fixture_router()
    view = captured(router)
    agent = CapturingSyntheticAgent()
    trace = run_generated_episode(
        agent, router.registry, scoped_synthetic_task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, _ids: ["marine.read"],
        experimental_agent_tool_surface=view,
        experimental_e0_trace_provenance=E0TraceProvenance(
            source_revision="a" * 40,
            source_sha256="b" * 64,
            hmac_key=b"trusted-only-e0-key-0123456789",
            seed=123,
        ),
    )
    assert trace["passed"] is True
    assert trace["e0_stage_evidence"]["observed_stages"] == ["passed"]
    assert trace["e0_stage_evidence"]["visible_candidate_counts"] == [1]
    assert trace["e0_stage_evidence"]["independent_e2_qualified"] is False
    assert trace["e0_stage_evidence"]["task_hmac_sha256"]
    assert agent.calls == 2
    serialized = json.dumps(trace)
    assert SECRET not in serialized
    assert "semantic_task_id" not in serialized
    assert "required_routes" not in serialized
    assert "attempts" not in serialized
    assert "original_query" not in serialized


def test_e0_trace_provenance_cannot_attach_to_non_scoped_or_frozen_episode():
    router = fixture_router()
    agent = CapturingSyntheticAgent()
    provenance = E0TraceProvenance(
        source_revision="a" * 40,
        source_sha256="b" * 64,
        hmac_key=b"trusted-only-e0-key-0123456789",
        seed=123,
    )
    with pytest.raises(ValueError, match="trusted scoped fixed5"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, _ids: ["marine.read"],
            experimental_e0_trace_provenance=provenance,
        )
    with pytest.raises(ValueError, match="trusted scoped fixed5"):
        run_generated_episode(
            agent, router.registry, scoped_synthetic_task(), "FULL",
            experimental_agent_tool_surface=captured(router),
            experimental_e0_trace_provenance=provenance,
        )
    assert agent.calls == 0



def test_captured_output_visibility_map_mutation_rejects_private_observation():
    view = captured()
    view._visible_output_names["marine.read"] = frozenset({
        "public_field", "secret_field",
    })
    with pytest.raises(PolicyViolationError, match="captured authorized source identity drift"):
        view.project_observation("marine.read", {
            "status": "ok", "public_field": "ok", "secret_field": SECRET,
        })


def test_captured_route_identity_and_definition_map_changes_rejected():
    from dataclasses import replace

    view = captured()
    forged = replace(view, visible_route_ids=tuple(reversed(view.visible_route_ids)))
    with pytest.raises(PolicyViolationError, match="captured authorized source identity drift"):
        forged.tool_definitions(["marine.read"])
    original = captured()
    original._tool_definitions["marine.read"]["parameters"]["properties"][
        "private_unregistered_field"
    ] = {"type": "string"}
    with pytest.raises(PolicyViolationError, match="captured authorized source identity drift"):
        original.tool_definitions(["marine.read"])


def test_empty_authorized_catalog_receipt_is_valid_and_not_no_fit():
    view = captured(principal=OUTSIDER)
    assert view.visible_route_ids == ()
    assert view.tool_definitions([]) == []
    assert view.executable_authority is False


def test_optin_fixture_agent_can_grade_hallucinated_unavailable_route_without_leak():
    """This opt-in turns one blocked *fictional* tool attempt into an E0 failure."""
    router = fixture_router()
    view = captured(router)
    agent = CapturingSyntheticAgent(wrong_route=True)
    result = run_generated_episode(
        agent, router.registry, scoped_synthetic_task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, _ids: ["marine.read"],
        experimental_agent_tool_surface=view,
        experimental_block_unavailable_observation=True,
    )
    assert result["passed"] is False
    assert result["tool_call_count"] == 1
    assert result["unauthorized_destructive_executions"] == 0
    assert result["visible_candidate_counts"] == [1]
    assert len(agent.snapshots) == 2
    assert "unavailable_scoped_route" in agent.snapshots[1]
    assert SECRET not in agent.snapshots[1]
    assert "secret_field" not in agent.snapshots[1]
    # The assistant's own invalid tool name can appear in conversation,
    # but the host must not reveal the hidden route's real description.
    assert "Read archive values" not in agent.snapshots[1]
    assert SECRET not in json.dumps(result)


def test_blocked_unavailable_agent_route_flag_rejects_legacy_or_unscoped_use():
    router = fixture_router()
    view = captured(router)
    for condition, scoped, selector in (
        ("FULL", None, None),
        (EXPERIMENTAL_FIXED5_CONDITION, None, lambda _query, _ids: ["marine.read"]),
        (EXPERIMENTAL_FIXED5_CONDITION, view, None),
    ):
        with pytest.raises(ValueError, match="blocked unsupported observation"):
            run_generated_episode(
                CapturingSyntheticAgent(), router.registry, scoped_synthetic_task(),
                condition,
                experimental_agent_tool_surface=scoped,
                experimental_candidate_selector=selector,
                experimental_block_unavailable_observation=True,
            )


def test_new_grading_flag_must_be_actual_boolean():
    router = fixture_router()
    view = captured(router)
    with pytest.raises(ValueError, match="blocked unsupported observation"):
        run_generated_episode(
            CapturingSyntheticAgent(), router.registry, scoped_synthetic_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_agent_tool_surface=view,
            experimental_candidate_selector=lambda _query, _ids: ["marine.read"],
            experimental_block_unavailable_observation=1,
        )


@pytest.mark.parametrize("policy_mutation", (
    "default_effect", "existing_rule", "data_scope",
    "compiled_rule_index", "compiled_data_index", "compiled_rule_objects",
))
def test_inplace_authority_mutation_between_agent_turns_fails_closed(policy_mutation):
    """The opt-in view must reject identity-stable but semantically changed policy."""
    router = fixture_router()
    view = captured(router)
    policy = router.authorization_policy
    assert policy is not None
    if policy_mutation == "default_effect":
        object.__setattr__(policy, "default_effect", "allow")
    elif policy_mutation == "existing_rule":
        object.__setattr__(policy.rules[1], "effect", "deny")
    elif policy_mutation == "data_scope":
        object.__setattr__(policy.data_rules[0], "hidden_fields", ())
    elif policy_mutation == "compiled_rule_index":
        policy._rule_index.partitions.clear()
    elif policy_mutation == "compiled_rule_objects":
        object.__setattr__(policy._rule_index, "rules", ())
    else:
        policy._data_rule_index.partitions.clear()
    # Same policy object still passes the legacy identity witness.
    router._check_retrieval_authority_witness(view.witness)
    with pytest.raises(PolicyViolationError, match="authorization policy modified in place"):
        view.tool_definitions(["marine.read"])
    with pytest.raises(PolicyViolationError, match="authorization policy modified in place"):
        view.project_observation("marine.read", {
            "status": "ok", "public_field": "public",
        })
    with pytest.raises(PolicyViolationError, match="authorization policy modified in place"):
        view.public_trace({"passed": True})


def test_policy_mutation_during_source_retrieval_fails_before_model_view(monkeypatch):
    router = fixture_router()
    policy = router.authorization_policy
    assert policy is not None
    original = router.retrieve_authorized

    def mutating_retrieval(*args, **kwargs):
        result = original(*args, **kwargs)
        object.__setattr__(policy.data_rules[0], "hidden_fields", ())
        return result

    monkeypatch.setattr(router, "retrieve_authorized", mutating_retrieval)
    with pytest.raises(PolicyViolationError, match="policy modified during source capture"):
        captured(router)


def test_catalog_index_only_discloses_authorized_route_titles_and_visible_fields():
    """The model receives a table of contents, never executable authority."""
    view = captured()
    index = view.catalog_index()
    assert type(index) is tuple
    assert len(index) == len(view.visible_route_ids) == 2
    assert tuple(route for route, _ in index) == view.visible_route_ids
    assert all(type(item) is tuple and len(item) == 2 for item in index)
    assert "public_field" in json.dumps(index)
    assert SECRET not in json.dumps(index)
    assert "secret_field" not in json.dumps(index)
    assert "archive.read" not in json.dumps(index)
    assert "registered_route_count" not in json.dumps(index)
    assert "parameters" not in json.dumps(index)
    assert view.executable_authority is False

    # The application/agent picks an ID from the index, then asks the trusted
    # router for that entry's *separate* schema. Neither step executes a tool.
    chosen = index[0][0]
    detail = view.tool_definitions([chosen], k=1)
    assert len(detail) == 1
    assert detail[0]["name"] == chosen.replace(".", "__")


def test_catalog_index_never_plans_or_invokes_a_tool(monkeypatch):
    view = captured()
    router = view.router

    def forbidden(*_args, **_kwargs):
        raise AssertionError("catalog reading must never plan or execute")

    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert len(view.catalog_index()) == 2
    assert len(view.tool_definitions(["marine.read"], k=1)) == 1


@pytest.mark.parametrize("budget", (0, -1, True, 131073, "32768"))
def test_catalog_index_invalid_byte_budget_fails_closed(budget):
    with pytest.raises(ValueError, match="invalid scoped catalog index byte budget"):
        captured().catalog_index(max_json_bytes=budget)


def test_catalog_index_fails_closed_instead_of_truncating_source():
    view = captured()
    with pytest.raises(ValueError, match="scoped catalog index exceeds research byte cap"):
        view.catalog_index(max_json_bytes=2)
    # Lowered budget cannot trim or reorder authorized native routes.
    assert tuple(route for route, _ in view.catalog_index()) == view.visible_route_ids


def test_catalog_index_no_visible_routes_is_not_a_no_fit_verdict():
    view = captured(principal=OUTSIDER)
    assert view.catalog_index() == ()
    assert view.executable_authority is False
    assert view.independent_quality_evidence is False


def test_catalog_index_rejects_mutated_source_or_revoked_authority():
    from dataclasses import replace

    view = captured()
    forged = replace(view, _semantic_source_routes=tuple(
        reversed(view._semantic_source_routes)
    ))
    with pytest.raises(PolicyViolationError):
        forged.catalog_index()
    # The retrieval witness tracks the trusted planner availability source.
    # Temporary execution cooldown is not equivalent to source policy drift.
    view.router.planner.availability_predicate = lambda _tool, _endpoint: False
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        view.catalog_index()


@pytest.mark.parametrize("preserve_rank", (False, True))
def test_scoped_fixed5_ranked_model_disclosure_is_explicit_opt_in(preserve_rank):
    """Model-visible order, not just scorer receipt, is the controlled variable."""
    router = fixture_router()
    view = captured(router)
    agent = CapturingSyntheticAgent()
    ranker_order = ["papers.read", "marine.read"]  # deliberately nonalphabetic

    row = run_generated_episode(
        agent, router.registry, scoped_synthetic_task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, ids: [
            route for route in ranker_order if route in ids
        ],
        experimental_agent_tool_surface=view,
        experimental_preserve_rank_order=preserve_rank,
    )
    observed_tools = json.loads(agent.snapshots[0])["tools"]
    expected_routes = (
        ranker_order if preserve_rank else sorted(ranker_order)
    )
    expected_tools = view.tool_definitions(expected_routes)
    assert [tool["name"] for tool in observed_tools] == [
        tool["name"] for tool in expected_tools
    ]
    assert row["passed"] is True
    assert row["visible_candidate_counts"] == [2]
    assert row["tool_call_count"] == 1
    for exposure in agent.snapshots:
        assert SECRET not in exposure
        assert "secret_field" not in exposure
        assert "archive__read" not in exposure


@pytest.mark.parametrize("bad", (None, 1, "yes"))
def test_ranked_disclosure_refuses_nonboolean_flags(bad):
    router = fixture_router()
    with pytest.raises(ValueError, match="ranked tool disclosure"):
        run_generated_episode(
            CapturingSyntheticAgent(), router.registry,
            scoped_synthetic_task(), EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, ids: list(ids),
            experimental_agent_tool_surface=captured(router),
            experimental_preserve_rank_order=bad,
        )


def test_ranked_disclosure_refuses_unscoped_or_frozen_execution():
    router = fixture_router()
    def choose(_query, ids):
        return list(ids[:2])

    with pytest.raises(ValueError, match="ranked tool disclosure"):
        run_generated_episode(
            CapturingSyntheticAgent(), router.registry,
            scoped_synthetic_task(), EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=choose,
            experimental_preserve_rank_order=True,
        )
    with pytest.raises(ValueError, match="ranked tool disclosure"):
        run_generated_episode(
            CapturingSyntheticAgent(), router.registry,
            scoped_synthetic_task(), "SR-5",
            experimental_candidate_selector=choose,
            experimental_agent_tool_surface=captured(router),
            experimental_preserve_rank_order=True,
        )
