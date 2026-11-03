"""Internal concept-union keys cannot reject otherwise valid owner declarations."""
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
    NativeSchemaPostingIndex,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperUnderstanding,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.paper_understood_direct_plan import _source_owned_understood_group

ACTOR = PrincipalContext(subject="proof-key", roles=("reader",))


def _source(aliases):
    catalog = NativeConceptCatalog(concepts=tuple(
        NativeDeclaredConcept(
            concept_id=f"case.{name}", aliases=(alias,), source_type="case", license="reviewed",
            required_fields=(CapabilityFieldContract(
                semantic_id=f"case.{name}", json_schema={"type": "string"},
            ),),
        ) for name, alias in zip(("first", "second"), aliases, strict=True)
    ))
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="case.lookup", required_concept_ids=("case.first", "case.second"),
    ),))
    understood = PaperUnderstanding(intent_id="case.lookup")
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="case.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(ToolSpec(name="case", source_type="case", license="reviewed", endpoints=[
        EndpointSpec(name="read", read_only=True, output_fields=[
            FieldSpec(name=name, semantic_id=f"case.{name}", json_schema={"type": "string"})
            for name in ("first", "second")
        ]),
    ]))
    return router, catalog, intents, understood


@pytest.mark.parametrize("aliases", (
    ("a" * 140, "b" * 140),
    ("가" * 90, "나" * 90),
))
def test_public_understood_plan_accepts_long_combined_aliases_and_retains_rank_inputs(
    aliases, monkeypatch,
):
    router, catalog, intents, understood = _source(aliases)
    session = router.prepare_field_routing(catalog=catalog)
    seen = []
    original = NativeSchemaPostingIndex.lookup

    def lookup(self, *args, **kwargs):
        seen.append(kwargs.get("_paper_rank_aliases"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(NativeSchemaPostingIndex, "lookup", lookup)
    plan = session.compile_understood(
        understood, principal=ACTOR, intent_registry=intents,
        rank_policy=PaperNativeRankPolicy(snapshot_id=session.snapshot_id),
    )
    assert plan.status == "ready" and plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["case.read"]
    assert plan.calls[0].call.fields == ["first", "second"]
    assert seen and all(value == tuple((alias,) for alias in aliases) for value in seen)
    assert plan.snapshot_id == session.snapshot_id and not plan.executable_authority

    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    denied = session.compile_understood(understood, principal=ACTOR, intent_registry=intents)
    assert denied.status == "no_proven_hit" and denied.calls == ()
    assert not denied.coverage.complete


@pytest.mark.parametrize("aliases", (
    ("a" * 128, "b" * 127),  # Exactly 256 characters/bytes.
    ("가" * 85, "나" * 85 + "b"),  # Exactly 512 UTF-8 bytes.
))
def test_existing_canonical_key_is_unchanged_within_both_bounds(aliases):
    _, catalog, intents, understood = _source(aliases)
    _, group = _source_owned_understood_group(understood, catalog, intents)
    assert group.aliases == (" ".join(aliases),)


def test_oversized_key_is_bounded_deterministic_and_sensitive_to_owner_declarations():
    _, catalog, intents, understood = _source(("a" * 140, "b" * 140))
    _, first = _source_owned_understood_group(understood, catalog, intents)
    _, repeated = _source_owned_understood_group(understood, catalog, intents)
    changed = catalog.model_copy(update={"concepts": (
        catalog.concepts[0].model_copy(update={"aliases": ("c" * 140,)}), catalog.concepts[1],
    )})
    _, different = _source_owned_understood_group(understood, changed, intents)
    assert first == repeated and first.aliases != different.aliases
    assert len(first.aliases[0]) <= 256 and len(first.aliases[0].encode("utf-8")) <= 512
    assert first.required_fields == repeated.required_fields == different.required_fields
