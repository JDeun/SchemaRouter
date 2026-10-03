from schemarouter.capability_fallback import evaluate_fallback_eligibility
from schemarouter.contract_validation import CapabilityContractValidation
from schemarouter.execution_state import StateEligibility


def test_legacy_health_only_behavior_is_preserved_without_contract_metadata() -> None:
    assert evaluate_fallback_eligibility(authorized=True, healthy=True).eligible is True

    unavailable = evaluate_fallback_eligibility(authorized=True, healthy=False)
    assert unavailable.eligible is False
    assert unavailable.reasons == ["method_unhealthy"]


def test_alive_method_can_be_ineligible_when_contract_is_incompatible() -> None:
    result = evaluate_fallback_eligibility(
        authorized=True,
        healthy=True,
        contract_validation=CapabilityContractValidation(
            status="incompatible",
            fields=[],
        ),
    )

    assert result.eligible is False
    assert result.reasons == ["contract_incompatible"]


def test_contract_drift_and_state_are_composed_with_health() -> None:
    result = evaluate_fallback_eligibility(
        authorized=True,
        healthy=True,
        contract_drifted=True,
        state_eligibility=StateEligibility(
            status="missing_required_state",
            reasons=[],
        ),
    )

    assert result.eligible is False
    assert result.reasons == ["contract_drifted", "state_ineligible"]


def test_host_denial_cannot_be_widened_by_healthy_compatible_candidate() -> None:
    result = evaluate_fallback_eligibility(
        authorized=False,
        healthy=True,
        contract_validation=CapabilityContractValidation(status="valid", fields=[]),
    )

    assert result.eligible is False
    assert result.reasons == ["policy_denied"]


def test_retrieval_membership_is_part_of_effective_candidate_intersection() -> None:
    result = evaluate_fallback_eligibility(
        authorized=True,
        healthy=True,
        retrieved=False,
    )

    assert result.eligible is False
    assert result.reasons == ["not_retrieved"]
