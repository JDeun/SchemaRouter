import schemarouter


def test_documented_framework_exports_remain_public() -> None:
    expected = {
        "SchemaRouter",
        "ConfiguredSchemaRouter",
        "ToolRegistry",
        "InMemoryRegistry",
        "ToolSpec",
        "EndpointSpec",
        "ParameterSpec",
        "FieldSpec",
        "PlanRequest",
        "ExecutionPlan",
        "ToolResult",
        "ExecutionPolicy",
        "RunConfig",
        "RetryPolicy",
        "RunEvent",
        "schema_tool",
        "tool_from_callable",
        "__version__",
    }

    assert expected <= set(schemarouter.__all__)
    for name in expected:
        assert hasattr(schemarouter, name)
