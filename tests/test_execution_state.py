from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemarouter import (
    CapabilityFieldContract,
    ObservedStateField,
    TypedExecutionState,
    evaluate_state_eligibility,
)


def field(semantic_id: str, **kwargs) -> CapabilityFieldContract:
    return CapabilityFieldContract(semantic_id=semantic_id, **kwargs)


def test_satisfied_typed_state_is_eligible() -> None:
    requirement = field("resource.material_id", json_schema={"type": "string"})
    state = TypedExecutionState(
        completed_route_ids=("search_material",),
        observed_fields=[ObservedStateField(contract=requirement, stable_identifier="mp-149")],
        last_status="success",
        task_incomplete=True,
    )
    result = evaluate_state_eligibility([requirement], state)
    assert result.status == "eligible"
    assert result.eligible


def test_missing_typed_state_is_excluded_with_deterministic_reason() -> None:
    result = evaluate_state_eligibility(
        [field("resource.material_id", json_schema={"type": "string"})],
        TypedExecutionState(task_incomplete=True),
    )
    assert result.status == "missing_required_state"
    assert result.reasons[0].semantic_id == "resource.material_id"


def test_incompatible_observed_type_fails_closed() -> None:
    result = evaluate_state_eligibility(
        [field("resource.material_id", json_schema={"type": "string"})],
        TypedExecutionState(
            observed_fields=[
                ObservedStateField(
                    contract=field("resource.material_id", json_schema={"type": "number"})
                )
            ]
        ),
    )
    assert result.status == "incompatible_state"
    assert not result.eligible


def test_duplicate_completed_route_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TypedExecutionState(completed_route_ids=("route-a", "route-a"))


def test_state_contract_has_no_oracle_or_rank_fields() -> None:
    assert "gold_routes" not in TypedExecutionState.model_fields
    assert "future_routes" not in TypedExecutionState.model_fields
    assert "rank_scores" not in TypedExecutionState.model_fields
    assert "tool_output" not in TypedExecutionState.model_fields
