"""No-model E0 bridge tests; not real model accuracy or external E2."""
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
from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PlanningError
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_fixed5_decision_bridge import (
    AuthorizedFixed5DecisionSelector,
)
from scripts.research_bounded_authorized_semantic_diagnostic import (
    propose_bounded_semantic_shortlist,
)

SECRET = "PRIVATE-CANARY-1481"
VIEWER = PrincipalContext(subject="synthetic-viewer", roles=("viewer",))


def fixture_router() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(effect="deny", operation="archive.*",
                              roles_any=("viewer",)),
            AuthorizationRule(effect="allow", operation="*.*",
                              roles_any=("viewer",)),
        ),
        data_rules=(DataScopeRule(
            operation="*.*", roles_any=("viewer",),
            hidden_fields=("secret_field",),
        ),),
    ))
    for name in ("marine", "papers", "archive"):
        router.add_tool(ToolSpec(
            name=name,
            description=f"Public marine papers read {name} {SECRET}",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                description=f"marine papers read from {name} {SECRET}",
                parameters=[ParameterSpec(
                    name="place", required=True, location="query",
                    description=f"location {SECRET}",
                    json_schema={"type": "string", "examples": [SECRET]},
                )],
                output_fields=[
                    FieldSpec(name="public_field"),
                    FieldSpec(name="secret_field"),
                ],
            )],
        ))
    return router


def fixture_view(router=None, query="marine papers read"):
    router = router or fixture_router()
    return capture_authorized_agent_tool_surface(
        router, query, principal=VIEWER,
    )


def choose_marine(request):
    assert request.query
    assert request.max_selections == min(5, len(request.options))
    assert {option.label for option in request.options} == {
        "marine.read", "papers.read",
    }
    assert all(SECRET not in option.description for option in request.options)
    return {"selections": [{
        "option_id": next(
            option.id for option in request.options
            if option.label == "marine.read"
        ),
    }]}


def task(query="marine papers read"):
    return {
        "semantic_task_id": "E0-bridge-not-independent",
        "query": query,
        "language": "ko",
        "supported": True,
        "required_routes": ["marine.read"],
        "executor_fixture": {"steps": [{
            "route_id": "marine.read",
            "argument_rules": {"place": {"eq": "Seoul"}},
            "observation": {
                "status": "ok",
                "public_field": "record-321",
                "secret_field": SECRET,
            },
        }]},
    }


class SyntheticAgent:
    def __init__(self):
        self.calls = 0
        self.prompts = []

    def generate(self, messages, tools):
        self.prompts.append(json.dumps(
            {"messages": messages, "tools": tools}, ensure_ascii=False,
        ))
        if self.calls == 0:
            content = (
                '<tool_call>{"name":"marine__read",'
                '"arguments":{"place":"Seoul"}}</tool_call>'
            )
        else:
            content = "Completed without sensitive data."
        self.calls += 1
        return {
            "text": content, "input_tokens": 14,
            "tool_tokens": 9, "output_tokens": 7,
            "latency_ms": 0.0, "context_overflow": False,
        }


def test_real_existing_agent_episode_uses_scoped_decision_callback():
    view = fixture_view()
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(choose_marine),
    )
    agent = SyntheticAgent()
    result = run_generated_episode(
        agent, view.router.registry, task(),
        EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert result["passed"] is True
    assert result["tool_call_count"] == 1
    assert result["visible_candidate_counts"] == [1]
    assert selector.last_status == "unverified_partial_k_model_ranking"
    assert selector.last_model_input_bytes > 0
    assert selector.calibrated_no_fit is False
    assert selector.executable_authority is False
    assert selector.independent_quality_evidence is False
    assert agent.calls == 2
    assert all(SECRET not in prompt for prompt in agent.prompts)
    assert SECRET not in json.dumps(result)
    assert "required_routes" not in result


@pytest.mark.parametrize("query", (
    "marine papers read",
    "marine 해양 자료를 읽어주세요",
    "marine 海洋データを読んで",
))
def test_model_receives_original_query_and_only_authorized_source(query):
    view = fixture_view(query=query)
    observed = []

    def backend(request):
        observed.append(request.query)
        assert {o.label for o in request.options}.issubset(
            {"marine.read", "papers.read"}
        )
        assert all(SECRET not in o.description for o in request.options)
        return {"selections": [{"option_id": request.options[0].id}]}

    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(backend),
    )
    ids = selector(query, view.visible_route_ids)
    assert len(ids) == 1
    assert ids[0] in view.visible_route_ids
    assert observed == [query]


def test_backend_abstention_never_becomes_calibrated_no_fit():
    view = fixture_view()
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(lambda _: {"abstained": True}),
    )
    assert selector(view.original_query, view.visible_route_ids) == []
    assert selector.last_status == "backend_abstained_not_calibrated_no_fit"
    assert selector.calibrated_no_fit is False


@pytest.mark.parametrize("bad", (
    {"selections": [{"option_id": "native:999"}]},
    {"selections": [{"option_id": "native:0"}] * 2},
))
def test_forged_duplicate_or_unregistered_model_choice_is_rejected(bad):
    view = fixture_view()
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(lambda _: bad),
    )
    with pytest.raises((PlanningError, ValueError)):
        selector(view.original_query, view.visible_route_ids)


def test_wrong_query_or_forged_source_set_denied_before_backend_call():
    view = fixture_view()
    def forbidden(_):
        raise AssertionError("must not call model")
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(forbidden),
    )
    with pytest.raises(PolicyViolationError, match="query mismatch"):
        selector("different request", view.visible_route_ids)
    with pytest.raises(PolicyViolationError, match="query mismatch"):
        selector(view.original_query, ("archive.read",))
    with pytest.raises(PolicyViolationError, match="query mismatch"):
        selector(view.original_query, list(view.visible_route_ids))


def test_principal_revocation_during_backend_inference_fails_closed():
    router = fixture_router()
    principal = PrincipalContext(subject="mutable", roles=("viewer",))
    view = capture_authorized_agent_tool_surface(
        router, "marine papers read", principal=principal,
    )
    def revoke(request):
        principal.roles = ("outsider",)
        return {"selections": [{"option_id": request.options[0].id}]}
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(revoke),
    )
    with pytest.raises(PolicyViolationError, match="principal claims changed"):
        selector(view.original_query, view.visible_route_ids)


def test_registry_read_copy_mutation_cannot_change_authoritative_source():
    view = fixture_view()
    original_fp = view.router.registry.get("marine").fingerprint

    def mutate_detached_copy(request):
        # Registry.get() returns a detached public copy, not an in-place
        # authoritative mutation. Only registered source updates can alter it.
        view.router.registry.get("marine").description = "detached test change"
        return {"selections": [{"option_id": request.options[0].id}]}

    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(mutate_detached_copy),
    )
    assert len(selector(view.original_query, view.visible_route_ids)) == 1
    assert view.router.registry.get("marine").fingerprint == original_fp


def test_authoritative_registry_replacement_during_backend_fails_closed():
    view = fixture_view()

    def replace_authoritative_source(request):
        view.router.add_tool(ToolSpec(
            name="new_source",
            endpoints=[EndpointSpec(name="read", read_only=True)],
        ))
        return {"selections": [{"option_id": request.options[0].id}]}

    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(replace_authoritative_source),
    )
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        selector(view.original_query, view.visible_route_ids)


def test_research_backend_never_calls_planning_or_provider_execution():
    view = fixture_view()
    def forbidden(*args, **kwargs):
        raise AssertionError("model ranking must not execute")
    view.router.plan = forbidden
    view.router.execute = forbidden
    view.router.aplan_executable_authorized = forbidden
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(choose_marine),
    )
    assert selector(view.original_query, view.visible_route_ids) == [
        "marine.read",
    ]


def test_invalid_input_budget_rejected_without_inference():
    view = fixture_view()
    for bad in (0, True, -1, 262145):
        with pytest.raises(ValueError, match="comparator input budget"):
            AuthorizedFixed5DecisionSelector(
                view, CallableDecisionBackend(choose_marine),
                max_model_input_bytes=bad,
            )
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(choose_marine),
        max_model_input_bytes=1,
    )
    with pytest.raises(ValueError, match="bounded research limit"):
        selector(view.original_query, view.visible_route_ids)


def test_explicit_256k_optin_keeps_default_128k_unchanged():
    view = fixture_view()
    ordinary = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(choose_marine),
    )
    extended = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(choose_marine),
        max_model_input_bytes=262144,
    )
    assert ordinary.max_model_input_bytes == 131072
    assert extended.max_model_input_bytes == 262144
    assert ordinary(view.original_query, view.visible_route_ids) == ["marine.read"]
    assert extended(view.original_query, view.visible_route_ids) == ["marine.read"]


@pytest.mark.parametrize("query", (
    "Find field-scoped marine papers",
    "해양 논문에서 공개 정보를 조회해 주세요",
    "海洋研究の公開情報を検索してください",
))
def test_captured_comparator_has_byte_identical_model_inputs_to_live_source(query):
    router = fixture_router()
    view = fixture_view(router, query)
    captured_decisions = []

    def identical_top1(request):
        captured_decisions.append(request.model_dump_json())
        return {"selections": [{"option_id": request.options[0].id}]}

    backend = CallableDecisionBackend(identical_top1)
    live = propose_bounded_semantic_shortlist(
        router, query, principal=VIEWER, backend=backend, k=5,
    )
    optimized = AuthorizedFixed5DecisionSelector(view, backend)
    selected = optimized(query, view.visible_route_ids)
    assert tuple(selected) == live.route_ids
    assert optimized.last_status == live.status
    assert optimized.last_model_input_bytes == live.model_input_bytes
    assert captured_decisions[0] == captured_decisions[1]
    assert SECRET not in captured_decisions[0]
    assert optimized.calibrated_no_fit is False
    assert optimized.executable_authority is False


def test_captured_source_has_no_second_authorized_catalog_lookup():
    view = fixture_view()
    selector = AuthorizedFixed5DecisionSelector(
        view, CallableDecisionBackend(choose_marine),
    )
    def forbidden_reretrieve(*args, **kwargs):
        raise AssertionError("same-request full-catalog reread is forbidden")
    view.router.retrieve_authorized = forbidden_reretrieve
    assert selector(view.original_query, view.visible_route_ids) == ["marine.read"]


def test_foreign_principal_or_query_cannot_reuse_authorized_capture():
    view = fixture_view()
    backend = CallableDecisionBackend(choose_marine)
    impostor = PrincipalContext(subject="different-reader", roles=("viewer",))
    with pytest.raises(PolicyViolationError, match="source identity drift"):
        propose_bounded_semantic_shortlist(
            view.router, view.original_query,
            principal=impostor, backend=backend,
            authorized_source_view=view,
        )
    with pytest.raises(PolicyViolationError, match="source identity drift"):
        propose_bounded_semantic_shortlist(
            view.router, "malicious substituted query",
            principal=VIEWER, backend=backend,
            authorized_source_view=view,
        )


def test_mutated_source_record_cannot_sneak_into_immutable_capture():
    from dataclasses import replace

    view = fixture_view()
    route = view._semantic_source_routes[0]
    bad = replace(route, route_id="archive.read")
    tampered = replace(
        view, _semantic_source_routes=(bad, *view._semantic_source_routes[1:]),
    )
    with pytest.raises(PolicyViolationError, match="source identity drift"):
        propose_bounded_semantic_shortlist(
            tampered.router, tampered.original_query,
            principal=VIEWER, backend=CallableDecisionBackend(choose_marine),
            authorized_source_view=tampered,
        )
