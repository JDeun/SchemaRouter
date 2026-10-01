from __future__ import annotations

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ServerProjectionSpec,
    UnitNormalizationSpec,
)
from schemarouter.errors import SchemaValidationError
from schemarouter.executor import RegistryExecutor
from schemarouter.validation import projected_output_schema


def _endpoint() -> EndpointSpec:
    return EndpointSpec(
        name="search",
        output_schema={
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "score": {"type": "number"},
                        },
                        "required": ["title"],
                    },
                }
            },
            "required": ["results"],
        },
        output_fields=[
            FieldSpec(
                name="results[].title",
                path=["results", "*", "title"],
                result_path=["results", "*", "title"],
                json_schema={"type": "string"},
            ),
            FieldSpec(
                name="results[].url",
                path=["results", "*", "url"],
                result_path=["results", "*", "url"],
                json_schema={"type": "string"},
            ),
            FieldSpec(
                name="results[].score",
                path=["results", "*", "score"],
                result_path=["results", "*", "score"],
                json_schema={"type": "number"},
                unit="meV",
                unit_normalization=UnitNormalizationSpec(
                    dimension="energy",
                    canonical_unit="eV",
                    scale=0.001,
                ),
            ),
        ],
        server_projection=ServerProjectionSpec(
            parameter="fields",
            field_map={
                "results[].title": "title",
                "results[].url": "url",
                "results[].score": "score",
            },
        ),
    )


def test_array_item_field_requires_record_preserving_result_path() -> None:
    with pytest.raises(ValueError, match="require an explicit result_path"):
        FieldSpec(
            name="results[].title",
            path=["results", "*", "title"],
            json_schema={"type": "string"},
        )

    with pytest.raises(ValueError, match="preserve wildcard positions"):
        FieldSpec(
            name="results[].title",
            path=["results", "*", "title"],
            result_path=["results", "title"],
            json_schema={"type": "string"},
        )


def test_array_item_projection_merges_children_by_record_index() -> None:
    endpoint = _endpoint()
    raw = {
        "results": [
            {
                "title": "A",
                "url": "https://a.example",
                "score": 1000.0,
            },
            {
                "title": "B",
                "score": 2500.0,
            },
        ]
    }

    projected = RegistryExecutor._project(
        raw,
        ["results[].title", "results[].url"],
        endpoint,
    )

    assert projected == {
        "results": [
            {
                "title": "A",
                "url": "https://a.example",
            },
            {
                "title": "B",
            },
        ]
    }


def test_array_item_unit_normalization_preserves_record_alignment() -> None:
    endpoint = _endpoint()
    raw = {
        "results": [
            {"score": 1000.0},
            {"score": 2500.0},
        ]
    }

    projected = RegistryExecutor._project(
        raw,
        ["results[].score"],
        endpoint,
    )
    normalized = RegistryExecutor._normalize_projected_units(
        projected,
        ["results[].score"],
        endpoint,
    )

    assert normalized == {
        "results": [
            {"score": 1.0},
            {"score": 2.5},
        ]
    }


def test_array_item_selected_schema_validation_checks_each_present_record() -> None:
    endpoint = _endpoint()
    raw = {
        "results": [
            {"title": "A"},
            {"title": 123},
        ]
    }

    with pytest.raises(SchemaValidationError, match="array item 1"):
        RegistryExecutor._validate_selected_field_schemas(
            raw,
            ["results[].title"],
            endpoint,
            context="output",
        )


def test_array_item_presence_allows_optional_child_missing_in_some_records() -> None:
    endpoint = _endpoint()
    raw = {
        "results": [
            {"url": "https://a.example"},
            {},
        ]
    }

    RegistryExecutor._validate_selected_fields_present(
        raw,
        ["results[].url"],
        endpoint,
        context="output",
    )


def test_projected_output_schema_narrows_nested_array_items() -> None:
    endpoint = _endpoint()

    schema = projected_output_schema(
        endpoint,
        ["results[].title", "results[].url"],
    )

    results = schema["properties"]["results"]
    assert set(results["items"]["properties"]) == {"title", "url"}
    assert results["items"]["required"] == ["title"]
    assert schema["required"] == ["results"]
