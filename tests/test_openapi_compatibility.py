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
    constructs = {issue.construct: issue.support for issue in report.issues}

    assert report.status == "partial"
    assert constructs["external_ref"] == "unsupported"
    assert constructs["cookie_parameter"] == "unsupported"
    assert constructs["multiple_request_content_types"] == "partial"
    assert constructs["non_object_request_body"] == "unsupported"
    assert constructs["oneOf"] == "partial"
    assert constructs["multiple_response_content_types"] == "partial"
    assert constructs["security_requirements"] == "partial"


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

    assert any(issue.construct == "recursive_ref" for issue in report.issues)


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
