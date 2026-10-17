"""E0-only tests of fixed hybrid routing; no measured real-model accuracy."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
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
from scripts.research_authorized_hybrid_fixed5 import (
    FIXED_RRF_CONSTANT,
    AuthorizedHybridFixed5Selector,
)

SECRET = "HIDDEN-HYBRID-1483"
PRINCIPAL = PrincipalContext(subject="safe-reader", roles=("reader",))


def scoped(query="Read marine data"):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(effect="deny", operation="archive.*",
                              roles_any=("reader",)),
            AuthorizationRule(effect="allow", operation="*.*",
                              roles_any=("reader",)),
        ),
        data_rules=(DataScopeRule(
            operation="*.*", roles_any=("reader",), hidden_fields=("secret",),
        ),),
    ))
    for index in range(7):
        router.add_tool(ToolSpec(
            name=f"svc{index}",
            description=f"Secret in free prose: {SECRET}",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                description=f"Untrusted publisher prose {SECRET}",
                output_fields=[FieldSpec(name="public"), FieldSpec(name="secret")],
            )],
        ))
    router.add_tool(ToolSpec(
        name="archive",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    return capture_authorized_agent_tool_surface(router, query, principal=PRINCIPAL)


def select_deep(request):
    assert request.max_selections == 5
    assert len(request.options) == 7
    assert not any(o.label == "archive.read" for o in request.options)
    assert all(SECRET not in o.description for o in request.options)
    return {"selections": [{
        "option_id": next(o.id for o in request.options if o.label == "svc6.read"),
    }]}


def test_hybrid_is_exact_k5_and_authorized_deep_semantic_route_is_retained():
    view = scoped()
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(select_deep),
    )
    selected = selector(view.original_query, view.visible_route_ids)
    assert len(selected) == 5
    assert len(set(selected)) == 5
    assert "svc6.read" in selected
    assert set(selected).issubset(view.visible_route_ids)
    assert selector.last_status == "partial_semantic_lexical_rrf_fill_unverified"
    assert selector.last_semantic_status == "unverified_partial_k_model_ranking"
    assert selector.last_model_input_bytes > 0
    assert selector.calibrated_no_fit is False
    assert selector.executable_authority is False
    assert selector.independent_quality_evidence is False
    assert FIXED_RRF_CONSTANT == 60


class ScriptedAgent:
    def __init__(self):
        self.turns = 0
        self.observed = []

    def generate(self, messages, tools):
        self.observed.append(json.dumps(
            {"messages": messages, "tools": tools}, ensure_ascii=False,
        ))
        text = (
            '<tool_call>{"name":"svc6__read","arguments":{}}</tool_call>'
            if self.turns == 0 else "Synthetic only done."
        )
        self.turns += 1
        return {
            "text": text,
            "input_tokens": 17,
            "tool_tokens": 7,
            "output_tokens": 9,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def test_hybrid_runs_existing_principal_scoped_agent_fixture_not_new_executor():
    view = scoped()
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(select_deep),
    )
    task = {
        "semantic_task_id": "synthetic-test-not-E2",
        "query": view.original_query,
        "language": "ko",
        "supported": True,
        "required_routes": ["svc6.read"],
        "executor_fixture": {"steps": [{
            "route_id": "svc6.read", "argument_rules": {},
            "observation": {"public": "answer", "secret": SECRET},
        }]},
    }
    agent = ScriptedAgent()
    result = run_generated_episode(
        agent, view.router.registry, task, EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=selector,
        experimental_agent_tool_surface=view,
    )
    assert result["passed"] is True
    assert result["visible_candidate_counts"] == [5]
    assert result["tool_call_count"] == 1
    assert len(agent.observed) == 2
    assert all(SECRET not in seen for seen in agent.observed)
    assert SECRET not in json.dumps(result)
    assert "required_routes" not in json.dumps(result)


def test_abstaining_model_falls_back_to_lexical_not_calibrated_no_fit():
    view = scoped("unsupported question")
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(lambda _: {"abstained": True}),
    )
    expected = [
        c.route_id for c in view.router.retrieve_authorized(
            view.original_query, principal=PRINCIPAL, k=7,
        ).candidates[:5]
    ]
    actual = selector(view.original_query, view.visible_route_ids)
    assert actual == expected
    assert selector.last_status == "semantic_abstained_lexical_fallback_not_no_fit"
    assert selector.calibrated_no_fit is False


@pytest.mark.parametrize("query", (
    "Read marine data",
    "바다 데이터를 조회해 주세요",
    "海洋データを取得してください",
))
def test_original_en_ko_ja_query_forwarded_without_gold(query):
    view = scoped(query)
    seen = []
    def backend(request):
        seen.append(request.query)
        return {"selections": [{"option_id": request.options[0].id}]}
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(backend),
    )
    assert len(selector(query, view.visible_route_ids)) == 5
    assert seen == [query]


def test_source_and_query_forgery_rejected_before_model_call():
    view = scoped()
    def must_not_call(request):
        raise AssertionError("backend cannot receive mismatched scoped source")
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(must_not_call),
    )
    for query, ids in (
        ("forged user query", view.visible_route_ids),
        (view.original_query, ("archive.read",)),
        (view.original_query, tuple(reversed(view.visible_route_ids))),
        (view.original_query, list(view.visible_route_ids)),
    ):
        with pytest.raises(PolicyViolationError, match="query mismatch"):
            selector(query, ids)


@pytest.mark.parametrize("bad_result", (
    {"selections": [{"option_id": "unregistered:model:tool"}]},
    {"selections": [
        {"option_id": "native:0"}, {"option_id": "native:0"},
    ]},
))
def test_malicious_backend_cannot_forge_or_duplicate_route(bad_result):
    view = scoped()
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(lambda _: bad_result),
    )
    with pytest.raises((PlanningError, ValueError)):
        selector(view.original_query, view.visible_route_ids)


def test_policy_mutation_during_inference_denies_result_publication():
    view = scoped()
    def mutate_authoritative_policy(request):
        view.router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
        )
        return {"selections": [{"option_id": request.options[0].id}]}
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(mutate_authoritative_policy),
    )
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        selector(view.original_query, view.visible_route_ids)


def test_hybrid_diagnostic_never_calls_planning_or_tool_execution():
    view = scoped()
    def forbidden(*args, **kwargs):
        raise AssertionError("selector must never execute or plan provider operations")
    view.router.plan = forbidden
    view.router.execute = forbidden
    view.router.aplan_executable_authorized = forbidden
    selector = AuthorizedHybridFixed5Selector(
        view, CallableDecisionBackend(select_deep),
    )
    assert len(selector(view.original_query, view.visible_route_ids)) == 5
