# Issue #712 regression coverage.
from schemarouter.capability_eligibility import (
    CapabilityEligibilityReason,
    explain_capability_eligibility,
)


def test_visible_eligible_capability_has_stable_default_reason() -> None:
    result = explain_capability_eligibility("provider.route", visible=True)

    assert result is not None
    assert result.eligible is True
    assert result.model_dump(mode="json") == {
        "capability_id": "provider.route",
        "eligible": True,
        "reasons": [{"code": "eligible", "detail": "", "children": []}],
    }


def test_multiple_reasons_are_machine_readable_and_composable() -> None:
    result = explain_capability_eligibility(
        "provider.route",
        visible=True,
        reasons=[
            CapabilityEligibilityReason(
                code="method_unhealthy",
                detail="health probe unavailable",
            ),
            CapabilityEligibilityReason(
                code="type_or_unit_incompatible",
                children=[
                    CapabilityEligibilityReason(
                        code="unsupported_or_unknown",
                        detail="unit metadata missing",
                    )
                ],
            ),
        ],
    )

    assert result is not None
    assert result.eligible is False
    assert [item.code for item in result.reasons] == [
        "method_unhealthy",
        "type_or_unit_incompatible",
    ]
    assert result.reasons[1].children[0].code == "unsupported_or_unknown"


def test_hidden_capability_returns_no_explanation() -> None:
    result = explain_capability_eligibility(
        "secret.admin.route",
        visible=False,
        reasons=[CapabilityEligibilityReason(code="policy_denied")],
    )

    assert result is None
