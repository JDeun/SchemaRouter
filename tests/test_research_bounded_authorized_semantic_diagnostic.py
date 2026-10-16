"""Synthetic contract and scope proof, NOT multilingual model accuracy."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    PolicyViolationError,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PlanningError
from scripts.research_bounded_authorized_semantic_diagnostic import (
    propose_bounded_semantic_shortlist,
)

VIEWER = PrincipalContext(subject="host-viewer", roles=("viewer",))
OUTSIDER = PrincipalContext(subject="host-outsider", roles=("outsider",))


def _read_tool(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"Original {name} published tool referencing private reporting",
        endpoints=[
            EndpointSpec(
                name="read", read_only=True,
                description=f"Original {name} private-sector read-only operation",
                output_fields=[
                    FieldSpec(name="public"),
                    FieldSpec(name="private"),
                ],
            ),
        ],
    )


def _router() -> SchemaRouter:
    router = SchemaRouter(
        registry=InMemoryRegistry(),
        authorization_policy=AuthorizationPolicy(
            rules=(
                AuthorizationRule(
                    name="deny-archive", effect="deny", operation="archive.*",
                    roles_any=("viewer",),
                ),
                AuthorizationRule(
                    name="allow-view", effect="allow", operation="*.*",
                    roles_any=("viewer",),
                ),
            ),
            default_effect="deny",
            data_rules=(
                DataScopeRule(
                    operation="*.*", roles_any=("viewer",),
                    hidden_fields=("private",),
                ),
            ),
        ),
    )
    for name in ("marine", "papers", "archive"):
        router.add_tool(_read_tool(name))
    return router


@pytest.mark.parametrize("query", (
    "Read ocean conditions", "해류와 파고 자료를 찾아줘",
    "海流と波高の資料を調べて",
))
def test_exact_k_diagnostic_preserves_multilingual_input_and_visible_pool(
    query: str,
) -> None:
    router = _router()
    captured = []

    def rank_visible(request):
        captured.append(request)
        assert request.query == query
        assert request.max_selections == 1
        assert {o.label for o in request.options} == {
            "marine.read", "papers.read",
        }
        assert all("private" not in o.description for o in request.options)
        assert all("Visible fields: public" in o.description for o in request.options)
        selected = next(
            o.id for o in request.options if o.label == "marine.read"
        )
        return {"selections": [{"option_id": selected}]}

    def no_action(*args, **kwargs):
        raise AssertionError("diagnostic cannot plan/execute")

    router.plan = no_action
    router.execute = no_action
    result = propose_bounded_semantic_shortlist(
        router, query,
        principal=VIEWER,
        backend=CallableDecisionBackend(rank_visible),
        k=1,
    )
    assert result.status == "unverified_full_k_model_ranking"
    assert result.route_ids == ("marine.read",)
    assert result.registered_candidate_count == 2
    assert len(result.source_tool_fingerprints[0]) >= 20
    assert len(result.source_endpoint_fingerprints[0]) >= 20
    assert result.model_input_bytes > 0
    assert not result.executable_authority
    assert not result.independent_quality_evidence
    assert not result.calibrated_no_fit
    assert len(captured) == 1


def test_explicit_abstain_does_not_claim_no_fit() -> None:
    result = propose_bounded_semantic_shortlist(
        _router(), "Unsupported sensitive operation",
        principal=VIEWER,
        backend=CallableDecisionBackend(
            lambda _: {"abstained": True},
        ),
        k=2,
    )
    assert result.status == "backend_abstained_not_calibrated_no_fit"
    assert not result.route_ids
    assert result.calibrated_no_fit is False


def test_outsider_cannot_recover_hidden_route_ids_or_model_calls() -> None:
    def never_called(request):
        raise AssertionError("no authorized options to expose")

    result = propose_bounded_semantic_shortlist(
        _router(), "Fetch private archive", principal=OUTSIDER,
        backend=CallableDecisionBackend(never_called),
    )
    assert result.status == "empty_visible_catalog_not_no_fit"
    assert not result.route_ids
    assert result.registered_candidate_count == 0


@pytest.mark.parametrize("forged", (
    {"selections": [{"option_id": "native:999"}]},
    {"selections": [
        {"option_id": "native:0"}, {"option_id": "native:0"},
    ]},
    {"selections": [
        {"option_id": "native:0"}, {"option_id": "native:1"},
    ]},
    {"abstained": True, "selections": [{"option_id": "native:0"}]},
))
def test_untrusted_model_cannot_forge_excess_or_malformed_authority(forged) -> None:
    with pytest.raises((PlanningError, ValueError)):
        propose_bounded_semantic_shortlist(
            _router(), "Some original query",
            principal=VIEWER,
            backend=CallableDecisionBackend(lambda _: forged),
            k=1,
        )


def test_partial_result_is_not_mislabeled_as_full_k_or_no_fit() -> None:
    result = propose_bounded_semantic_shortlist(
        _router(), "Some original query",
        principal=VIEWER,
        backend=CallableDecisionBackend(
            lambda _: {"selections": [{"option_id": "native:0"}]},
        ),
        k=2,
    )
    assert result.status == "unverified_partial_k_model_ranking"
    assert len(result.route_ids) == 1
    assert not result.calibrated_no_fit


@pytest.mark.parametrize("limit", ("catalog", "model_input"))
def test_resource_caps_reject_before_model_inference(limit: str) -> None:
    def must_not_rank(request):
        raise AssertionError("budget must fail before backend")

    kwargs = (
        {"max_catalog_routes": 2}
        if limit == "catalog"
        else {"max_model_input_bytes": 2}
    )
    with pytest.raises(ValueError, match="bounded research limit"):
        propose_bounded_semantic_shortlist(
            _router(), "Get data", principal=VIEWER,
            backend=CallableDecisionBackend(must_not_rank),
            **kwargs,
        )


@pytest.mark.parametrize("bad_k", (0, -1, 17, True, 3.5))
def test_strict_k_rejects_invalid_bounds(bad_k) -> None:
    with pytest.raises(ValueError, match="invalid fixed shortlist"):
        propose_bounded_semantic_shortlist(
            _router(), "a", principal=VIEWER,
            backend=CallableDecisionBackend(lambda _: {}),
            k=bad_k,
        )


@pytest.mark.parametrize("mutation", ("policy", "registry", "availability"))
def test_model_inference_source_mutation_cannot_publish_stale_routes(
    mutation: str,
) -> None:
    router = _router()

    def mutate(request):
        if mutation == "policy":
            router.authorization_policy = AuthorizationPolicy(
                default_effect="deny"
            )
        elif mutation == "registry":
            router.add_tool(_read_tool("fresh"))
        else:
            router.planner.availability_predicate = (
                lambda tool, endpoint: False
            )
        return {"selections": [{"option_id": request.options[0].id}]}

    with pytest.raises(
        PolicyViolationError, match="retrieval authority changed during request",
    ):
        propose_bounded_semantic_shortlist(
            router, "Read data", principal=VIEWER,
            backend=CallableDecisionBackend(mutate),
            k=1,
        )


def test_native_ids_are_unchanged_not_semantic_alias_inventions() -> None:
    router = _router()
    result = propose_bounded_semantic_shortlist(
        router, "해류 데이터를 알려줘",
        principal=VIEWER,
        backend=CallableDecisionBackend(
            lambda request: {
                "selections": [
                    {"option_id": next(
                        o.id for o in request.options
                        if o.label == "papers.read"
                    )}
                ],
            },
        ),
        k=1,
    )
    assert result.route_ids == ("papers.read",)
    assert result.source_endpoint_fingerprints == (
        router.registry.get("papers").endpoint("read").fingerprint,
    )
