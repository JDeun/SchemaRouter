from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    UnitConversion,
)
from schemarouter.capability_negotiation import (
    CapabilityNegotiationRequest,
    negotiate_capabilities,
)


def _field(semantic_id: str, *, unit: str | None = None) -> CapabilityFieldContract:
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema={"type": "number"},
        unit=unit,
        dimension="energy" if unit else None,
    )


def test_negotiation_distinguishes_exact_convertible_and_incompatible() -> None:
    request = CapabilityNegotiationRequest(required_outputs=[_field("band_gap", unit="eV")])
    capabilities = [
        CapabilityContract(capability_id="exact", produces=[_field("band_gap", unit="eV")]),
        CapabilityContract(capability_id="convertible", produces=[_field("band_gap", unit="meV")]),
        CapabilityContract(capability_id="missing", produces=[_field("density")]),
    ]
    context = CompatibilityContext(
        unit_conversions=[
            UnitConversion(
                from_unit="meV",
                to_unit="eV",
                dimension="energy",
                scale=0.001,
            )
        ]
    )

    result = negotiate_capabilities(request, capabilities, context=context)

    assert [(item.capability_id, item.status) for item in result.candidates] == [
        ("convertible", "convertible"),
        ("exact", "exact"),
        ("missing", "incompatible"),
    ]


def test_host_authorization_is_never_widened() -> None:
    request = CapabilityNegotiationRequest(required_outputs=[])
    capability = CapabilityContract(capability_id="secret")

    result = negotiate_capabilities(
        request,
        [capability],
        authorized_capability_ids=set(),
    )

    assert result.candidates[0].status == "policy_denied"


def test_unavailable_candidate_is_distinct_from_contract_mismatch() -> None:
    request = CapabilityNegotiationRequest(required_outputs=[_field("energy")])
    capability = CapabilityContract(capability_id="mcp.energy", produces=[_field("energy")])

    result = negotiate_capabilities(
        request,
        [capability],
        unavailable_capability_ids={"mcp.energy"},
    )

    assert result.candidates[0].status == "unavailable"


def test_scientific_semantic_equivalence_fixture() -> None:
    request = CapabilityNegotiationRequest(required_outputs=[_field("band_gap", unit="eV")])
    capability = CapabilityContract(
        capability_id="optimade.bandgap",
        produces=[_field("electronic_gap", unit="eV")],
    )
    context = CompatibilityContext(
        semantic_equivalences=[{"band_gap", "electronic_gap"}],
    )

    result = negotiate_capabilities(request, [capability], context=context)

    assert result.candidates[0].status in {"exact", "compatible"}
