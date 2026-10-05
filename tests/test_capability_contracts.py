from __future__ import annotations

from schemarouter import (
    CapabilityContract,
    CapabilityFieldContract,
    CompatibilityContext,
    FieldSpec,
    SemanticEquivalence,
    UnitConversion,
    UnitNormalizationSpec,
    compare_capability_composition,
    compare_capability_fields,
)


def contract(semantic_id: str, **kwargs) -> CapabilityFieldContract:
    return CapabilityFieldContract(semantic_id=semantic_id, **kwargs)


def test_exact_contract_is_satisfied() -> None:
    required = contract(
        "elastic_modulus",
        json_schema={"type": "number"},
        unit="Pa",
        dimension="pressure",
        qualifiers={"temperature": "300 K"},
    )
    result = compare_capability_fields(required, required)
    assert result.status == "exact"
    assert result.satisfies


def test_integer_output_satisfies_number_requirement() -> None:
    result = compare_capability_fields(
        contract("sample_count", json_schema={"type": "number"}),
        contract("sample_count", json_schema={"type": "integer"}),
    )
    assert result.status == "compatible"
    assert result.satisfies


def test_semantic_identity_is_not_inferred_from_similar_names() -> None:
    result = compare_capability_fields(
        contract("material.band_gap", json_schema={"type": "number"}),
        contract("material.bandgap", json_schema={"type": "number"}),
    )
    assert result.status == "incompatible"
    assert [reason.code for reason in result.reasons] == ["semantic_id_mismatch"]


def test_unit_dimension_and_qualifier_mismatch_fail_closed() -> None:
    result = compare_capability_fields(
        contract(
            "elastic_modulus",
            json_schema={"type": "number"},
            unit="Pa",
            dimension="pressure",
            qualifiers={"temperature": "300 K"},
        ),
        contract(
            "elastic_modulus",
            json_schema={"type": "number"},
            unit="m",
            dimension="length",
            qualifiers={"temperature": "500 K"},
        ),
    )
    assert result.status == "incompatible"
    assert {reason.code for reason in result.reasons} == {
        "unit_incompatible",
        "dimension_incompatible",
        "qualifier_mismatch",
    }


def test_missing_required_metadata_is_unknown_not_compatible() -> None:
    result = compare_capability_fields(
        contract("elastic_modulus", json_schema={"type": "number"}, unit="Pa"),
        contract("elastic_modulus"),
    )
    assert result.status == "unknown"
    assert not result.satisfies
    assert result.reasons[0].code == "metadata_incomplete"


def test_field_contract_uses_declared_canonical_unit() -> None:
    field = FieldSpec(
        name="elastic_modulus",
        semantic_id="elastic_modulus",
        json_schema={"type": "number"},
        unit="GPa",
        unit_normalization=UnitNormalizationSpec(
            dimension="pressure",
            canonical_unit="Pa",
            scale=1e9,
        ),
        qualifiers={"temperature": "300 K"},
    )
    converted = CapabilityFieldContract.from_field(field)
    assert converted is not None
    assert converted.unit == "Pa"
    assert converted.dimension == "pressure"
    assert converted.qualifiers == {"temperature": "300 K"}


def test_unitless_text_contract_remains_valid() -> None:
    field = FieldSpec(
        name="abstract",
        semantic_id="document_text",
        json_schema={"type": "string"},
        qualifiers={"language": "en"},
    )
    converted = CapabilityFieldContract.from_field(field)
    assert converted is not None
    assert converted.unit is None
    assert converted.dimension is None


def test_semantic_alias_requires_explicit_equivalence() -> None:
    required = contract("material.band_gap", json_schema={"type": "number"})
    produced = contract("material.bandgap", json_schema={"type": "number"})
    context = CompatibilityContext(
        semantic_equivalences=[
            SemanticEquivalence(
                canonical_id="material.band_gap",
                aliases={"material.bandgap"},
            )
        ]
    )
    result = compare_capability_fields(required, produced, context=context)
    assert result.status == "compatible"
    assert result.reasons[0].code == "semantic_equivalence_declared"


def test_unit_conversion_requires_explicit_directed_relation() -> None:
    required = contract(
        "elastic_modulus",
        json_schema={"type": "number"},
        unit="Pa",
        dimension="pressure",
    )
    produced = contract(
        "elastic_modulus",
        json_schema={"type": "number"},
        unit="GPa",
        dimension="pressure",
    )
    context = CompatibilityContext(
        unit_conversions=[
            UnitConversion(dimension="pressure", from_unit="GPa", to_unit="Pa")
        ]
    )
    result = compare_capability_fields(required, produced, context=context)
    assert result.status == "convertible"
    assert result.satisfies
    assert result.reasons[0].code == "conversion_declared"


def test_composition_requires_every_consumer_requirement() -> None:
    producer = CapabilityContract(
        capability_id="find_material",
        produces=[
            contract("resource.material_id", json_schema={"type": "string"}),
            contract("material.band_gap", json_schema={"type": "number"}, unit="eV"),
        ],
    )
    consumer = CapabilityContract(
        capability_id="get_structure",
        requires=[
            contract("resource.material_id", json_schema={"type": "string"}),
            contract("auth.scope", json_schema={"type": "string"}),
        ],
    )
    result = compare_capability_composition(producer, consumer)
    assert result.status == "incompatible"
    assert result.requirements["resource.material_id"].status == "exact"
    assert result.requirements["auth.scope"].reasons[0].code == "missing_requirement"


def test_composition_can_be_convertible_without_executing_conversion() -> None:
    producer = CapabilityContract(
        capability_id="get_elasticity_gpa",
        produces=[
            contract(
                "elastic_modulus",
                json_schema={"type": "number"},
                unit="GPa",
                dimension="pressure",
            )
        ],
    )
    consumer = CapabilityContract(
        capability_id="consume_elasticity_pa",
        requires=[
            contract(
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
    result = compare_capability_composition(producer, consumer, context=context)
    assert result.status == "convertible"
    assert result.satisfies


def test_composition_preserves_duplicate_semantic_requirements_deterministically() -> None:
    producer = CapabilityContract(
        capability_id="producer",
        produces=[
            CapabilityFieldContract(
                semantic_id="temperature",
                json_schema={"type": "number"},
                unit="C",
                dimension="temperature",
                qualifiers={"location": "surface"},
            )
        ],
    )
    requirements = [
        CapabilityFieldContract(
            semantic_id="temperature",
            json_schema={"type": "number"},
            unit="C",
            dimension="temperature",
            qualifiers={"location": "surface"},
        ),
        CapabilityFieldContract(
            semantic_id="temperature",
            json_schema={"type": "number"},
            unit="K",
            dimension="temperature",
            qualifiers={"location": "core"},
        ),
    ]

    forward = compare_capability_composition(
        producer,
        CapabilityContract(
            capability_id="consumer-forward",
            requires=requirements,
        ),
    )
    reverse = compare_capability_composition(
        producer,
        CapabilityContract(
            capability_id="consumer-reverse",
            requires=list(reversed(requirements)),
        ),
    )

    assert forward.status == "incompatible"
    assert reverse.status == "incompatible"
    assert len(forward.requirements) == 2
    assert list(forward.requirements) == list(reverse.requirements)
    assert [
        result.status for result in forward.requirements.values()
    ] == [
        result.status for result in reverse.requirements.values()
    ]


def test_composition_preserves_identical_duplicate_requirement_multiplicity() -> None:
    required = CapabilityFieldContract(
        semantic_id="temperature",
        json_schema={"type": "number"},
    )
    producer = CapabilityContract(
        capability_id="producer",
        produces=[required],
    )
    consumer = CapabilityContract(
        capability_id="consumer",
        requires=[required, required.model_copy(deep=True)],
    )

    result = compare_capability_composition(producer, consumer)

    assert result.status == "exact"
    assert len(result.requirements) == 2
    assert all(
        item.status == "exact"
        for item in result.requirements.values()
    )
