# Issue #707 regression coverage.
from schemarouter.capability_constraints import (
    CapabilityOperationalMetadata,
    HostCapabilityConstraints,
    evaluate_operational_constraints,
)


def test_hard_constraint_fails_closed_when_metadata_is_unknown() -> None:
    result = evaluate_operational_constraints(
        CapabilityOperationalMetadata(),
        HostCapabilityConstraints(max_cost=0.01),
    )

    assert result.eligible is False
    assert result.reasons[0].code == "metadata_unknown"


def test_locality_privacy_and_network_constraints_are_hard_filters() -> None:
    result = evaluate_operational_constraints(
        CapabilityOperationalMetadata(
            locality="remote",
            region="us-east",
            privacy_class="public",
            network_required=True,
        ),
        HostCapabilityConstraints(
            allowed_localities={"local"},
            allowed_regions={"kr"},
            allowed_privacy_classes={"sensitive"},
            network_allowed=False,
        ),
    )

    assert result.eligible is False
    assert {reason.code for reason in result.reasons} == {
        "locality_constraint",
        "residency_constraint",
        "privacy_constraint",
        "network_constraint",
    }


def test_soft_preferences_only_score_eligible_candidate() -> None:
    result = evaluate_operational_constraints(
        CapabilityOperationalMetadata(
            estimated_latency_ms=20,
            estimated_cost=0.1,
            locality="local",
        ),
        HostCapabilityConstraints(
            max_latency_ms=100,
            max_cost=1,
            allowed_localities={"local", "remote"},
            prefer_local=True,
            prefer_lower_latency=True,
            prefer_lower_cost=True,
        ),
    )

    assert result.eligible is True
    assert result.preference_score > 1.0
    assert [reason.code for reason in result.reasons] == ["eligible"]


def test_unknown_soft_preference_metadata_does_not_exclude_candidate() -> None:
    result = evaluate_operational_constraints(
        CapabilityOperationalMetadata(),
        HostCapabilityConstraints(prefer_lower_latency=True, prefer_lower_cost=True),
    )

    assert result.eligible is True
    assert result.preference_score == 0.0
