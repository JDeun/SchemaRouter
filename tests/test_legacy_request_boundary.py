"""Historical request types remain source-only, with their prior wire contract."""

import pytest
from pydantic import ValidationError

from schemarouter import EvidenceRequirements, PaperPlanRequest
from scripts.research_legacy_planning.requests import PlanRequest, QueryIntent


def test_historical_intent_preserves_evidence_and_preference_metadata() -> None:
    intent = QueryIntent(
        concepts=["material.conductivity"],
        preferred_tools=["catalog"],
        preferred_endpoints=["search"],
        arguments={"material_id": "m1"},
        evidence=EvidenceRequirements(provenance=True),
        field_evidence={"material.conductivity": EvidenceRequirements(units=True)},
    )
    assert QueryIntent.model_validate_json(intent.model_dump_json()) == intent
    assert isinstance(intent.evidence, EvidenceRequirements)
    assert intent.field_evidence["material.conductivity"].units


def test_historical_request_modes_keep_defaults_and_explicit_choices() -> None:
    default = PlanRequest(query="read conductivity")
    assert default.retrieval_mode == "coverage"
    assert default.fallback_scope == "disabled"
    for scope in ("disabled", "same_provider", "cross_provider"):
        for mode in ("coverage", "corroborate"):
            request = PlanRequest.model_validate({
                "query": "read conductivity", "retrieval_mode": mode, "fallback_scope": scope,
            })
            assert PlanRequest.model_validate_json(request.model_dump_json()) == request


@pytest.mark.parametrize("field", ["retrieval_mode", "fallback_scope"])
def test_historical_request_rejects_invalid_modes(field: str) -> None:
    with pytest.raises(ValidationError):
        PlanRequest.model_validate({"query": "read conductivity", field: "invalid"})


@pytest.mark.parametrize(("field", "value"), [
    ("retrieval_mode", "corroborate"), ("fallback_scope", "cross_provider"),
    ("preferred_tools", ["catalog"]),
])
def test_paper_request_rejects_legacy_request_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        PaperPlanRequest.model_validate({"query": "read conductivity", field: value})
