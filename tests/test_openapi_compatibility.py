from schemarouter import analyze_openapi_compatibility
from schemarouter.adapters import tool_from_openapi


def test_openapi_compatibility_reports_supported_common_subset() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Simple"},
        "paths": {
            "/items": {
                "get": {
                    "operationId": "list_items",
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
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

    assert report.status == "supported"
    assert report.operations_total == 1
    assert report.operations_importable == 1
    assert report.issues == []


def test_openapi_compatibility_makes_unsupported_semantics_visible() -> None:
    document = {
        "openapi": "3.0.4",
        "info": {"title": "Mixed"},
        "paths": {
            "/items": {
                "post": {
                    "operationId": "create_item",
                    "parameters": [
                        {
                            "name": "session",
                            "in": "cookie",
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "content": {
                            "text/plain": {"schema": {"type": "string"}},
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "https://example.com/item.json"},
                                }
                            },
                        }
                    },
                    "responses": {
                        "200": {
                            "content": {
                                "application/xml": {"schema": {"type": "object"}},
                                "application/json": {
                                    "schema": {
                                        "oneOf": [
                                            {"type": "object"},
                                            {"type": "array"},
                                        ]
                                    }
                                },
                            }
                        }
                    },
                    "security": [{"bearerAuth": []}],
                }
            }
        },
    }

    report = analyze_openapi_compatibility(document)
    constructs = {issue.schema_construct: issue.support for issue in report.issues}

    assert report.status == "partial"
    assert constructs["external_ref"] == "unsupported"
    assert constructs["cookie_parameter"] == "unsupported"
    assert constructs["multiple_request_content_types"] == "partial"
    assert "non_object_request_body" not in constructs
    assert constructs["oneOf"] == "partial"
    assert constructs["multiple_response_content_types"] == "partial"
    assert constructs["security_requirements"] == "partial"


def test_openapi_compatibility_scans_every_success_response() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Multi Response"},
        "paths": {
            "/items": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "json",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        },
                        "201": {
                            "description": "text",
                            "content": {
                                "text/plain": {
                                    "schema": {"type": "string"}
                                }
                            },
                        },
                    }
                }
            }
        },
    }

    report = analyze_openapi_compatibility(document)

    assert any(
        issue.schema_construct == "non_json_response"
        and "/responses/201/" in issue.location
        for issue in report.issues
    )


def test_openapi_compatibility_reports_schema_less_json_request_body() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Schema-less Body"},
        "paths": {
            "/items": {
                "post": {
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {}},
                    },
                    "responses": {"204": {"description": "ok"}},
                }
            }
        },
    }

    report = analyze_openapi_compatibility(document)

    assert report.status == "partial"
    assert any(
        issue.schema_construct == "schema_less_request_body"
        and issue.support == "unsupported"
        for issue in report.issues
    )


def test_openapi_compatibility_detects_recursive_component_refs() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Tree"},
        "paths": {
            "/tree": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Node"}
                                }
                            }
                        }
                    }
                }
            }
        },
        "components": {
            "schemas": {
                "Node": {
                    "type": "object",
                    "properties": {
                        "children": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/Node"},
                        }
                    },
                }
            }
        },
    }

    report = analyze_openapi_compatibility(document)

    assert any(issue.schema_construct == "recursive_ref" for issue in report.issues)


def test_openapi_import_attaches_machine_readable_compatibility_report() -> None:
    document = {
        "openapi": "3.1.0",
        "info": {"title": "Simple"},
        "paths": {"/health": {"get": {"responses": {"204": {"description": "ok"}}}}},
    }

    tool = tool_from_openapi("simple", document)

    report = tool.metadata["compatibility"]
    assert report["status"] == "supported"
    assert report["operations_total"] == 1
    assert report["operations_importable"] == 1


def test_openapi_compatibility_accepts_explicit_scalar_and_array_json_bodies() -> None:
    for schema in (
        {"type": "string"},
        {"type": "array", "items": {"type": "integer"}},
    ):
        document = {
            "openapi": "3.1.0",
            "info": {"title": "Root Body"},
            "paths": {
                "/submit": {
                    "post": {
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {
                                    "schema": schema,
                                }
                            },
                        },
                        "responses": {"204": {"description": "ok"}},
                    }
                }
            },
        }

        report = analyze_openapi_compatibility(document)

        assert not any(
            issue.schema_construct == "non_object_request_body"
            for issue in report.issues
        )
