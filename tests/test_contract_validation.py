from schemarouter.capability_contracts import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    UnitConversion,
)
from schemarouter.contract_validation import (
    CapabilityObservation,
    validate_capability_inputs,
    validate_capability_outputs,
)


def field(
    semantic_id: str,
    *,
    type_: str | None = "number",
    unit: str | None = None,
    dimension: str | None = None,
    qualifiers: dict[str, str] | None = None,
) -> CapabilityFieldContract:
    schema = {} if type_ is None else {"type": type_}
    return CapabilityFieldContract(
        semantic_id=semantic_id,
        json_schema=schema,
        unit=unit,
        dimension=dimension,
        qualifiers=qualifiers or {},
    )


def test_input_validation_accepts_exact_typed_state() -> None:
    capability = CapabilityContract(
        capability_id="materials.lookup",
        requires=[field("resource.material_id", type_="string")],
    )
    result = validate_capability_inputs(
        capability,
        [CapabilityObservation(contract=field("resource.material_id", type_="string"))],
    )
    assert result.status == "valid"
    assert result.valid is True


def test_input_validation_distinguishes_missing_and_incompatible() -> None:
    capability = CapabilityContract(
        capability_id="materials.lookup",
        requires=[field("resource.material_id", type_="string")],
    )
    missing = validate_capability_inputs(capability, [])
    incompatible = validate_capability_inputs(
        capability,
        [CapabilityObservation(contract=field("resource.material_id", type_="number"))],
    )
    assert missing.status == "missing"
    assert incompatible.status == "incompatible"
    assert incompatible.valid is False


def test_output_validation_marks_declared_unit_conversion_coercible() -> None:
    capability = CapabilityContract(
        capability_id="materials.band_gap",
        produces=[
            field(
                "electronic.band_gap",
                unit="eV",
                dimension="energy",
                qualifiers={"temperature": "300 K"},
            )
        ],
    )
    context = CompatibilityContext(
        unit_conversions=[
            UnitConversion(dimension="energy", from_unit="meV", to_unit="eV")
        ]
    )
    result = validate_capability_outputs(
        capability,
        [
            CapabilityObservation(
                contract=field(
                    "electronic.band_gap",
                    unit="meV",
                    dimension="energy",
                    qualifiers={"temperature": "300 K"},
                )
            )
        ],
        context=context,
    )
    assert result.status == "coercible"
    assert result.valid is True


def test_output_validation_fails_closed_on_qualifier_mismatch() -> None:
    capability = CapabilityContract(
        capability_id="materials.modulus",
        produces=[
            field(
                "mechanical.elastic_modulus",
                unit="GPa",
                dimension="pressure",
                qualifiers={"temperature": "300 K"},
            )
        ],
    )
    result = validate_capability_outputs(
        capability,
        [
            CapabilityObservation(
                contract=field(
                    "mechanical.elastic_modulus",
                    unit="GPa",
                    dimension="pressure",
                    qualifiers={"temperature": "600 K"},
                )
            )
        ],
    )
    assert result.status == "incompatible"


def test_output_validation_is_unverifiable_when_type_metadata_is_absent() -> None:
    capability = CapabilityContract(
        capability_id="mcp.abstract",
        produces=[field("document.abstract", type_="string")],
    )
    result = validate_capability_outputs(
        capability,
        [CapabilityObservation(contract=field("document.abstract", type_=None))],
    )
    assert result.status == "unverifiable"
    assert result.valid is False


def test_capability_without_optional_contract_metadata_remains_valid() -> None:
    capability = CapabilityContract(capability_id="legacy.route")
    assert validate_capability_inputs(capability, []).status == "valid"
    assert validate_capability_outputs(capability, []).status == "valid"
