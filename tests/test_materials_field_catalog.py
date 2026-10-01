from __future__ import annotations

from schemarouter.adapters.openapi import tool_from_openapi


def test_large_materials_style_catalog_is_deterministic_and_complete() -> None:
    declared_properties = {
    "property_01": {
        "type": "number",
        "description": "Synthetic material property 1",
        "x-ucum-unit": "eV"
    },
    "property_02": {
        "type": "number",
        "description": "Synthetic material property 2",
        "x-ucum-unit": "eV"
    },
    "property_03": {
        "type": "number",
        "description": "Synthetic material property 3",
        "x-ucum-unit": "eV"
    },
    "property_04": {
        "type": "number",
        "description": "Synthetic material property 4",
        "x-ucum-unit": "eV"
    },
    "property_05": {
        "type": "number",
        "description": "Synthetic material property 5",
        "x-ucum-unit": "eV"
    },
    "property_06": {
        "type": "number",
        "description": "Synthetic material property 6",
        "x-ucum-unit": "eV"
    },
    "property_07": {
        "type": "number",
        "description": "Synthetic material property 7",
        "x-ucum-unit": "eV"
    },
    "property_08": {
        "type": "number",
        "description": "Synthetic material property 8",
        "x-ucum-unit": "eV"
    },
    "property_09": {
        "type": "number",
        "description": "Synthetic material property 9",
        "x-ucum-unit": "eV"
    },
    "property_10": {
        "type": "number",
        "description": "Synthetic material property 10",
        "x-ucum-unit": "eV"
    },
    "property_11": {
        "type": "number",
        "description": "Synthetic material property 11",
        "x-ucum-unit": "eV"
    },
    "property_12": {
        "type": "number",
        "description": "Synthetic material property 12",
        "x-ucum-unit": "eV"
    },
    "property_13": {
        "type": "number",
        "description": "Synthetic material property 13",
        "x-ucum-unit": "eV"
    },
    "property_14": {
        "type": "number",
        "description": "Synthetic material property 14",
        "x-ucum-unit": "eV"
    },
    "property_15": {
        "type": "number",
        "description": "Synthetic material property 15",
        "x-ucum-unit": "eV"
    },
    "property_16": {
        "type": "number",
        "description": "Synthetic material property 16",
        "x-ucum-unit": "eV"
    },
    "property_17": {
        "type": "number",
        "description": "Synthetic material property 17",
        "x-ucum-unit": "eV"
    },
    "property_18": {
        "type": "number",
        "description": "Synthetic material property 18",
        "x-ucum-unit": "eV"
    },
    "property_19": {
        "type": "number",
        "description": "Synthetic material property 19",
        "x-ucum-unit": "eV"
    },
    "property_20": {
        "type": "number",
        "description": "Synthetic material property 20",
        "x-ucum-unit": "eV"
    },
    "property_21": {
        "type": "number",
        "description": "Synthetic material property 21",
        "x-ucum-unit": "eV"
    },
    "property_22": {
        "type": "number",
        "description": "Synthetic material property 22",
        "x-ucum-unit": "eV"
    },
    "property_23": {
        "type": "number",
        "description": "Synthetic material property 23",
        "x-ucum-unit": "eV"
    },
    "property_24": {
        "type": "number",
        "description": "Synthetic material property 24",
        "x-ucum-unit": "eV"
    },
    "property_25": {
        "type": "number",
        "description": "Synthetic material property 25",
        "x-ucum-unit": "eV"
    },
    "property_26": {
        "type": "number",
        "description": "Synthetic material property 26",
        "x-ucum-unit": "eV"
    },
    "property_27": {
        "type": "number",
        "description": "Synthetic material property 27",
        "x-ucum-unit": "eV"
    },
    "property_28": {
        "type": "number",
        "description": "Synthetic material property 28",
        "x-ucum-unit": "eV"
    },
    "property_29": {
        "type": "number",
        "description": "Synthetic material property 29",
        "x-ucum-unit": "eV"
    },
    "property_30": {
        "type": "number",
        "description": "Synthetic material property 30",
        "x-ucum-unit": "eV"
    },
    "property_31": {
        "type": "number",
        "description": "Synthetic material property 31",
        "x-ucum-unit": "eV"
    },
    "property_32": {
        "type": "number",
        "description": "Synthetic material property 32",
        "x-ucum-unit": "eV"
    },
    "property_33": {
        "type": "number",
        "description": "Synthetic material property 33",
        "x-ucum-unit": "eV"
    },
    "property_34": {
        "type": "number",
        "description": "Synthetic material property 34",
        "x-ucum-unit": "eV"
    },
    "property_35": {
        "type": "number",
        "description": "Synthetic material property 35",
        "x-ucum-unit": "eV"
    },
    "property_36": {
        "type": "number",
        "description": "Synthetic material property 36",
        "x-ucum-unit": "eV"
    },
    "property_37": {
        "type": "number",
        "description": "Synthetic material property 37",
        "x-ucum-unit": "eV"
    },
    "property_38": {
        "type": "number",
        "description": "Synthetic material property 38",
        "x-ucum-unit": "eV"
    },
    "property_39": {
        "type": "number",
        "description": "Synthetic material property 39",
        "x-ucum-unit": "eV"
    },
    "property_40": {
        "type": "number",
        "description": "Synthetic material property 40",
        "x-ucum-unit": "eV"
    }
}
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Large materials API", "version": "1.0.0"},
        "paths": {
            "/materials": {
                "get": {
                    "operationId": "search_materials",
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "data": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": declared_properties,
                                                },
                                            },
                                            "meta": {"type": "object"},
                                        },
                                    }
                                }
                            },
                        }
                    },
                }
            }
        },
    }

    first = tool_from_openapi("materials", document)
    second = tool_from_openapi("materials", document)
    first_endpoint = first.endpoint("search_materials")
    second_endpoint = second.endpoint("search_materials")

    first_fields = {
        field.name: field
        for field in first_endpoint.output_fields
    }
    second_names = [
        field.name
        for field in second_endpoint.output_fields
    ]

    expected = {
        f"data[].property_{index:02d}"
        for index in range(1, 41)
    }
    assert expected <= set(first_fields)
    assert len(expected) == 40
    assert [
        field.name
        for field in first_endpoint.output_fields
    ] == second_names
    assert first_endpoint.fingerprint == second_endpoint.fingerprint

    sample = first_fields["data[].property_17"]
    assert sample.path == ["data", "*", "property_17"]
    assert sample.result_path == ["data", "*", "property_17"]
    assert sample.unit == "eV"
    assert sample.json_schema["type"] == "number"
