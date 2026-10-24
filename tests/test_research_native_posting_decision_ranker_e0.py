"""E0: native source-verified direct FieldGroup decisions; no real-model gold."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_native_posting_decision_ranker_e0 import (
    ResearchAuthorizedPostingDecisionRanker,
)

QUERIES = ("case status", "문의 상태", "問い合わせ状態")
PRINCIPAL = PrincipalContext(subject="approved-researcher", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=QUERIES,
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm",
    license="host-reviewed",
)
CANARY = "DO-NOT-LEAK-PRIVATE-TOKEN"


def fixture():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="case_*.read", roles_any=("reader",),
        ),),
        data_rules=(DataScopeRule(
            operation="case_*.read", roles_any=("reader",),
            hidden_fields=("sensitive_value",),
        ),),
    ))
    for n in range(6):
        router.add_tool(ToolSpec(
            name=f"case_{n}",
            source_type="crm",
            license="host-reviewed",
            description=CANARY,
            endpoints=[EndpointSpec(
                name="read",
                read_only=True,
                description=CANARY,
                output_fields=[
                    FieldSpec(
                        name="status",
                        semantic_id="crm.status",
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(name="sensitive_value", description=CANARY),
                ],
            )],
        ))
    return router, NativeSchemaPostingIndex.build(router.registry)


def choose_reversed(request):
    assert request.max_selections == 5
    assert request.context["executable_authority"] is False
    assert request.context["independent_quality_evidence"] is False
    assert CANARY not in request.model_dump_json()
    assert len(request.options) == 6
    assert all(option.description == "" for option in request.options)
    return {"selections": [
        {"option_id": option.id} for option in reversed(request.options[1:])
    ]}


@pytest.mark.parametrize("query", QUERIES)
def test_actual_decision_backend_selects_five_in_requested_order(query):
    router, index = fixture()
    baseline = index.lookup(router, query, group=GROUP, principal=PRINCIPAL)
    assert baseline.status == "over_k_unranked" and baseline.candidates == ()
    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(choose_reversed),
    )
    selected = index.lookup(
        router, query, group=GROUP, principal=PRINCIPAL,
        _research_ranker=ranker,
    )
    assert selected.status == "ranked_unverified"
    assert selected.experimental_ranked is True
    assert [item.route_id for item in selected.candidates] == [
        "case_5.read", "case_4.read", "case_3.read",
        "case_2.read", "case_1.read",
    ]
    assert selected.qualified_count == 6


def test_abstention_is_not_calibrated_no_fit():
    router, index = fixture()
    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(lambda _: {"abstained": True}),
    )
    selected = index.lookup(
        router, QUERIES[0], group=GROUP, principal=PRINCIPAL,
        _research_ranker=ranker,
    )
    assert selected.status == "ranker_abstained_unverified"
    assert selected.candidates == ()
    assert selected.experimental_ranked is True


@pytest.mark.parametrize("bad", (
    {"selections": [{"option_id": "route_999"}]},
    {"selections": [{"option_id": "route_00"}] * 5},
    {"selections": [{"option_id": "route_00"}]},
    {"selections": [{"option_id": f"route_{i:02d}"} for i in range(6)]},
))
def test_forged_duplicate_partial_and_over_k_decisions_fail_closed(bad):
    router, index = fixture()
    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(lambda _request: bad),
    )
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, QUERIES[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )


def test_backend_errors_do_not_expose_original_tool_descriptions():
    router, index = fixture()

    def failing(_):
        raise RuntimeError(CANARY)

    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(failing),
    )
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed") as err:
        index.lookup(
            router, QUERIES[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )
    assert CANARY not in str(err.value) and err.value.__cause__ is None


def test_explicit_small_prompt_budget_denies_backend_before_call():
    router, index = fixture()
    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(lambda _: pytest.fail("must not send oversized prompt")),
        max_model_input_bytes=1,
    )
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, QUERIES[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )


def test_untrusted_backend_cannot_select_after_midflight_policy_revocation():
    router, index = fixture()

    def revoked(request):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return {"selections": [
            {"option_id": item.id} for item in request.options[:5]
        ]}

    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(revoked),
    )
    with pytest.raises(PolicyViolationError):
        index.lookup(
            router, QUERIES[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )


def test_no_provider_execution_or_main_planner_is_required():
    router, index = fixture()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("research ranking must never execute tools")

    router.execute = forbidden
    router.plan = forbidden
    ranker = ResearchAuthorizedPostingDecisionRanker(
        CallableDecisionBackend(choose_reversed),
    )
    assert index.lookup(
        router, QUERIES[0], group=GROUP, principal=PRINCIPAL,
        _research_ranker=ranker,
    ).status == "ranked_unverified"


def test_invalid_ranker_options_are_rejected():
    backend = CallableDecisionBackend(choose_reversed)
    for bad in (0, -1, True, 16_385, 2.0):
        with pytest.raises(ValueError, match="direct posting decision input bounds"):
            ResearchAuthorizedPostingDecisionRanker(
                backend, max_model_input_bytes=bad,
            )
    with pytest.raises(ValueError, match="direct posting decision input bounds"):
        ResearchAuthorizedPostingDecisionRanker(
            backend, omit_identical_field_descriptions=1,
        )
