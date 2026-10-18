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
    # Original source descriptions are English and contain no declared
    # translated operation alias. This is an intentionally separate DEV case.
    assert baseline.candidates == []
    router = _router(graph=True)
    result = router.retrieve_authorized(
        language_query, principal=VIEWER, k=5,
    )
    assert [candidate.route_id for candidate in result.candidates] == [
        "materials.read",
    ]
    c = result.candidates[0]
    assert c.source_type == "materials_data"
    assert c.license == "CC-BY-4.0"
    assert [f.semantic_id for f in c.output_fields] == [
        "mechanical.elastic_modulus",
    ]
    assert c.tool_fingerprint and c.endpoint_fingerprint


def test_hidden_or_denied_semantic_edges_do_not_widen_eligibility() -> None:
    router = _router(graph=True)
    for query in ("기밀물성", "機密強度"):
        result = router.retrieve_authorized(query, principal=VIEWER, k=5)
        assert result.candidates == []
    public = router.retrieve_authorized("탄성계수", principal=VIEWER, k=5)
    encoded = json.dumps(public.model_dump(mode="json"), ensure_ascii=False)
    assert "restricted.read" not in encoded
    assert "private_value" not in encoded
    assert "mechanical.secret_strength" not in encoded


def test_unregistered_or_unrelated_alias_cannot_guess_new_semantics() -> None:
    router = _router(graph=True)
    assert router.retrieve_authorized(
        "탄성계수 관련 추가 질문", principal=VIEWER,
    ).candidates == []
    assert router.retrieve_authorized(
        "unavailable", principal=VIEWER,
    ).candidates == []


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
