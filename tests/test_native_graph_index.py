"""Native G5: actual adapter contracts, scoped graph evidence, no executor."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.concept_retrieval import NativeConceptCatalog, NativeDeclaredConcept
from schemarouter.decisions import CallableDecisionBackend
from schemarouter.errors import PlanningError, PolicyViolationError
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from schemarouter.semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)
from scripts.research_g5_decision_backend_ranker_e0 import (
    ResearchAuthorizedG5DecisionRanker,
)

ANALYST = PrincipalContext(subject="analyst", roles=("reader",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))
ALIASES = ("case status", "문의 상태", "問い合わせ状態")
STATUS = CapabilityFieldContract(
    semantic_id="crm.status", json_schema={"type": "string"},
)
GROUP = NativeDeclaredFieldGroup(
    aliases=ALIASES, required_fields=(STATUS,),
    source_type="crm", license="owner-reviewed",
)
CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.case_status", aliases=ALIASES, required_fields=(STATUS,),
    source_type="crm", license="owner-reviewed",
),))


def _attest(tool, endpoint, *members):
    return HostSemanticAttestation(
        expected_tool_key=tool.key,
        expected_tool_fingerprint=tool.fingerprint,
        source_type=tool.source_type, license=tool.license,
        reviewed_by="local-owner",
        mappings=tuple(HostSemanticMapping(
            endpoint_name=endpoint,
            expected_endpoint_fingerprint=tool.endpoint(endpoint).fingerprint,
            member_kind=kind, member_name=name, semantic_id=semantic,
        ) for kind, name, semantic in members),
    )


def _tools(*, n_targets=1, incompatible=False):
    root = tool_from_openapi("contacts", {
        "openapi": "3.1.0", "info": {"title": "Contacts", "version": "1"},
        "paths": {"/contacts": {"get": {
            "operationId": "read_contact",
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {
                    "type": "object",
                    "properties": {"contact_id": {"type": "string"}},
                }},
            }}},
        }}},
    })
    root.source_type = "crm"
    root.license = "owner-reviewed"
    root.endpoint("read_contact").read_only = True
    root = apply_host_semantic_attestation(
        root, attestation=_attest(
            root, "read_contact",
            ("output_field", "contact_id", "crm.contact_id"),
        ),
    )
    assert root.endpoint("read_contact").output_fields[0].identifier

    consumers = []
    for i in range(n_targets):
        tool = tool_from_mcp(f"cases_{i}", {"tools": [{
            "name": "read_case", "annotations": {"readOnlyHint": True},
            "inputSchema": {"type": "object", "properties": {
                "contact_id": {"type": "integer" if incompatible else "string"},
            }, "required": ["contact_id"]},
            "outputSchema": {"type": "object", "properties": {
                "status": {"type": "string"},
            }},
        }]})
        assert tool.endpoint("read_case").read_only is None
        # Separate explicit host permission review, not derived from MCP
        # readOnlyHint and NEVER performed by semantic attestation.
        tool.endpoint("read_case").read_only = True
        tool.source_type = "crm"
        tool.license = "owner-reviewed"
        consumers.append(apply_host_semantic_attestation(
            tool, attestation=_attest(
                tool, "read_case",
                ("input_parameter", "contact_id", "crm.contact_id"),
                ("output_field", "status", "crm.status"),
            ),
        ))
    return [root, *consumers]


def _router(*, n_targets=1, hidden=False, denied=False, incompatible=False, noise=0):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(() if denied else (AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader", "viewer"),
        ),)),
        data_rules=(DataScopeRule(
            operation="contacts.read_contact", roles_any=("viewer",),
            hidden_fields=("contact_id",),
        ),) if hidden else (),
    ))
    for tool in _tools(n_targets=n_targets, incompatible=incompatible):
        router.add_tool(tool)
    # Huge unrelated registered native tool catalog; no provider is called.
    for i in range(noise):
        router.add_tool(ToolSpec(
            name=f"unrelated_{i}",
            source_type="science", license="owner-reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="label", semantic_id="science.label",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    return router


def _index(router):
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


@pytest.mark.parametrize("query", ALIASES)
def test_actual_adapter_graph_discovers_target_with_source_witness_and_no_gold(query):
    router = _router(noise=24)
    graph = _index(router)
    assert graph.graph.predecessors("cases_0.read_case") == ("contacts.read_contact",)
    result = graph.lookup(router, query, group=GROUP, principal=ANALYST)
    assert result.status == "complete"
    assert result.index_snapshot_id == graph.field_index.snapshot_id
    assert result.qualified_path_count == 1
    assert result.requested_k == 5
    assert result.independent_quality_evidence is False
    assert result.executable_authority is False
    assert result.calibrated_no_fit is False
    edge = result.candidates[0]
    assert edge.producer_route_id == "contacts.read_contact"
    assert edge.consumer_route_id == "cases_0.read_case"
    assert edge.producer_identifier_field == "contact_id"
    assert edge.consumer_required_parameter == "contact_id"
    assert edge.parameter_bindings == (("contact_id", "contact_id"),)
    assert edge.consumer_output_fields == ("status",)
    assert len(edge.consumer_tool_fingerprint) == 64


def test_semantic_aliases_resolve_without_target_name():
    router = _router()
    idx = _index(router)
    for query in ALIASES:
        result = idx.lookup_concepts(
            router, query, catalog=CATALOG, principal=ANALYST,
        )
        assert [c.consumer_route_id for c in result.candidates] == [
            "cases_0.read_case",
        ]
    with pytest.raises(ValueError, match="no declared concept"):
        idx.lookup_concepts(router, "weather", catalog=CATALOG, principal=ANALYST)


def test_hidden_root_identifier_or_denied_policy_yields_no_graph_evidence():
    for kwargs in ({"hidden": True}, {"denied": True}):
        router = _router(**kwargs)
        idx = _index(router)
        result = idx.lookup(router, ALIASES[0], group=GROUP, principal=VIEWER)
        assert result.status == "no_proven_hit"
        assert result.candidates == ()


def test_unavailable_endpoint_revocation_is_live():
    router = _router()
    idx = _index(router)
    router.planner.availability_predicate = (
        lambda tool, ep: tool.key != "contacts"
    )
    assert idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
    ).candidates == ()


def test_mismatched_native_scalar_types_fail_canonical_graph():
    router = _router(incompatible=True)
    idx = _index(router)
    assert idx.graph.predecessors("cases_0.read_case") == ()
    assert idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST).candidates == ()


def test_unranked_overflow_keeps_none_of_the_six_source_verified_paths():
    router = _router(n_targets=6)
    idx = _index(router)
    result = idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert result.status == "over_k_unranked"
    assert result.qualified_path_count == 6
    assert result.candidates == ()


def test_untrusted_metadata_only_native_tool_cannot_create_graph_edges():
    router = _router()
    router.add_tool(ToolSpec(
        name="fake", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="contact id case status",
        )],
    ))
    idx = _index(router)
    assert "fake.read" not in idx.graph.predecessors("cases_0.read_case")
    assert idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
    ).qualified_path_count == 1


def test_registry_revision_and_wrong_registry_fail_closed():
    router = _router()
    idx = _index(router)
    router.add_tool(ToolSpec(name="later", endpoints=[EndpointSpec(name="read")]))
    with pytest.raises(PolicyViolationError, match="stale"):
        idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    with pytest.raises(PolicyViolationError, match="stale"):
        idx.lookup(_router(), ALIASES[0], group=GROUP, principal=ANALYST)


def test_global_registered_catalog_five_thousand_routes_without_query_global_scan(
    monkeypatch,
):
    router = _router(noise=5100)
    idx = _index(router)
    assert idx.field_index.indexed_route_count == 5102
    assert idx.native_root_count == 1
    assert idx.native_consumer_count == 1
    seen = []
    original = router.registry.get

    def recorded(key):
        seen.append(key)
        if len(seen) > 3:
            pytest.fail("per-query scanned registered native catalog")
        return original(key)

    monkeypatch.setattr(router.registry, "get", recorded)
    found = idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert found.qualified_path_count == 1
    assert set(seen) == {"contacts", "cases_0"}


def test_no_agent_executor_or_arbitrary_k_in_native_graph_lookup(monkeypatch):
    router = _router()
    idx = _index(router)
    monkeypatch.setattr(router, "plan", lambda *_a, **_k: pytest.fail("planned"))
    monkeypatch.setattr(router, "execute", lambda *_a, **_k: pytest.fail("executed"))
    assert idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST).candidates
    for value in (0, 6, True, 5.0):
        with pytest.raises(ValueError, match="fixed K5"):
            idx.lookup(router, ALIASES[0], group=GROUP,
                       principal=ANALYST, k=value)


def test_in_place_policy_rules_change_during_lookup_fails_closed():
    router = _router()
    idx = _index(router)
    original_policy = router.authorization_policy
    assert original_policy is not None
    changed = False

    def availability(tool, ep):
        nonlocal changed
        if not changed:
            changed = True
            # Simulate an adversarial owner-controlled hot policy rewrite
            # rather than normal immutable-dataclass replacement.
            object.__setattr__(original_policy, "default_effect", "allow")
        return True

    router.planner.availability_predicate = availability
    with pytest.raises(PolicyViolationError, match="rules changed"):
        idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)


def test_replacing_availability_predicate_mid_graph_lookup_fails_closed():
    router = _router()
    index = _index(router)
    consulted = False

    def replace_during_check(tool, endpoint):
        nonlocal consulted
        if not consulted:
            consulted = True
            router.planner.availability_predicate = lambda _tool, _ep: False
        return True

    router.planner.availability_predicate = replace_during_check
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        index.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert consulted


def test_research_ranker_receives_only_current_authorized_scoped_paths_after_k():
    router = _router(n_targets=7)
    idx = _index(router)
    baseline = idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST)
    assert baseline.status == "over_k_unranked"
    assert baseline.qualified_path_count == 7
    assert baseline.candidates == ()
    seen = []

    def ranker(query, offered, k):
        seen.append((query, offered, k))
        assert query == ALIASES[0] and k == 5
        assert len(offered) == 7
        assert all(
            c.producer_route_id == "contacts.read_contact"
            and c.producer_identifier_field == "contact_id"
            and c.consumer_output_fields == ("status",)
            and len(c.consumer_tool_fingerprint) == 64
            for c in offered
        )
        return (6, 4, 2, 0, 5)

    outcome = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=ranker,
    )
    assert len(seen) == 1
    assert outcome.status == "ranked_unverified"
    assert outcome.experimental_ranked is True
    assert not outcome.independent_quality_evidence
    assert not outcome.calibrated_no_fit
    assert not outcome.executable_authority
    assert outcome.qualified_path_count == 7
    assert tuple(c.consumer_route_id for c in outcome.candidates) == (
        "cases_6.read_case", "cases_4.read_case", "cases_2.read_case",
        "cases_0.read_case", "cases_5.read_case",
    )
    # No callback means byte/behavior-compatible, strict unranked overflow.
    assert idx.lookup(router, ALIASES[0], group=GROUP, principal=ANALYST) == baseline


def test_research_ranker_mutated_offered_candidate_cannot_forge_returned_source():
    router = _router(n_targets=7)
    idx = _index(router)
    original = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
    )
    assert original.status == "over_k_unranked"

    def adversarial(_query, offered, k):
        assert k == 5
        assert len(offered) == 7
        # Python dataclass(frozen=True) is NOT an isolation boundary.
        # A model-owned callback can bypass frozen checks using object.__setattr__.
        # It must never mutate the source-pinned object later returned to user.
        object.__setattr__(
            offered[6], "consumer_route_id", "admin.erase_all_records"
        )
        object.__setattr__(
            offered[6], "consumer_output_fields", ("secret_raw_payload",)
        )
        object.__setattr__(
            offered[6], "consumer_tool_fingerprint", "0" * 64
        )
        object.__setattr__(
            offered[6], "parameter_bindings", (("admin", "secret_key"),)
        )
        return (6, 4, 2, 0, 5)

    ranked = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=adversarial,
    )
    assert ranked.status == "ranked_unverified"
    assert ranked.qualified_path_count == 7
    assert tuple(item.consumer_route_id for item in ranked.candidates) == (
        "cases_6.read_case", "cases_4.read_case", "cases_2.read_case",
        "cases_0.read_case", "cases_5.read_case",
    )
    for item in ranked.candidates:
        assert item.consumer_output_fields == ("status",)
        assert item.consumer_tool_fingerprint != "0" * 64
        assert item.parameter_bindings == (("contact_id", "contact_id"),)
        assert "secret" not in repr(item)
    assert idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST
    ) == original


def test_research_ranker_never_sees_denied_hidden_or_unavailable_paths():
    for kwargs, actor in (
        ({"n_targets": 7, "hidden": True}, VIEWER),
        ({"n_targets": 7, "denied": True}, ANALYST),
    ):
        router = _router(**kwargs)
        idx = _index(router)

        def forbidden(*_args):
            pytest.fail("ranker was called with no authorized complete paths")

        outcome = idx.lookup(
            router, ALIASES[0], group=GROUP, principal=actor,
            _research_ranker=forbidden,
        )
        assert outcome.status == "no_proven_hit"
        assert outcome.candidates == ()
    router = _router(n_targets=7)
    idx = _index(router)
    router.planner.availability_predicate = (
        lambda tool, _endpoint: tool.key not in {"cases_4", "cases_5", "cases_6"}
    )
    outcome = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=lambda *_: pytest.fail("ranker invoked below K"),
    )
    assert outcome.status == "complete"
    assert outcome.qualified_path_count == 4
    assert all(c.consumer_route_id not in {
        "cases_4.read_case", "cases_5.read_case", "cases_6.read_case",
    } for c in outcome.candidates)


@pytest.mark.parametrize("forged", [
    (0, 1, 2), (0, 0, 1, 2, 3), (-1, 1, 2, 3, 4),
    (7, 1, 2, 3, 4), (True, 1, 2, 3, 4),
    [0, 1, 2, 3, 4], "01234", (0, 1, 2, 3, "4"),
])
def test_research_ranker_refuses_partial_forged_or_duplicate_offsets(forged):
    router = _router(n_targets=7)
    idx = _index(router)
    with pytest.raises(PolicyViolationError, match="forged, partial or duplicate"):
        idx.lookup(
            router, ALIASES[0], group=GROUP, principal=ANALYST,
            _research_ranker=lambda *_: forged,
        )


def test_research_ranker_abstention_never_claims_calibrated_no_fit():
    router = _router(n_targets=7)
    idx = _index(router)
    result = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=lambda *_: (),
    )
    assert result.status == "ranker_abstained_unverified"
    assert result.qualified_path_count == 7
    assert result.candidates == ()
    assert result.experimental_ranked
    assert not result.calibrated_no_fit
    assert not result.independent_quality_evidence


def test_research_ranker_bounded_to_32_authorized_paths_before_callback():
    router = _router(n_targets=33)
    idx = _index(router)
    outcome = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=lambda *_: pytest.fail("ranker saw unbounded 33 paths"),
    )
    assert outcome.qualified_path_count == 33
    assert outcome.status == "over_k_unranked"
    assert outcome.candidates == ()
    assert not outcome.experimental_ranked


def test_research_ranker_policy_or_source_mutation_fails_closed():
    for change in ("policy", "registry", "availability"):
        router = _router(n_targets=7)
        idx = _index(router)

        def malicious(_query, _offered, _k, *, change=change, router=router):
            if change == "policy":
                router.authorization_policy = AuthorizationPolicy(
                    default_effect="deny",
                )
            elif change == "registry":
                router.add_tool(ToolSpec(
                    name="after_ranker",
                    endpoints=[EndpointSpec(name="read")],
                ))
            else:
                router.planner.availability_predicate = lambda *_: False
            return (0, 1, 2, 3, 4)

        with pytest.raises(PolicyViolationError):
            idx.lookup(
                router, ALIASES[0], group=GROUP, principal=ANALYST,
                _research_ranker=malicious,
            )


def test_research_ranker_is_not_an_agent_and_cannot_plan_or_execute(monkeypatch):
    router = _router(n_targets=7)
    idx = _index(router)
    monkeypatch.setattr(router, "execute", lambda *_a, **_k: pytest.fail("executed"))
    monkeypatch.setattr(router, "plan", lambda *_a, **_k: pytest.fail("planned"))
    result = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=lambda _query, candidates, _k: tuple(
            range(5)
        ) if len(candidates) == 7 else (),
    )
    assert result.status == "ranked_unverified"


def test_research_g5_ranker_can_use_existing_strict_decision_backend():
    router = _router(n_targets=7)
    idx = _index(router)
    captured = []

    def model(request):
        captured.append(request)
        assert request.max_selections == 5
        assert request.context["independent_quality_evidence"] is False
        assert request.context["executable_authority"] is False
        assert len(request.options) == 7
        assert all(option.metadata == {} for option in request.options)
        assert all(option.description.startswith("source=contacts.read_contact; ")
                   for option in request.options)
        return {"selections": [
            {"option_id": request.options[position].id}
            for position in (6, 4, 2, 0, 1)
        ]}

    ranker = ResearchAuthorizedG5DecisionRanker(CallableDecisionBackend(model))
    outcome = idx.lookup(
        router, ALIASES[1], group=GROUP, principal=ANALYST,
        _research_ranker=ranker,
    )
    assert len(captured) == 1
    assert outcome.status == "ranked_unverified"
    assert tuple(c.consumer_route_id for c in outcome.candidates) == (
        "cases_6.read_case", "cases_4.read_case", "cases_2.read_case",
        "cases_0.read_case", "cases_1.read_case",
    )
    assert not outcome.calibrated_no_fit
    assert not outcome.executable_authority
    assert not outcome.independent_quality_evidence


def test_optional_common_field_description_ablation_never_edits_native_paths():
    from dataclasses import replace

    router = _router(n_targets=7)
    idx = _index(router)
    captured = []

    def model(request):
        captured.append(request)
        return {"selections": [
            {"option_id": option.id} for option in request.options[:5]
        ]}

    raw = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=ResearchAuthorizedG5DecisionRanker(
            CallableDecisionBackend(model),
        ),
    )
    common = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=ResearchAuthorizedG5DecisionRanker(
            CallableDecisionBackend(model),
            omit_identical_descriptions=True,
        ),
    )
    assert len(captured) == 2
    assert all(o.description.startswith("source=contacts.read_contact; ")
               for o in captured[0].options)
    assert all(o.description == "" for o in captured[1].options)
    assert [o.label for o in captured[0].options] == [
        o.label for o in captured[1].options
    ]
    assert raw.candidates == common.candidates
    assert not raw.executable_authority and not common.executable_authority
    assert not common.independent_quality_evidence
    assert not common.calibrated_no_fit
    originals = []
    idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=lambda _q, paths, _k: (
            originals.extend(paths) or (0, 1, 2, 3, 4)
        ),
    )
    # Heterogeneous ORIGINAL source descriptions MUST be retained
    # for ALL candidates. No partial lexical masking / hidden inference.
    mixed = (
        replace(originals[0], consumer_output_fields=("other",)),
        *originals[1:],
    )
    mixed_queries = []

    def mixed_model(request):
        mixed_queries.append(request)
        return {"selections": [
            {"option_id": option.id} for option in request.options[:5]
        ]}

    ResearchAuthorizedG5DecisionRanker(
        CallableDecisionBackend(mixed_model),
        omit_identical_descriptions=True,
    )(ALIASES[0], mixed, 5)
    assert len(mixed_queries) == 1
    assert all(opt.description for opt in mixed_queries[0].options)
    assert all(opt.label for opt in mixed_queries[0].options)
    for value in (1, "true", None):
        with pytest.raises(ValueError, match="byte limit"):
            ResearchAuthorizedG5DecisionRanker(
                CallableDecisionBackend(model),
                omit_identical_descriptions=value,
            )


def test_research_g5_backend_rejects_partial_forged_and_abstention_is_not_no_fit():
    router = _router(n_targets=7)
    idx = _index(router)
    for model, error in (
        (lambda req: {"selections": [
            {"option_id": opt.id} for opt in req.options[:3]
        ]}, PolicyViolationError),
        (lambda _req: {"selections": [
            {"option_id": "source_unregistered_route"} for _ in range(5)
        ]}, PlanningError),
    ):
        ranker = ResearchAuthorizedG5DecisionRanker(
            CallableDecisionBackend(model),
        )
        with pytest.raises(error):
            idx.lookup(
                router, ALIASES[0], group=GROUP, principal=ANALYST,
                _research_ranker=ranker,
            )
    abstain = ResearchAuthorizedG5DecisionRanker(
        CallableDecisionBackend(
            lambda _req: {"abstained": True, "selections": []},
        ),
    )
    result = idx.lookup(
        router, ALIASES[0], group=GROUP, principal=ANALYST,
        _research_ranker=abstain,
    )
    assert result.status == "ranker_abstained_unverified"
    assert result.candidates == ()
    assert not result.calibrated_no_fit


def test_research_g5_backend_model_input_budget_fails_before_backend():
    router = _router(n_targets=7)
    idx = _index(router)
    def no_call(_request):
        pytest.fail("model saw oversized or unauthorized G5 evidence")
    ranker = ResearchAuthorizedG5DecisionRanker(
        CallableDecisionBackend(no_call), max_model_input_bytes=64,
    )
    with pytest.raises(PolicyViolationError, match="input byte cap"):
        idx.lookup(
            router, ALIASES[0], group=GROUP, principal=ANALYST,
            _research_ranker=ranker,
        )
    for invalid in (0, 16385, True, 12.5):
        with pytest.raises(ValueError, match="byte limit"):
            ResearchAuthorizedG5DecisionRanker(
                CallableDecisionBackend(no_call),
                max_model_input_bytes=invalid,
            )
