"""#1560: a bounded model decision backend cannot forge indexed native routes."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.decisions import (
    CallableDecisionBackend,
    DecisionResult,
    DecisionSelection,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import (
    IndexedNativeFieldCandidate,
    NativeSchemaPostingIndex,
)
from scripts.research_indexed_decision_backend_ranker_e0 import (
    MAX_MODEL_INPUT_BYTES,
    ResearchIndexedFieldDecisionRanker,
)

PRINCIPAL = PrincipalContext(subject="index-experiment", roles=("analyst",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("case status", "문의 상태", "案件の状態"),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="crm.case_status",
            json_schema={"type": "string"},
        ),
    ),
    source_type="crm",
    license="reviewed",
)


def _source():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            operation="queue_*.read",
            effect="allow",
            roles_any=("analyst",),
        ),),
    ))
    for i in range(7):
        router.add_tool(ToolSpec(
            name=f"queue_{i}",
            source_type="crm",
            license="reviewed",
            endpoints=[EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(
                    name="status",
                    semantic_id="crm.case_status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    return router, NativeSchemaPostingIndex.build(router.registry)


def _backend(select=(6, 5, 4, 3, 2), *, calls=None):
    def choose(request):
        if calls is not None:
            calls.append(request)
        return DecisionResult(selections=[
            DecisionSelection(option_id=request.options[i].id)
            for i in select
        ])
    return CallableDecisionBackend(choose)


@pytest.mark.parametrize("query", GROUP.aliases)
def test_model_backend_reuses_authorized_index_and_preserves_order(query):
    router, index = _source()
    calls = []
    ranker = ResearchIndexedFieldDecisionRanker(
        _backend(calls=calls), omit_identical_descriptions=True,
    )
    initial = index.lookup(router, query, group=GROUP, principal=PRINCIPAL)
    result = index.lookup(
        router, query, group=GROUP, principal=PRINCIPAL,
        _research_ranker=ranker,
    )
    assert initial.status == "over_k_unranked"
    assert result.status == "ranked_unverified"
    assert result.experimental_ranked is True
    assert result.qualified_count == 7
    assert [candidate.route_id for candidate in result.candidates] == [
        "queue_6.read", "queue_5.read", "queue_4.read",
        "queue_3.read", "queue_2.read",
    ]
    assert len(calls) == 1
    request = calls[0]
    assert request.query == query
    assert request.max_selections == 5
    assert [o.label for o in request.options] == [
        f"queue_{i}.read" for i in range(7)
    ]
    assert all(o.description == "" and o.metadata == {} for o in request.options)
    assert request.context["executable_authority"] is False
    assert request.context["independent_quality_evidence"] is False
    assert request.context["calibrated_no_fit"] is False
    assert "fingerprint" not in request.model_dump_json()


def test_scoped_field_names_are_only_descriptions_sent_to_backend():
    router, index = _source()
    requests = []
    ranker = ResearchIndexedFieldDecisionRanker(
        _backend(calls=requests),
    )
    result = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
        _research_ranker=ranker,
    )
    assert result.status == "ranked_unverified"
    assert {o.description for o in requests[0].options} == {"status"}
    assert all(not o.metadata for o in requests[0].options)


def test_model_abstention_is_not_claimed_as_no_fit():
    router, index = _source()
    backend = CallableDecisionBackend(lambda _request: DecisionResult(abstained=True))
    selected = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
        _research_ranker=ResearchIndexedFieldDecisionRanker(backend),
    )
    assert selected.status == "ranker_abstained_unverified"
    assert selected.candidates == () and selected.qualified_count == 7


@pytest.mark.parametrize("selected", [
    (0, 1), (0, 0, 1, 2, 3), (0, 1, 2, 3, 7),
])
def test_model_backend_rejects_partial_duplicate_and_forged_choices(selected):
    router, index = _source()

    def invalid(request):
        return DecisionResult(selections=[
            DecisionSelection(
                option_id=(
                    request.options[i].id if i < len(request.options)
                    else "route_99"
                ),
            )
            for i in selected
        ])

    ranker = ResearchIndexedFieldDecisionRanker(CallableDecisionBackend(invalid))
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )


def test_model_backend_rejects_partial_even_as_valid_decision_result():
    router, index = _source()
    ranker = ResearchIndexedFieldDecisionRanker(_backend(select=(0, 1)))
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )


def test_model_backend_input_is_bounded_before_calling_external_backend():
    attempts = []
    item = IndexedNativeFieldCandidate(
        route_id="owner.read",
        tool_fingerprint="owner-tool-fingerprint",
        endpoint_fingerprint="owner-endpoint-fingerprint",
        required_output_fields=("status",),
    )
    ranker = ResearchIndexedFieldDecisionRanker(
        _backend(calls=attempts),
        max_model_input_bytes=64,
    )
    offered = tuple(
        IndexedNativeFieldCandidate(
            route_id=f"owner_{i}.read",
            tool_fingerprint=item.tool_fingerprint,
            endpoint_fingerprint=item.endpoint_fingerprint,
            required_output_fields=item.required_output_fields,
        )
        for i in range(6)
    )
    with pytest.raises(PolicyViolationError, match="byte cap"):
        ranker("case status", offered, 5)
    assert attempts == []


def test_model_backend_prevents_forged_direct_callback_shapes():
    ranker = ResearchIndexedFieldDecisionRanker(_backend())
    candidate = IndexedNativeFieldCandidate(
        route_id="owner.read",
        tool_fingerprint="tool",
        endpoint_fingerprint="endpoint",
        required_output_fields=("status",),
    )
    with pytest.raises(PolicyViolationError, match="bounded scoped"):
        ranker("case status", (candidate,) * 6, 5)
    with pytest.raises(PolicyViolationError, match="bounded scoped"):
        ranker("case status", (candidate,), 5)
    with pytest.raises(ValueError, match="configuration"):
        ResearchIndexedFieldDecisionRanker(
            _backend(), max_model_input_bytes=MAX_MODEL_INPUT_BYTES + 1,
        )


def test_model_backend_cannot_mutate_host_decision_option_set():
    router, index = _source()

    def mutating(request):
        # Invalid provider response must be checked against the ORIGINAL
        # offered option set, not the provider-modified request.
        request.options[0].id = "forged"
        return DecisionResult(selections=[
            DecisionSelection(option_id="forged"),
            *(DecisionSelection(option_id=request.options[i].id) for i in (1, 2, 3, 4)),
        ])
    ranker = ResearchIndexedFieldDecisionRanker(
        CallableDecisionBackend(mutating),
    )
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed"):
        index.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )

def test_model_backend_error_omits_provider_secret_and_cause():
    """An untrusted model exception must not expose credentials to callers."""
    router, index = _source()
    secret = "DO_NOT_LEAK_PRIVATE_PROVIDER_CREDENTIAL"

    def failed_provider(_request):
        raise RuntimeError(secret)

    ranker = ResearchIndexedFieldDecisionRanker(
        CallableDecisionBackend(failed_provider),
    )
    with pytest.raises(PolicyViolationError, match="indexed research ranking failed") as exc:
        index.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )
    assert secret not in str(exc.value)
    assert exc.value.__cause__ is None


def test_model_backend_health_revocation_of_unselected_route_fails_closed():
    """Revalidate all original qualified sources, not just the selected K5."""
    router, index = _source()
    availability = {"queue_0": True}
    router.planner.availability_predicate = (
        lambda tool, _endpoint: availability.get(tool.key, True)
    )

    def revoke_unselected(request):
        availability["queue_0"] = False
        return DecisionResult(selections=[
            DecisionSelection(option_id=request.options[i].id)
            for i in (2, 3, 4, 5, 6)
        ])

    ranker = ResearchIndexedFieldDecisionRanker(
        CallableDecisionBackend(revoke_unselected),
    )
    with pytest.raises(PolicyViolationError, match="eligibility changed") as exc:
        index.lookup(
            router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
            _research_ranker=ranker,
        )
    assert exc.value.__cause__ is None


def test_model_backend_never_receives_over_limit_scoped_source_menu():
    """A 33-route hit must abstain before invoking any model callback."""
    router, _ = _source()
    for i in range(7, 33):
        router.add_tool(ToolSpec(
            name=f"queue_{i}",
            source_type="crm",
            license="reviewed",
            endpoints=[EndpointSpec(
                name="read",
                read_only=True,
                output_fields=[FieldSpec(
                    name="status",
                    semantic_id="crm.case_status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    index = NativeSchemaPostingIndex.build(router.registry)
    attempts = []
    ranker = ResearchIndexedFieldDecisionRanker(
        _backend(calls=attempts),
    )
    result = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=PRINCIPAL,
        _research_ranker=ranker,
    )
    assert result.status == "over_k_unranked"
    assert result.qualified_count == 33
    assert result.candidates == ()
    assert attempts == []


def test_model_backend_concept_lookup_requires_declared_source_semantics():
    """The model gets only candidates resolved from a host-owned concept."""
    router, index = _source()
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="crm.case_status",
        aliases=GROUP.aliases,
        required_fields=GROUP.required_fields,
        source_type="crm",
        license="reviewed",
    ),))
    calls = []
    result = index.lookup_concepts(
        router, GROUP.aliases[0], principal=PRINCIPAL, catalog=catalog,
        _research_ranker=ResearchIndexedFieldDecisionRanker(
            _backend(calls=calls),
        ),
    )
    assert result.status == "ranked_unverified"
    assert len(result.candidates) == 5
    assert [candidate.route_id for candidate in result.candidates] == [
        f"queue_{i}.read" for i in (6, 5, 4, 3, 2)
    ]
    assert len(calls) == 1
    assert all(option.metadata == {} for option in calls[0].options)
