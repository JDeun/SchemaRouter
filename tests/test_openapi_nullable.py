import pytest

from schemarouter import SchemaValidationError, analyze_openapi_compatibility
from schemarouter.adapters.openapi import tool_from_openapi
from schemarouter.validation import validate_json_schema_value


def test_openapi30_nullable_response_property_becomes_json_schema_union() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Nullable Response"},
        "paths": {
            "/user": {
                "get": {
                    "operationId": "get_user",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/User"
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "middle_name": {
                            "type": "string",
                            "nullable": True,
                        }
                    },
                    "required": ["middle_name"],
                }
            }
        },
    }

    tool = tool_from_openapi("nullable", document)
    endpoint = tool.endpoint("get_user")
    field = endpoint.output_fields[0]

    assert field.name == "middle_name"
    assert field.json_schema["type"] == ["string", "null"]
    assert "nullable" not in field.json_schema
    assert tool.metadata["openapi_30_nullable_normalized"] == 1

    validate_json_schema_value(
        {"middle_name": None},
        endpoint.output_schema,
        context="nullable response",
    )


def test_openapi30_nullable_request_property_accepts_json_null() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Nullable Request"},
        "paths": {
            "/user": {
                "post": {
                    "operationId": "create_user",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "nickname": {
                                            "type": "string",
                                            "nullable": True,
                                        }
                                    },
                                    "required": ["nickname"],
                                }
                            }
                        },
                    },
                    "responses": {"204": {"description": "created"}},
                }
            }
        },
    }

    endpoint = tool_from_openapi("nullable", document).endpoint("create_user")

    assert endpoint.parameters[0].json_schema["type"] == ["string", "null"]
    validate_json_schema_value(
        {"nickname": None},
        endpoint.input_schema,
        context="nullable request",
    )


def test_openapi30_nullable_keeps_other_constraints_authoritative() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Nullable Enum"},
        "paths": {
            "/state": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "string",
                                        "nullable": True,
                                        "enum": ["ready"],
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    endpoint = tool_from_openapi("nullable", document).endpoints[0]

    with pytest.raises(SchemaValidationError):
        validate_json_schema_value(
            None,
            endpoint.output_schema,
            context="nullable enum",
        )


def test_openapi30_nullable_without_same_object_type_is_not_rewritten() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Nullable Without Type"},
        "paths": {
            "/value": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "nullable": True,
                                        "enum": ["x", None],
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    tool = tool_from_openapi("nullable", document)
    endpoint = tool.endpoints[0]

    assert endpoint.output_schema["nullable"] is True
    assert "type" not in endpoint.output_schema
    assert tool.metadata["openapi_30_nullable_normalized"] == 0


def test_openapi31_legacy_nullable_keyword_is_not_rewritten() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "OAS31"},
        "paths": {
            "/value": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "string",
                                        "nullable": True,
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    tool = tool_from_openapi("oas31", document)
    endpoint = tool.endpoints[0]

    assert endpoint.output_schema["type"] == "string"
    assert endpoint.output_schema["nullable"] is True
    assert tool.metadata["openapi_30_nullable_normalized"] == 0

    with pytest.raises(SchemaValidationError):
        validate_json_schema_value(
            None,
            endpoint.output_schema,
            context="OAS 3.1 legacy nullable",
        )


def test_openapi30_nullable_normalization_does_not_rewrite_examples() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Example Safety"},
        "paths": {
            "/value": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "value": {
                                                "type": "string",
                                                "nullable": True,
                                                "example": {
                                                    "type": "example-data",
                                                    "nullable": True,
                                                },
                                            }
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    endpoint = tool_from_openapi("examples", document).endpoints[0]
    field = endpoint.output_fields[0]

    assert field.json_schema["type"] == ["string", "null"]
    assert field.json_schema["example"] == {
        "type": "example-data",
        "nullable": True,
    }


def test_openapi30_nullable_inside_external_bundle_is_normalized() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "External Bundle"},
        "paths": {
            "/value": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": (
                                            "#/x-schemarouter-external-refs/"
                                            "doc0/User"
                                        )
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
        "x-schemarouter-external-refs": {
            "doc0": {
                "User": {
                    "type": "object",
                    "properties": {
                        "nickname": {
                            "type": "string",
                            "nullable": True,
                        }
                    },
                }
            }
        },
    }

    endpoint = tool_from_openapi("external", document).endpoints[0]

    assert endpoint.output_fields[0].json_schema["type"] == ["string", "null"]
    validate_json_schema_value(
        {"nickname": None},
        endpoint.output_schema,
        context="external nullable response",
    )


def test_openapi30_nullable_is_no_longer_reported_as_partial() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Nullable Compatibility"},
        "paths": {
            "/value": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "string",
                                        "nullable": True,
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    report = analyze_openapi_compatibility(document)

    assert not any(issue.schema_construct == "nullable" for issue in report.issues)
