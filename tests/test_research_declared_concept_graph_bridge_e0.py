"""E0 paper-graph intent→field→endpoint controls; no learned accuracy claims."""
from __future__ import annotations

import json

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
from schemarouter.capability_contracts import SemanticEquivalence
from schemarouter.errors import PlanningError
from scripts.research_declared_concept_graph_bridge_e0 import (
    DeclaredConceptGraphAnalyzer,
)

VIEWER = PrincipalContext(subject="synthetic-viewer", roles=("viewer",))
ALIASES = (
    SemanticEquivalence(
        canonical_id="mechanical.elastic_modulus",
        aliases={"탄성계수", "ヤング率", "Youngs modulus"},
    ),
    SemanticEquivalence(
        canonical_id="mechanical.secret_strength",
        aliases={"기밀물성", "機密強度"},
    ),
)


def _router(*, graph: bool) -> SchemaRouter:
    router = SchemaRouter(
        analyzer=DeclaredConceptGraphAnalyzer(ALIASES) if graph else None,
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(
                AuthorizationRule(
                    effect="deny", operation="restricted.*", roles_any=("viewer",),
                ),
                AuthorizationRule(
                    effect="allow", operation="materials.*", roles_any=("viewer",),
                ),
            ),
            data_rules=(
                DataScopeRule(
                    operation="materials.*", roles_any=("viewer",),
                    hidden_fields=("private_value",),
                ),
            ),
        ),
    )
    public = FieldSpec(
        name="elastic_value",
        semantic_id="mechanical.elastic_modulus",
        unit="GPa",
        json_schema={"type": "number"},
        description="A typed mechanical property",
    )
    private = FieldSpec(
        name="private_value",
        semantic_id="mechanical.secret_strength",
        json_schema={"type": "number"},
    )
    router.add_tool(ToolSpec(
        name="materials", description="Typed scientific data",
        source_type="materials_data", license="CC-BY-4.0",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="Read typed material data",
            output_fields=[public, private],
        )],
    ))
    router.add_tool(ToolSpec(
        name="restricted", description="Restricted private provider",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description="Read private provider",
            output_fields=[public],
        )],
    ))
    return router


@pytest.mark.parametrize("language_query", (
    "탄성계수", "ヤング率", "Youngs modulus",
))
def test_declared_graph_alias_links_intent_to_visible_field_and_route(
    language_query: str,
) -> None:
    baseline = _router(graph=False).retrieve_authorized(
        language_query, principal=VIEWER, k=5,
    )
    # The production no-fit policy may backfill *zero-score* candidates.
    # Such candidates are NOT successful concept↔field matches or calibrated
    # unsupported results. For EN, a lexical substring can also match.
    assert all(candidate.score >= 0 for candidate in baseline.candidates)
    router = _router(graph=True)
    result = router.retrieve_authorized(
        language_query, principal=VIEWER, k=5,
    )
    assert [candidate.route_id for candidate in result.candidates] == [
        "materials.read",
    ]
    c = result.candidates[0]
    assert c.score > 0
    if language_query in ("탄성계수", "ヤング率"):
        assert all(candidate.score == 0 for candidate in baseline.candidates)
    # The agent-facing DATA-SCOPED descriptor must never claim source
    # provenance/license from arbitrary source-owner strings. The host
    # retains the original attestation for authorized execution.
    assert c.source_type is None
    assert c.license is None
    trusted_tool = router.registry.get("materials")
    assert trusted_tool.source_type == "materials_data"
    assert trusted_tool.license == "CC-BY-4.0"
    assert c.tool_fingerprint == trusted_tool.fingerprint
    assert c.endpoint_fingerprint == trusted_tool.endpoint("read").fingerprint
    assert [f.semantic_id for f in c.output_fields] == [
        "mechanical.elastic_modulus",
    ]
    assert c.tool_fingerprint and c.endpoint_fingerprint


def test_hidden_or_denied_semantic_edges_do_not_widen_eligibility() -> None:
    router = _router(graph=True)
    for query in ("기밀물성", "機密強度"):
        result = router.retrieve_authorized(query, principal=VIEWER, k=5)
        # A zero-score unrelated backfill is not semantic authorization.
        assert all(candidate.score == 0 for candidate in result.candidates)
        assert all(not candidate.matched_fields for candidate in result.candidates)
    public = router.retrieve_authorized("탄성계수", principal=VIEWER, k=5)
    # Assert this bridge never matches a hidden field nor denied endpoint.
    # Raw output_schema metadata leakage is tracked/fixed separately in
    # security #1532 / PR #1533, not silently promoted as graph correctness.
    assert [c.route_id for c in public.candidates] == ["materials.read"]
    visible_fields = json.dumps([
        field.model_dump(mode="json")
        for candidate in public.candidates
        for field in candidate.output_fields
    ])
    assert "private_value" not in visible_fields
    assert "mechanical.secret_strength" not in visible_fields


def test_unregistered_or_unrelated_alias_cannot_guess_new_semantics() -> None:
    router = _router(graph=True)
    for query in ("탄성계수 관련 추가 질문", "unavailable"):
        result = router.retrieve_authorized(query, principal=VIEWER)
        assert all(candidate.score == 0 for candidate in result.candidates)
        assert all(not candidate.matched_fields for candidate in result.candidates)


def test_declared_graph_lookup_is_retrieval_only(monkeypatch) -> None:
    router = _router(graph=True)

    def impossible(*_args, **_kwargs):
        raise AssertionError("analyzer must not plan or execute tools")

    monkeypatch.setattr(router, "plan", impossible)
    monkeypatch.setattr(router, "execute", impossible)
    result = router.retrieve_authorized("탄성계수", principal=VIEWER, k=5)
    assert len(result.candidates) == 1


@pytest.mark.parametrize("equivalences", (
    (),
    (SemanticEquivalence(canonical_id="mechanical.elastic_modulus"),),
    (
        SemanticEquivalence(
            canonical_id="one", aliases={"중복", "UNIQUE"},
        ),
        SemanticEquivalence(
            canonical_id="two", aliases={"중복"},
        ),
    ),
))
def test_undeclared_empty_or_ambiguous_graph_rejected(equivalences):
    with pytest.raises(ValueError):
        DeclaredConceptGraphAnalyzer(equivalences)


def test_registry_changed_during_graph_lookup_fails_closed() -> None:
    analyzer = DeclaredConceptGraphAnalyzer(ALIASES)
    real_registry = _router(graph=False).registry

    class UnstableVisibleRegistry:
        version = 1

        def tools(self):
            self.version += 1
            return real_registry.tools()

    from schemarouter import PlanRequest
    with pytest.raises(PlanningError, match="declared concept source changed"):
        analyzer.analyze(
            PlanRequest(query="탄성계수"), UnstableVisibleRegistry(),
        )
