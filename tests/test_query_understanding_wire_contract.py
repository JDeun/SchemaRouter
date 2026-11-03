"""Extraction protocol checks; deterministic responses do not measure model accuracy."""
from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator
from test_schema_independent_field_query import _query
from test_understood_multi_concept import ACTOR, CATALOG, INTENTS, _field, _router, _tool

from schemarouter import PaperQueryUnderstanding
from schemarouter.errors import PolicyViolationError


@pytest.mark.asyncio
async def test_wire_requires_explicit_channels_but_legacy_dto_defaults_still_decode():
    seen = []
    plan = await _query(_router(), {"intent_id": None}, observe=seen)
    assert plan.calls == () and not plan.coverage.complete
    schema = seen[0]["response_schema"]
    assert set(schema["required"]) == set(schema["properties"])
    need_schema = schema["$defs"]["PaperQueryNeed"]
    assert set(need_schema["required"]) == {"concept", "unit", "source_type", "qualifiers"}
    response = PaperQueryUnderstanding(intent_id=None).model_dump(mode="json")
    Draft202012Validator(schema).validate(response)
    for channel in ("needs", "needs_truncated", "excluded_concepts", "named_tools",
                    "parameter_hints", "source_type"):
        missing = {key: value for key, value in response.items() if key != channel}
        assert not Draft202012Validator(schema).is_valid(missing)
    response["needs"] = [{"concept": "reserve equipment"}]
    assert not Draft202012Validator(schema).is_valid(response)
    assert PaperQueryUnderstanding.model_validate({"intent_id": None}).needs == ()
    assert PaperQueryUnderstanding.model_json_schema()["required"] == ["intent_id"]


@pytest.mark.asyncio
async def test_unsupported_goal_keeps_explicit_conditions_paths_and_scalar_labels():
    seen = []
    response = {
        "intent_id": None,
        "needs": [{"concept": "reserve equipment", "unit": None, "source_type": None,
                   "qualifiers": {"time": "next week", "source_path": "/payload/item",
                                  "result_path": "/reservation/item"}}],
        "needs_truncated": False, "excluded_concepts": ["equipment purchase"],
        "named_tools": [], "parameter_hints": {"requested_count": 3}, "source_type": None,
    }
    plan = await _query(_router(), response, observe=seen,
                        query="Reserve equipment next week, requested_count=3; source path "
                        "/payload/item, result path /reservation/item; exclude equipment purchase")
    assert plan.status == "no_proven_hit" and plan.calls == () and not plan.coverage.complete
    assert plan.understanding_hints == response
    unmet = next(row for row in plan.coverage.uncovered if row.semantic_id == "reserve equipment")
    assert {"time=next week", "source_path=/payload/item", "result_path=/reservation/item"} <= set(
        unmet.qualifiers)
    rules = " ".join(seen[0]["rules"])
    assert "data, action or goal" in rules and "intent_id is null" in rules
    assert "narrowest applicable" in rules and "additional needs" in rules
    assert "excluded_concepts" in rules and "not in needs or qualifiers" in rules
    assert "qualifiers.source_path" in rules and "qualifiers.result_path" in rules
    assert "explicit parameter labels" in rules and "not subject matter" in rules


@pytest.mark.asyncio
async def test_callback_source_mutation_is_opaque_and_payload_has_no_owner_metadata():
    router = _router()
    session = router.prepare_field_routing(catalog=CATALOG)

    def model(payload):
        encoded = json.dumps(payload)
        assert "material.band_gap" not in encoded and "materials-fixture-license" not in encoded
        assert "required_concept_ids" not in encoded and "offered_concepts" not in encoded
        changed = router.registry.get("materials")
        changed.endpoints[0].output_fields[0].semantic_id = "PRIVATE_CHANGED_SEMANTIC"
        router.add_tool(changed, replace=True)
        return {"intent_id": None, "needs": [{"concept": "reserve equipment"}]}

    with pytest.raises(PolicyViolationError) as exc:
        await session.acompile_query(
            "reserve equipment", principal=ACTOR, model=model, intent_registry=INTENTS,
            model_visible_intent_ids=tuple(intent.intent_id for intent in INTENTS.intents),
        )
    assert "PRIVATE_CHANGED_SEMANTIC" not in str(exc.value)


@pytest.mark.asyncio
async def test_chosen_broad_intent_keeps_its_six_required_routes_and_k5_bound():
    router = _router()
    for name, family, semantic, kind in (
        ("cases", "crm", "crm.status", "string"),
        ("inventory", "inventory", "stock", "integer"),
        ("weather", "weather", "temperature", "number"),
        ("finance", "finance", "price", "number"),
    ):
        router.add_tool(_tool(name, family, [_field("value", semantic, kind)]))
    plan = await _query(router, {"intent_id": "all.metrics", "needs": [{"concept": "band gap"}]})
    assert plan.status == "budget_unsatisfied" and plan.calls == ()
    assert not plan.coverage.complete
