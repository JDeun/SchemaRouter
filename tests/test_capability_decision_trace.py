from __future__ import annotations

from schemarouter.capability_constraints import (
    OperationalConstraintReason,
    OperationalConstraintResult,
)
from schemarouter.capability_decision_trace import (
    CapabilityDecisionCandidateInput,
    build_capability_decision_trace,
    render_capability_decision_trace,
)
from schemarouter.capability_eligibility import (
    CapabilityEligibilityReason,
    explain_capability_eligibility,
)
from schemarouter.capability_fallback import CapabilityFallbackEligibility
from schemarouter.capability_lineage import (
    CapabilityLineageHop,
    build_capability_lineage,
)
from schemarouter.capability_negotiation import CapabilityNegotiationCandidate
from schemarouter.execution_state import StateEligibility, StateEligibilityReason


def _visible_candidate(capability_id: str) -> CapabilityDecisionCandidateInput:
    explanation = explain_capability_eligibility(
        capability_id,
        visible=True,
        reasons=[
            CapabilityEligibilityReason(
                code="method_unhealthy",
                detail="health probe unavailable",
            )
        ],
    )
    assert explanation is not None
    return CapabilityDecisionCandidateInput(
        capability_id=capability_id,
        visible=True,
        final_disposition="excluded",
        retrieval="retrieved",
        health="unhealthy",
        drift="drifted",
        policy="denied",
        eligibility=explanation,
        state=StateEligibility(
            status="missing_required_state",
            reasons=[
                StateEligibilityReason(
                    code="missing_required_state",
                    semantic_id="resource.material_id",
                    detail="required semantic state has not been observed",
                )
            ],
        ),
        operational=OperationalConstraintResult(
            eligible=False,
            reasons=[
                OperationalConstraintReason(
                    code="privacy_constraint",
                    detail="privacy class is outside host allow-set",
                )
            ],
        ),
        negotiation=CapabilityNegotiationCandidate(
            capability_id=capability_id,
            status="incompatible",
            reasons=("missing semantic output material.band_gap",),
        ),
        fallback=CapabilityFallbackEligibility(
            eligible=False,
            reasons=["contract_drifted", "state_ineligible"],
        ),
    )


def test_trace_aggregates_existing_decisions_without_recomputing_policy() -> None:
    trace = build_capability_decision_trace(
        [_visible_candidate("materials.rest.summary")],
        snapshot_id="snapshot-1",
        registry_version=7,
    )

    assert trace is not None
    assert trace.snapshot_id == "snapshot-1"
    assert trace.registry_version == 7
    candidate = trace.candidates[0]
    assert candidate.final_disposition == "excluded"
    assert candidate.health == "unhealthy"
    assert candidate.drift == "drifted"
    assert candidate.policy == "denied"

    reason_pairs = [(reason.stage, reason.code) for reason in candidate.reasons]
    assert ("eligibility", "method_unhealthy") in reason_pairs
    assert ("state", "missing_required_state") in reason_pairs
    assert ("health", "method_unhealthy") in reason_pairs
    assert ("drift", "contract_drifted") in reason_pairs
    assert ("policy", "policy_denied") in reason_pairs
    assert ("operational", "privacy_constraint") in reason_pairs
    assert ("negotiation", "incompatible") in reason_pairs
    assert ("fallback", "state_ineligible") in reason_pairs


def test_invisible_candidate_is_not_disclosed_by_trace_or_rendering() -> None:
    trace = build_capability_decision_trace(
        [
            CapabilityDecisionCandidateInput(
                capability_id="public.read",
                visible=True,
                final_disposition="candidate",
            ),
            CapabilityDecisionCandidateInput(
                capability_id="secret.admin.delete",
                visible=False,
                final_disposition="excluded",
                policy="denied",
            ),
        ],
        registry_version=2,
    )

    assert trace is not None
    assert [item.capability_id for item in trace.candidates] == ["public.read"]
    serialized = trace.model_dump_json()
    assert "secret.admin.delete" not in serialized

    rendered = render_capability_decision_trace(trace, detailed=True)
    assert "secret.admin.delete" not in str(rendered)


def test_trace_is_deterministic_across_input_order() -> None:
    a = CapabilityDecisionCandidateInput(
        capability_id="a",
        final_disposition="selected",
        retrieval="retrieved",
        health="healthy",
        policy="allowed",
    )
    b = CapabilityDecisionCandidateInput(
        capability_id="b",
        final_disposition="fallback",
        retrieval="retrieved",
        health="healthy",
        policy="allowed",
    )

    first = build_capability_decision_trace([b, a], snapshot_id="s", registry_version=3)
    second = build_capability_decision_trace([a, b], snapshot_id="s", registry_version=3)

    assert first == second
    assert first is not None
    assert [item.capability_id for item in first.candidates] == ["a", "b"]


def test_trace_includes_compact_fallback_lineage_without_payloads() -> None:
    selected = CapabilityLineageHop(
        provider="materials-project",
        access_method="rest",
        route_id="materials.rest.summary",
        capability_id="material.summary",
        reason="selected",
    )
    actual = CapabilityLineageHop(
        provider="materials-project",
        access_method="optimade",
        route_id="materials.optimade.summary",
        capability_id="material.summary",
        reason="method_fallback",
    )
    lineage = build_capability_lineage(
        selected=selected,
        actual=actual,
        fallbacks=[actual],
    )

    trace = build_capability_decision_trace(
        [
            CapabilityDecisionCandidateInput(
                capability_id="material.summary",
                final_disposition="fallback",
            )
        ],
        lineage=lineage,
    )
    assert trace is not None

    compact = render_capability_decision_trace(trace)
    assert compact["lineage"] == {
        "lineage_id": lineage.lineage_id,
        "selected": "materials.rest.summary",
        "actual": "materials.optimade.summary",
    }

    detailed = render_capability_decision_trace(trace, detailed=True)
    assert detailed["lineage"]["fallbacks"][0]["access_method"] == "optimade"

    serialized = trace.model_dump_json()
    for forbidden in ("payload", "arguments", "credentials", "headers"):
        assert forbidden not in serialized


def test_trace_models_exclude_rank_score_and_execution_authority() -> None:
    trace = build_capability_decision_trace(
        [CapabilityDecisionCandidateInput(capability_id="public.read")]
    )
    assert trace is not None

    candidate_fields = set(type(trace.candidates[0]).model_fields)
    assert "rank" not in candidate_fields
    assert "score" not in candidate_fields
    assert "payload" not in candidate_fields
    assert "arguments" not in candidate_fields
    assert "headers" not in candidate_fields
    assert "credentials" not in candidate_fields

    forbidden_methods = {
        "execute",
        "invoke",
        "commit",
        "rollback",
        "retry",
        "compensate",
        "authorize",
        "plan",
    }
    assert forbidden_methods.isdisjoint(dir(trace))


def test_disabled_trace_construction_returns_none() -> None:
    assert build_capability_decision_trace([], enabled=False) is None


def test_trace_rejects_mismatched_component_identity() -> None:
    import pytest

    with pytest.raises(ValueError, match="eligibility capability_id"):
        CapabilityDecisionCandidateInput(
            capability_id="a",
            eligibility=explain_capability_eligibility("b", visible=True),
        )

    with pytest.raises(ValueError, match="negotiation capability_id"):
        CapabilityDecisionCandidateInput(
            capability_id="a",
            negotiation=CapabilityNegotiationCandidate(
                capability_id="b",
                status="exact",
            ),
        )


def test_trace_rejects_duplicate_visible_capability_ids() -> None:
    import pytest

    with pytest.raises(ValueError, match="must be unique"):
        build_capability_decision_trace(
            [
                CapabilityDecisionCandidateInput(capability_id="a"),
                CapabilityDecisionCandidateInput(capability_id="a"),
            ]
        )
