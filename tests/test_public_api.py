import schemarouter


def test_public_framework_exports_are_intentional_and_stable() -> None:
    expected = {
        "__version__",
        "AdapterContext",
        "AdapterLoadResult",
        "AdapterRegistry",
        "BindingDriftError",
        "ConfiguredSchemaRouter",
        "EndpointSpec",
        "EvidenceRequirements",
        "ExecutionError",
        "ExecutionPlan",
        "ExecutionPolicy",
        "FieldSpec",
        "InMemoryRegistry",
        "KeywordAnalyzer",
        "ModelAnalysisError",
        "ModelCallable",
        "ModelQueryAnalyzer",
        "ParameterSpec",
        "PlanRequest",
        "PlanValidationError",
        "PlanningError",
        "PolicyViolationError",
        "ProposalApprovalError",
        "QueryAnalyzer",
        "QueryIntent",
        "RegistrationError",
        "RegistryExecutor",
        "RetryPolicy",
        "RunConfig",
        "RunEvent",
        "SchemaDriftError",
        "SchemaPlanner",
        "SchemaProposal",
        "SchemaRouter",
        "SchemaRouterError",
        "SchemaSourceError",
        "SchemaValidationError",
        "SourceAdapter",
        "OPTIMADESourceAdapter",
        "ToolCall",
        "ToolRegistry",
        "ToolResult",
        "ToolSpec",
        "UnsupportedSchemaSourceError",
        "schema_tool",
        "tool_from_callable",
    }

    assert set(schemarouter.__all__) == expected
    for name in expected:
        assert hasattr(schemarouter, name)


def test_internal_implementation_types_are_not_top_level_exports() -> None:
    internal = {
        "DocumentationModelCallable",
        "ModelIntent",
        "ProposalEndpoint",
        "ProposalField",
        "ProposalParameter",
        "PythonCallableInvoker",
        "SchemaProposalDraft",
        "inspect_documentation_url",
    }

    assert internal.isdisjoint(schemarouter.__all__)
