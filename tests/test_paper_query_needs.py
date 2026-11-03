"""Schema-independent query atoms resolve only through explicit owner declarations."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.concept_retrieval import NativeConceptCatalog, NativeDeclaredConcept
from schemarouter.paper_query_needs import (
    PaperQueryNeed,
    PaperQueryUnderstanding,
    _resolve_query_need,
)


@pytest.mark.parametrize("key,value", [("unit", "eV"), ("source_type", "calculated")])
def test_reserved_conditions_have_one_lossless_canonical_representation(key, value):
    incoming = {"concept": "band gap", key: value, "qualifiers": {key: value, "phase": "solid"}}
    need = PaperQueryNeed.model_validate(incoming)
    assert getattr(need, key) == value and need.qualifiers == {"phase": "solid"}
    assert incoming["qualifiers"] == {key: value, "phase": "solid"}
    from_qualifier = PaperQueryNeed.model_validate({
        "concept": "band gap", "qualifiers": {key: value},
    })
    assert getattr(from_qualifier, key) == value and from_qualifier.qualifiers == {}


@pytest.mark.parametrize("key", ["unit", "source_type"])
def test_conflicting_reserved_conditions_are_not_silently_replaced(key):
    with pytest.raises(ValueError):
        PaperQueryNeed.model_validate({
            "concept": "band gap", key: "first", "qualifiers": {key: "second"},
        })


def _catalog(*fields, aliases=("temperature", "기온"), cid="weather.temperature"):
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=cid, aliases=aliases, source_type="weather", license="reviewed",
        required_fields=fields or (CapabilityFieldContract(
            semantic_id="weather.temperature", json_schema={"type": "number"}, unit="K",
            qualifiers={"role": "current", "temporal": "present"},
        ),),
    ),))


@pytest.mark.parametrize("text", ("temperature", "TEMPERATURE", "기온", "weather.temperature"))
def test_whole_declared_alias_or_id_resolves_without_changing_owner_contract(text):
    catalog = _catalog()
    before = catalog.model_dump_json()
    assert _resolve_query_need(PaperQueryNeed(concept=text), catalog) == (
        "weather.temperature", False,
    )
    assert catalog.model_dump_json() == before


@pytest.mark.parametrize("text", (
    "temperature and risk", "tomorrow temperature", "metatemperature", "unlisted", "!!!",
))
def test_unknown_or_compound_atoms_never_become_partial_matches(text):
    assert _resolve_query_need(PaperQueryNeed(concept=text), _catalog()) == (None, False)


def test_normalized_alias_collisions_are_ambiguous_even_with_different_constraints():
    first = _catalog(aliases=("author.login",), cid="owner.author").concepts[0]
    other = first.model_copy(update={"concept_id": "owner.reviewer", "aliases": ("author login",)})
    catalog = NativeConceptCatalog(concepts=(first, other))
    assert _resolve_query_need(
        PaperQueryNeed(concept="author_login", unit="K"), catalog,
    ) == (None, True)


def test_normalized_alias_collision_with_another_concept_id_is_ambiguous():
    first = _catalog(aliases=("other concept",)).concepts[0]
    other = first.model_copy(update={"concept_id": "other.concept", "aliases": ("different",)})
    assert _resolve_query_need(
        PaperQueryNeed(concept="other concept"), NativeConceptCatalog(concepts=(first, other)),
    ) == (None, True)


@pytest.mark.parametrize("kwargs,global_source,expected", (
    ({"unit": "K"}, None, "weather.temperature"),
    ({"unit": "k"}, None, None),
    ({"unit": "Celsius"}, None, None),
    ({"qualifiers": {"role": "current", "temporal": "present"}}, None, "weather.temperature"),
    ({"qualifiers": {"role": "forecast"}}, None, None),
    ({"qualifiers": {"temporal": "tomorrow"}}, None, None),
    ({"qualifiers": {"path": "author.login"}}, None, None),
    ({"source_type": "weather"}, "weather", "weather.temperature"),
    ({"source_type": "Weather"}, None, None),
    ({"source_type": "crm"}, "weather", None),
    ({}, "crm", None),
))
def test_only_explicit_source_unit_role_path_and_temporal_conditions_resolve(
    kwargs, global_source, expected,
):
    assert _resolve_query_need(
        PaperQueryNeed(concept="temperature", **kwargs), _catalog(),
        global_source_type=global_source,
    ) == (expected, False)


def test_all_requested_conditions_must_hold_on_one_owner_field():
    catalog = _catalog(
        CapabilityFieldContract(
            semantic_id="weather.a", json_schema={"type": "number"}, unit="K",
            qualifiers={"role": "current"},
        ),
        CapabilityFieldContract(
            semantic_id="weather.b", json_schema={"type": "number"}, unit="Celsius",
            qualifiers={"role": "forecast", "temporal": "tomorrow"},
        ),
    )
    assert _resolve_query_need(PaperQueryNeed(concept="temperature"), catalog)[0]
    for need in (
        PaperQueryNeed(concept="temperature", unit="K", qualifiers={"role": "forecast"}),
        PaperQueryNeed(
            concept="temperature", qualifiers={"role": "current", "temporal": "tomorrow"},
        ),
    ):
        assert _resolve_query_need(need, catalog) == (None, False)
    assert _resolve_query_need(PaperQueryNeed(
        concept="temperature", unit="Celsius",
        qualifiers={"role": "forecast", "temporal": "tomorrow"},
    ), catalog) == ("weather.temperature", False)


def test_owner_declared_role_and_full_path_are_both_required():
    catalog = _catalog(CapabilityFieldContract(
        semantic_id="crm.login", json_schema={"type": "string"},
        qualifiers={"role": "author", "path": "author.login"},
    ), aliases=("author login",), cid="crm.author_login")
    assert _resolve_query_need(PaperQueryNeed(
        concept="author login", qualifiers={"role": "author", "path": "author.login"},
    ), catalog) == ("crm.author_login", False)
    assert _resolve_query_need(PaperQueryNeed(
        concept="author login", qualifiers={"role": "author", "path": "reviewer.login"},
    ), catalog) == (None, False)


def test_query_dto_preserves_raw_needs_exclusions_and_untrusted_scalar_hints():
    payload = {
        "intent_id": "lookup",
        "needs": [{"concept": "author login", "qualifiers": {"role": "author"}}],
        "excluded_concepts": ["reviewer login"], "named_tools": ["user-mentioned-name"],
        "parameter_hints": {"issue": 42, "active": True, "text": "원문"}, "source_type": "crm",
    }
    result = PaperQueryUnderstanding.model_validate_json(json.dumps(payload), strict=True)
    assert result.model_dump(mode="json")["needs"][0]["concept"] == "author login"
    assert result.excluded_concepts == ("reviewer login",)
    assert result.parameter_hints == payload["parameter_hints"]
    assert PaperQueryUnderstanding(intent_id=None).needs == ()
    schema = PaperQueryUnderstanding.model_json_schema()
    for model in (schema, schema["$defs"]["PaperQueryNeed"]):
        assert model["additionalProperties"] is False
        assert all(prop.get("description") for prop in model["properties"].values())
    assert not {"concept_ids", "catalog", "route_ids", "principal"} & schema["properties"].keys()


def test_valid_name_count_and_existing_hint_scalar_boundaries():
    need = PaperQueryNeed(concept="x" * 160, qualifiers={
        str(i): "v" * 160 for i in range(8)
    })
    assert len(need.qualifiers) == 8
    result = PaperQueryUnderstanding(
        intent_id="lookup", needs=tuple(PaperQueryNeed(concept=str(i)) for i in range(8)),
        parameter_hints={"min": -(2**63), "max": 2**63 - 1, "text": "é" * 256},
    )
    assert len(result.needs) == 8
    assert len(result.parameter_hints["text"].encode("utf-8")) == 512


@pytest.mark.parametrize("updates", (
    {"needs": "temperature"}, {"needs": ["temperature"]},
    {"needs": [{"concept": 7}]}, {"needs": [{"concept": " temperature"}]},
    {"needs": [{"concept": "x" * 161}]}, {"needs": [{"concept": "a\nb"}]},
    {"needs": [{"concept": "ok", "unit": 1}]},
    {"needs": [{"concept": "ok", "unit": "x" * 161}]},
    {"needs": [{"concept": "ok", "qualifiers": {"role": False}}]},
    {"needs": [{"concept": "ok", "qualifiers": {"role": "x" * 161}}]},
    {"needs": [{"concept": "ok", "qualifiers": {str(i): "v" for i in range(9)}}]},
    {"needs": [{"concept": "ok"}] * 9},
    {"excluded_concepts": ["x"] * 9}, {"excluded_concepts": ["same", "same"]},
    {"named_tools": ["x"] * 6}, {"intent_id": "invalid intent"},
    {"source_type": " weather"}, {"source_type": 1},
    {"parameter_hints": {"id": None}}, {"parameter_hints": {"id": {"nested": 1}}},
    {"parameter_hints": {"id": [1]}}, {"parameter_hints": {"id": float("nan")}},
    {"parameter_hints": {"id": 2**63}}, {"parameter_hints": {"id": "x" * 513}},
    {"parameter_hints": {"id": "é" * 257}},
    {"parameter_hints": {str(i): i for i in range(9)}},
    {"concept_ids": ["hidden-id"]}, {"route_ids": ["private.read"]},
))
def test_invalid_json_shapes_and_bounds_are_rejected(updates):
    with pytest.raises(ValidationError):
        PaperQueryUnderstanding.model_validate_json(
            json.dumps({"intent_id": "lookup", **updates}), strict=True,
        )


def test_total_query_understanding_byte_bound_includes_raw_constraints_and_hints():
    payload = {
        "intent_id": "lookup", "needs": [{"concept": "x" * 160}] * 8,
        "excluded_concepts": ["y" * 159 + str(i) for i in range(5)],
        "parameter_hints": {str(i): "x" * 500 for i in range(4)},
    }
    with pytest.raises(ValidationError):
        PaperQueryUnderstanding.model_validate_json(json.dumps(payload), strict=True)
