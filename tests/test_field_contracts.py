from __future__ import annotations

import pytest

from schemarouter import EndpointSpec, FieldSpec


def test_text_field_has_string_type_and_optional_unit_none() -> None:
    field = FieldSpec(
        name="abstract",
        semantic_id="abstract_text",
        json_schema={"type": "string"},
        unit=None,
    )

    assert field.declared_json_types == ("string",)
    assert field.unit is None
    assert field.normalized_unit is None


def test_nullable_numeric_field_reports_number_and_null_types() -> None:
    field = FieldSpec(
        name="elastic_modulus",
        json_schema={
            "anyOf": [
                {"type": "number"},
                {"type": "null"},
            ]
        },
        unit="GPa",
    )

    assert field.declared_json_types == ("null", "number")
    assert field.normalized_unit == "GPa"


def test_unit_normalization_preserves_scientific_case() -> None:
    upper = FieldSpec(
        name="pressure",
        json_schema={"type": "number"},
        unit="  GPa  ",
    )
    lower = FieldSpec(
        name="current",
        json_schema={"type": "number"},
        unit=" pA ",
    )

    assert upper.normalized_unit == "GPa"
    assert lower.normalized_unit == "pA"


def test_empty_unit_is_rejected_but_none_is_allowed() -> None:
    FieldSpec(name="abstract", json_schema={"type": "string"}, unit=None)

    with pytest.raises(ValueError, match="unit must be non-empty"):
        FieldSpec(name="bad", json_schema={"type": "number"}, unit="   ")


def test_endpoint_rejects_field_type_disagreement_with_raw_output_schema() -> None:
    with pytest.raises(ValueError, match="json_schema type disagrees"):
        EndpointSpec(
            name="search",
            read_only=True,
            output_fields=[
                FieldSpec(
                    name="elastic_modulus",
                    json_schema={"type": "number"},
                    unit="GPa",
                )
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "elastic_modulus": {"type": "string"},
                },
            },
        )


def test_nested_field_type_matches_raw_output_schema() -> None:
    endpoint = EndpointSpec(
        name="search",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="elastic_modulus",
                path=["elasticity", "bulk_modulus"],
                result_path=["elastic_modulus"],
                json_schema={"type": "number"},
                unit="GPa",
            )
        ],
        output_schema={
            "type": "object",
            "properties": {
                "elasticity": {
                    "type": "object",
                    "properties": {
                        "bulk_modulus": {"type": "number"},
                    },
                },
            },
        },
    )

    assert endpoint.output_fields[0].declared_json_types == ("number",)


def test_root_array_field_type_matches_item_schema() -> None:
    endpoint = EndpointSpec(
        name="search",
        read_only=True,
        output_fields=[
            FieldSpec(
                name="title",
                json_schema={"type": "string"},
                unit=None,
            )
        ],
        output_schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                },
            },
        },
    )

    assert endpoint.output_fields[0].declared_json_types == ("string",)
