"""E0 indexed K5 model adapter: current-source constraints and no authority."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.research_indexed_decision_backend_ranker_e0 import (
    ResearchAuthorizedIndexedDecisionRanker,
)

PRINCIPAL = PrincipalContext(subject="authorized-researcher", roles=("reader",))
SEMANTIC = CapabilityFieldContract(
    semantic_id="service.status", json_schema={"type": "string"},
)
QUERY = "show invoice status"
GROUP = NativeDeclaredFieldGroup(
    aliases=(QUERY,),
    required_fields=(SEMANTIC,),
    source_type="crm",
    license="reviewed",
)


def _source(*, count: int = 7):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="forbidden.read", roles_any=("reader",),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("reader",),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="hidden.read", roles_any=("reader",),
                hidden_fields=("status",),
            ),
        ),
    ))
    for name in (
        *(f"service_{i:02d}" for i in range(count)),
        "forbidden",
        "hidden",
    ):
        router.add_tool(ToolSpec(
            name=name,
            source_type="crm",
            license="reviewed",
            endpoints=[EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(
                    name="status",
                    semantic_id="service.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    return router, NativeSchemaPostingIndex.build(router.registry)


def _ranker(handler, **options):
    return ResearchAuthorizedIndexedDecisionRanker(
        CallableDecisionBackend(handler), **options,
    )


def test_model_receives_only_seven_scoped_source_candidates_and_returns_original_five():
    router, index = _source()
    seen = []

    def model(request):
        seen.append(request.model_dump(mode="python"))
        assert request.query == QUERY
        assert request.max_selections == 5
        assert all(option.metadata == {} for option in request.options)
        assert [option.label for option in request.options] == [
            f"service_{i:02d}.read" for i in range(7)
        ]
        assert all(
            option.description == "required output=status"
            for option in request.options
        )
        assert request.context["executable_authority"] is False
        assert request.context["independent_quality_evidence"] is False
        return {"selections": [
            {"option_id": f"route_{i:02d}"} for i in (6, 5, 4, 3, 2)
        ]}

    baseline = index.lookup(router, QUERY, group=GROUP, principal=PRINCIPAL)
    assert baseline.status == "over_k_unranked"
    assert baseline.candidates == ()
    outcome = index.lookup(
        router, QUERY, group=GROUP, principal=PRINCIPAL,
        _research_ranker=_ranker(model),
    )
    assert outcome.status == "ranked_unverified"
    assert outcome.experimental_ranked is True
    assert outcome.qualified_count == 7
    assert [item.route_id for item in outcome.candidates] == [
        f"service_{i:02d}.read" for i in (6, 5, 4, 3, 2)
    ]
    assert len(seen) == 1
    assert "forbidden.read" not in str(seen)
    assert "hidden.read" not in str(seen)


@pytest.mark.parametrize("malformed", [
    {"selections": [{"option_id": "route_00"}]},
    {"selections": [{"option_id": "route_99"}]},
    {"selections": [{"option_id": "route_00"}] * 5},
    {"selections": [{"option_id": f"route_{i:02d}"} for i in range(6)]},
])
def test_model_forgery_partial_or_duplicate_cannot_select(malformed):
    router, index = _source()
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
            _research_ranker=_ranker(lambda _request: malformed),
        )


def test_model_abstention_never_claims_calibrated_no_fit():
    router, index = _source()
    outcome = index.lookup(
        router, QUERY, group=GROUP, principal=PRINCIPAL,
        _research_ranker=_ranker(lambda _request: {"abstained": True}),
    )
    assert outcome.status == "ranker_abstained_unverified"
    assert outcome.candidates == ()
    assert outcome.experimental_ranked is True


def test_adapter_sanitizes_private_backend_error_and_model_payload_is_bounded():
    router, index = _source()

    def secret_error(_request):
        raise RuntimeError("DO_NOT_LEAK_PROVIDER_API_KEY")

    with pytest.raises(PolicyViolationError, match="indexed research ranking failed") as exc:
        index.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
            _research_ranker=_ranker(secret_error),
        )
    assert "DO_NOT_LEAK_PROVIDER_API_KEY" not in str(exc.value)
    assert exc.value.__cause__ is None
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
            _research_ranker=_ranker(
                lambda *_: pytest.fail("oversized model call"),
                max_model_input_bytes=64,
            ),
        )


def test_model_can_omit_common_field_descriptions_without_changing_id_set():
    router, index = _source()

    def choose(request):
        assert all(option.description == "" for option in request.options)
        return {"selections": [
            {"option_id": f"route_{i:02d}"} for i in (0, 1, 2, 3, 4)
        ]}

    result = index.lookup(
        router, QUERY, group=GROUP, principal=PRINCIPAL,
        _research_ranker=_ranker(
            choose, omit_identical_field_descriptions=True,
        ),
    )
    assert len(result.candidates) == 5


def test_backend_health_revocation_blocks_model_selected_candidates():
    router, index = _source()
    health = {"service_00": True}

    def availability(tool, endpoint):
        assert endpoint.name == "read"
        return health.get(tool.key, True)

    router.planner.availability_predicate = availability

    def change_health(request):
        health["service_00"] = False
        return {"selections": [
            {"option_id": f"route_{i:02d}"} for i in (2, 3, 4, 5, 6)
        ]}

    with pytest.raises(PolicyViolationError, match="eligibility changed"):
        index.lookup(
            router, QUERY, group=GROUP, principal=PRINCIPAL,
            _research_ranker=_ranker(change_health),
        )


def test_model_never_receives_large_unbounded_private_candidate_menu():
    router, index = _source(count=33)
    result = index.lookup(
        router, QUERY, group=GROUP, principal=PRINCIPAL,
        _research_ranker=_ranker(
            lambda _request: pytest.fail("unbounded private menu exposed"),
        ),
    )
    assert result.status == "over_k_unranked"
    assert result.qualified_count == 33
    assert result.candidates == ()


def test_concept_lookup_still_requires_declared_current_semantics():
    router, index = _source()
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="service.status",
        aliases=(QUERY,),
        required_fields=(SEMANTIC,),
        source_type="crm",
        license="reviewed",
    ),))
    result = index.lookup_concepts(
        router, QUERY, principal=PRINCIPAL, catalog=catalog,
        _research_ranker=_ranker(lambda request: {"selections": [
            {"option_id": option.id} for option in request.options[:5]
        ]}),
    )
    assert result.status == "ranked_unverified"
    assert len(result.candidates) == 5
