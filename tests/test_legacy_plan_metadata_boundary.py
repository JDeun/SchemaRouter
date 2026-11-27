"""Product execution fields and historical lexical diagnostics stay separate."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemarouter import ExecutionPlan, FallbackRoute, ToolCall
from scripts.research_legacy_planning.plan_models import ExecutionPlan as HistoricalPlan
from scripts.research_legacy_planning.plan_models import FallbackRoute as HistoricalFallback
from scripts.research_legacy_planning.plan_models import (
    FieldSelectionExplanation,
    PlanExplanation,
    ScoreComponent,
)
from scripts.research_legacy_planning.plan_models import ToolCall as HistoricalCall


def _historical_call() -> HistoricalCall:
    return HistoricalCall(
        tool="records",
        endpoint="read",
        arguments={"id": "r1"},
        fields=["value"],
        schema_fingerprint="endpoint-fingerprint",
        tool_fingerprint="tool-fingerprint",
        score=12.5,
        explanation=PlanExplanation(
            candidate_selection="deterministic",
            score_components=[ScoreComponent(kind="field_exact", value=12.5, matched="value")],
            field_selection=[FieldSelectionExplanation(field="value", reason="field_exact")],
            ignored_arguments=["undeclared"],
        ),
    )


def test_product_toolcall_rejects_legacy_metadata_at_all_wire_levels() -> None:
    historical = _historical_call()
    payload = historical.model_dump(mode="python")
    with pytest.raises(ValidationError):
        ToolCall.model_validate(payload, strict=True)

    call = ToolCall.model_validate(
        historical.model_dump(exclude={"score", "explanation"}), strict=True,
    )
    expected = ExecutionPlan(query="read", registry_version=1, calls=[call])
    assert {"score", "explanation"}.isdisjoint(call.model_dump())
    assert {"score", "explanation"}.isdisjoint(ToolCall.model_json_schema()["properties"])

    with pytest.raises(ValidationError):
        ExecutionPlan.model_validate(
            {**expected.model_dump(), "calls": [payload]}, strict=True,
        )
    with pytest.raises(ValidationError):
        ExecutionPlan.model_validate(
            {
                **expected.model_dump(),
                "fallback_routes": [{"primary_call_index": 0, "alternatives": [payload]}],
            },
            strict=True,
        )


def test_historical_plan_retains_primary_and_fallback_metadata_after_roundtrip() -> None:
    call = _historical_call()
    plan = HistoricalPlan(
        query="read",
        registry_version=1,
        calls=[call],
        fallback_routes=[HistoricalFallback(primary_call_index=0, alternatives=[call])],
    )
    assert isinstance(plan, ExecutionPlan)
    assert isinstance(plan.calls[0], ToolCall)
    assert isinstance(plan.fallback_routes[0], FallbackRoute)
    wire = plan.model_dump(mode="json")
    assert "planning_status" not in wire
    assert wire["calls"][0] == call.model_dump(mode="json")
    assert wire["calls"][0]["score"] == 12.5
    assert wire["calls"][0]["explanation"]["ignored_arguments"] == ["undeclared"]
    assert wire["fallback_routes"][0]["alternatives"][0] == wire["calls"][0]
    assert HistoricalPlan.model_validate(wire, strict=True) == plan
    assert HistoricalPlan.model_validate_json(plan.model_dump_json(), strict=True) == plan
    with pytest.raises(ValidationError):
        ExecutionPlan.model_validate(wire, strict=True)


def test_historical_schema_does_not_accept_corrupt_nested_explanation() -> None:
    call = _historical_call()
    forged = call.model_copy(update={"explanation": ["not a structured explanation"]})
    plan = HistoricalPlan(query="read", registry_version=1, calls=[call])
    broken = plan.model_copy(update={"calls": [forged]})
    with pytest.raises(ValidationError):
        HistoricalPlan.model_validate(broken.model_dump(warnings=False), strict=True)


def test_historical_fallbacks_keep_product_bounds_and_index_validation() -> None:
    call = _historical_call()
    with pytest.raises(ValidationError):
        HistoricalFallback(primary_call_index=0, alternatives=[call] * 9)
    with pytest.raises(ValidationError):
        HistoricalPlan(
            query="read", registry_version=1, calls=[call],
            fallback_routes=[HistoricalFallback(primary_call_index=1, alternatives=[call])],
        )
