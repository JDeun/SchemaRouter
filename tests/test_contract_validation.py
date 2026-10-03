from __future__ import annotations

from schemarouter import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    ContractObservation,
    SemanticEquivalence,
    UnitConversion,
    validate_capability_input,
    validate_capability_output,
)


def field(semantic_id: str, **kwargs) -> CapabilityFieldContract:
    return CapabilityFieldContract(semantic_id=semantic_id, **kwargs)


def test_input_validation_reports_missing_field() -> None:
    capability = CapabilityContract(
        capability_id="get_structure",
        requires=[field("resource.material_id", json_schema={"type": "string"})],
    )
    result = validate_capability_input(capability, [])
    assert result.status == "missing"
    assert not result.valid


def test_output_validation_fails_closed_on_incompatible_type() -> None:
    capability = CapabilityContract(
        capability_id="search",
        produces=[field("resource.material_id", json_schema={"type": "string"})],
    )
    result = validate_capability_output(
        capability,
        [ContractObservation(
            contract=field("resource.material_id", json_schema={"type": "number"})
        )],
    )
    assert result.status == "incompatible"


def test_output_validation_distinguishes_declared_conversion() -> None:
    capability = CapabilityContract(
        capability_id="elasticity",
        produces=[
            field(
                "elastic_modulus",
                json_schema={"type": "number"},
                unit="Pa",
                dimension="pressure",
            )
        ],
    )
    context = CompatibilityContext(
        unit_conversions=[
            UnitConversion(dimension="pressure", from_unit="GPa", to_unit="Pa")
        ]
    )
    result = validate_capability_output(
        capability,
        [ContractObservation(contract=field(
            "elastic_modulus",
            json_schema={"type": "number"},
            unit="GPa",
            dimension="pressure",
        ))],
        context=context,
    )
    assert result.status == "convertible"
    assert result.valid


def test_semantic_alias_validation_requires_explicit_declaration() -> None:
    capability = CapabilityContract(
        capability_id="provider-a",
        produces=[field("material.band_gap", json_schema={"type": "number"})],
    )
    observation = ContractObservation(
        contract=field("material.bandgap", json_schema={"type": "number"})
    )
    assert validate_capability_output(capability, [observation]).status == "missing"

    context = CompatibilityContext(
        semantic_equivalences=[
            SemanticEquivalence(
                canonical_id="material.band_gap",
                aliases={"material.bandgap"},
            )
        ]
    )
    assert validate_capability_output(
        capability,
        [observation],
        context=context,
    ).status == "valid"


def test_capability_without_validation_metadata_is_backward_compatible() -> None:
    capability = CapabilityContract(capability_id="legacy")
    assert validate_capability_input(capability, []).status == "valid"
    assert validate_capability_output(capability, []).status == "valid"
