import subprocess
import sys

import schemarouter


def test_public_framework_exports_are_intentional_and_stable() -> None:
    expected = {
        "__version__",
        "HostSemanticAttestation",
        "HostSemanticMapping",
        "apply_host_semantic_attestation",
        "CrossrefPaperSourceProbe",
        "inspect_crossref_paper_source",
        "register_reviewed_crossref_paper_source",
        "DeepWikiPaperSourceProbe",
        "inspect_deepwiki_paper_source",
        "register_reviewed_deepwiki_paper_source",
        "EuropePMCPaperSourceProbe",
        "inspect_europepmc_paper_source",
        "register_reviewed_europepmc_paper_source",
        "AggregatedField",
        "CanonicalEntity",
        "CapabilityCompatibility",
        "CapabilityDependencyEdge",
        "CapabilityDependencyGraph",
        "CapabilityComposition",
        "CapabilityContract",
        "CapabilityGraphArtifact",
        "CapabilityContractValidation",
        "CapabilityObservation",
        "ContractFieldValidation",
        "ContractValidationStatus",
        "CapabilityFieldContract",
        "CompatibilityContext",
        "CompatibilityReason",
        "CompatibilityStatus",
        "SemanticEquivalence",
        "UnitConversion",
        "CapabilityExplorerDocument",
        "ExplorerAuthScheme",
        "ExplorerEndpoint",
        "ExplorerEndpointStatus",
        "ExplorerField",
        "ExplorerParameter",
        "ExplorerProjection",
        "ExplorerTool",
        "ExplorerUnitNormalization",
        "ExplorerWatchStatus",
        "DeclaredOperationFitPolicy",
        "NativeDeclaredFieldGroup",
        "NativeConceptCatalog",
        "NativeDeclaredConcept",
        "ResolvedNativeConcepts",
        "resolve_native_concepts",
        "NativeConceptGraphSelection",
        "NativeConceptRouteSet",
        "retrieve_authorized_concept_graph",
        "PaperFieldRoute",
        "PaperFieldAlternative",
        "PaperFieldCoverage",
        "retrieve_paper_field_coverage",
        "SchemaFieldRoutingSession",
        "SchemaFieldReviewField",
        "SchemaFieldReviewRoute",
        "SchemaFieldReviewPage",
        "PaperObservedBinding",
        "observe_and_bind_paper_plan",
        "PaperExecutedToolSequence",
        "observe_and_execute_paper_plan",
            "PaperUnderstoodExecutedGraph",
            "observe_and_execute_paper_understood_graph",
        "PaperPlanBinding",
        "PaperPlanCall",
        "PaperPlanFieldMeta",
        "PaperPlanParameterMeta",
        "PaperTypedToolPlan",
        "PaperNativeRankPolicy",
        "compile_paper_typed_tool_plan",
        "PaperIntentDeclaration",
        "PaperIntentRegistry",
        "PaperUnderstanding",
        "PaperQueryNeed",
        "PaperQueryUnderstanding",
            "discover_optimade_paper_source",
            "register_reviewed_optimade_paper_source",
        "NativeIndexedGraphCandidate",
        "NativeIndexedGraphResult",
        "NativeSchemaGraphIndex",
        "IndexedNativeFieldCandidate",
        "IndexedNativeFieldResult",
        "NativeSchemaPostingIndex",
        "validate_declared_operation_fit",
        "FieldObservation",
        "RetrievalMode",
        "SourceRecord",
        "aggregate_records",
        "canonical_identity",
        "AccessHealthMonitor",
        "CAPABILITY_ARTIFACT_FORMAT_VERSION",
        "ArtifactSourceKind",
        "CapabilityArtifactEdge",
        "CapabilityArtifactSource",
        "ADAPTER_ENTRY_POINT_GROUP",
        "AdapterContext",
        "AdapterLoadResult",
        "AdapterPluginInfo",
        "AdapterRegistry",
        "AfterExecutionHook",
        "ApprovalCallback",
        "AuthorizationAuditDeliveryError",
        "AuthorizationAuditDeliveryMode",
        "AuthorizationAuditDeliveryStatus",
        "AuthorizationDecision",
        "AuthorizationEffect",
        "AuthorizationPolicy",
        "AuthorizationRule",
        "DataScopeDecision",
        "DataScopeRule",
        "BeforeExecutionHook",
        "ApprovalDeniedError",
        "AuthRequirementSet",
        "AuthSchemeRequirement",
        "BindingDriftError",
        "BindingReconciliationError",
        "BindingReconciliationItem",
        "BindingReconciliationReport",
        "BindingReconciliationStatus",
        "BindingResolver",
        "ConfiguredSchemaRouter",
        "ContractAmendmentError",
        "DiscoveryProfile",
        "E5CachedEmbedder",
        "DefaultMCPClientFactory",
        "EligibilityStatus",
        "EndpointSpec",
        "EvidenceContract",
        "EvidenceContractError",
        "EvidenceLedgerEntry",
        "EvidenceRequirements",
        "ExecutionBudget",
        "ExecutionStatus",
        "ExecutionBudgetExceededError",
        "ExecutionError",
        "ExecutionHookError",
        "ExecutionInvariantError",
        "IndeterminateInvocationError",
        "InvocationUnavailableError",
        "ExecutionMode",
        "ExecutionHooks",
        "HealthProbe",
        "HealthProbeSnapshot",
        "HealthProbeInspection",
        "HealthStatus",
        "ExecutionPlan",
        "FallbackRoute",
        "FallbackScope",
        "ExecutionPolicy",
        "FieldInspection",
        "FieldSelectionExplanation",
        "FieldSpec",
        "InMemoryRegistry",
        "EndpointInspection",
        "ExecutionInspection",
        "PlannerInspection",
        "RegistryInspection",
        "RouterInspection",
        "ToolInspection",
        "TraceInspection",
        "TraceRedactionConfig",
        "TrustedBindingConfig",
        "MCPBoundClientFactory",
        "MCPClientFactory",
        "MCPDiscoveryLimits",
        "NativeDiscoveryLimits",
        "MCPStdioConfig",
        "ModelAnalysisError",
        "NetworkPolicy",
        "NetworkPolicyError",
        "MutableToolRegistry",
        "NonRetryableInvocationError",
        "ObservedStateField",
        "OpenAPICompatibilityIssue",
        "OpenAPICompatibilityReport",
        "ParameterSpec",
        "PlanCoverage",
        "PlanExplanation",
        "PaperPlanRequest",
        "PlanValidationError",
        "PlanningError",
        "PolicyViolationError",
        "PostInvocationHookError",
        "PolicyDecision",
        "PolicyEffect",
        "PolicyRule",
        "ProposalApprovalError",
        "PROVIDER_PROFILE_ENTRY_POINT_GROUP",
        "ProviderAccessMethod",
        "ProviderDiscoveryBackend",
        "ProviderDiscoveryCandidate",
        "ProviderDiscoveryProposal",
        "PrincipalContext",
        "TrustedFilterBinding",
        "ProviderMethodRegistration",
        "ProviderMethodResolution",
        "ProviderProfile",
        "ProviderProfilePluginInfo",
        "ProviderProfileRegistry",
        "ProviderRegistrationResult",
        "ProviderResolution",
        "built_in_provider_profile_registry",
        "discover_provider_profile_plugins",
        "load_provider_profile_plugins",
        "QueryIntent",
        "ResultFieldContract",
        "ClickHouseRecordBackend",
        "CosmosRecordBackend",
        "CouchbaseRecordBackend",
        "DynamoDBRecordBackend",
        "ElasticRecordBackend",
        "InfluxRecordBackend",
        "MongoRecordBackend",
        "RecordFieldSpec",
        "RecordModel",
        "RecordSourceBinding",
        "RecordSourceInvoker",
        "RecordSourceSpec",
        "RecordStoreBackend",
            "RegistrationError",
        "RefreshProfile",
        "RegistryExecutor",
        "RetryPolicy",
        "RunConfig",
        "RunEvent",
        "RunTrace",
        "RunTraceStore",
        "TracePruneResult",
        "TraceRetentionPolicy",
        "SchemaDriftError",
        "StaleExportedToolError",
        "SchemaChange",
        "SchemaChangeSeverity",
        "SchemaCompatibility",
        "SchemaDiffReport",
        "SchemaProposal",
        "ArangoGraphBackend",
        "FalkorGraphBackend",
        "GraphModel",
        "GraphNodeTypeSpec",
        "GraphPropertySpec",
        "GraphRelationshipTypeSpec",
        "GraphSourceBinding",
        "GraphSourceInvoker",
        "GraphSourceSpec",
        "GraphStoreBackend",
        "ScopedGraphStoreBackend",
        "Neo4jGraphBackend",
        "NeptuneOpenCypherBackend",
        "SparqlGraphBackend",
        "SchemaRouter",
        "SchemaRouterError",
        "SchemaSourceError",
        "SQLiteRegistry",
        "SQLiteRunTraceStore",
        "SQLiteTableBinding",
        "SQLiteTableInvoker",
        "SQLAlchemyTableBinding",
        "SQLAlchemyTableInvoker",
        "SchemaValidationError",
        "StateEligibility",
        "StateEligibilityReason",
        "StorageFormatError",
        "StorageComponent",
        "StorageComponentInspection",
        "StorageInspection",
        "StorageMigrationRecord",
        "StorageMigrationResult",
        "StorageStatus",
        "PersistedDocumentLimits",
        "CURRENT_STORAGE_FORMAT_VERSION",
        "CURRENT_REGISTRY_DOCUMENT_VERSION",
        "CURRENT_TRACE_DOCUMENT_VERSION",
        "ScoreComponent",
        "SemanticFieldRequirement",
        "ServerProjectionSpec",
        "SourceAdapter",
        "SourceAdapterProbeDiagnostic",
        "SourceProbeDiagnosticError",
        "SourceProbeFailureCategory",
        "SourceProbeFailureReport",
        "SourceProbeResult",
        "ChromaVectorBackend",
        "MilvusVectorBackend",
        "PgvectorVectorBackend",
        "PineconeVectorBackend",
        "ODataSourceAdapter",
        "QdrantVectorBackend",
            "WeaviateVectorBackend",
        "OPTIMADESourceAdapter",
        "ToolCall",
        "TypedExecutionState",
        "ToolRegistry",
        "ToolResult",
        "ToolSpec",
        "VectorCollectionBinding",
        "VectorCollectionInvoker",
        "VectorCollectionSpec",
        "VectorMetadataField",
        "ScopedVectorStoreBackend",
        "VectorQueryEmbedder",
        "VectorStoreBackend",
        "UnitNormalizationSpec",
        "TraceError",
        "TracePersistenceError",
        "TransientInvocationError",
        "UnsupportedSchemaSourceError",
        "schema_tool",
        "serialize_capability_artifact",
        "tool_from_callable",
        "tool_from_odata_metadata",
        "analyze_openapi_compatibility",
        "build_capability_artifact",
        "build_capability_dependency_graph",
        "compare_capability_composition",
        "compare_capability_fields",
        "evaluate_state_eligibility",
        "validate_capability_inputs",
        "validate_capability_outputs",
        "compare_endpoint_specs",
        "compare_tool_specs",
        "backup_sqlite_storage",
        "build_capability_explorer_document",
        "render_schema_explorer",
        "LEGACY_CAPABILITY_ARTIFACT_FORMAT_VERSION",
        "SUPPORTED_CAPABILITY_ARTIFACT_FORMAT_VERSIONS",
        "ArtifactEdgeOrigin",
        "CapabilityArtifactMigrationRecord",
        "CapabilityArtifactMigrationResult",
        "artifact_edges_from_graph",
        "build_capability_artifact_from_graph",
        "capability_dependency_graph_digest",
        "migrate_capability_artifact",
        "validate_capability_artifact",
        "CAPABILITY_SNAPSHOT_DOCUMENT_VERSION",
        "LEGACY_CAPABILITY_SNAPSHOT_DOCUMENT_VERSION",
        "CapabilitySnapshotDocument",
        "CapabilitySnapshotMigrationRecord",
        "CapabilitySnapshotMigrationResult",
        "build_capability_snapshot_document",
        "load_capability_snapshot",
        "migrate_capability_snapshot",
        "serialize_capability_snapshot",
        "validate_capability_snapshot",
        "CapabilityDecisionCandidate",
        "CapabilityDecisionCandidateInput",
        "CapabilityDecisionDisposition",
        "CapabilityDecisionReason",
        "CapabilityDecisionStage",
        "CapabilityDecisionTrace",
        "CapabilityDriftDisposition",
        "CapabilityHealthDisposition",
        "CapabilityPolicyDisposition",
        "CapabilityRetrievalDisposition",
        "build_capability_decision_trace",
        "render_capability_decision_trace",
        "CapabilityDecisionCandidateInspection",
        "CapabilityDecisionTraceInspection",
        "inspect_capability_decision_trace",
        "write_schema_explorer",
        "inspect_sqlite_storage",
        "introspect_sqlite_database",
        "introspect_vector_backend",
        "introspect_graph_backend",
        "introspect_record_backend",
        "introspect_sqlalchemy_engine",
        "migrate_sqlite_storage",
        "dependency_cycles",
        "dependency_strongly_connected_components",
        "satisfiable_capability_ids",
        "update_capability_dependency_graph",
        "discover_adapter_plugins",
        "inspect_registry",
        "inspect_router",
        "inspect_run_trace",
        "inspect_tool",
        "inspect_tool_spec",
        "inspect_trace",
        "inspect_traces",
        "load_adapter_plugins",
        "load_capability_artifact",
        "raw_tool_spec_document",
        "tool_spec_document",
        "record_run_events",
        "render_dashboard",
        "replay_run_events",
        "write_dashboard",
        "CapabilityOperationalMetadata",
        "HostCapabilityConstraints",
        "OperationalConstraintReason",
        "OperationalConstraintResult",
        "evaluate_operational_constraints",
        "CapabilityDriftChange",
        "CapabilityGraphDrift",
        "capability_contract_fingerprint",
        "compare_capability_graph_snapshot",
        "CapabilityEligibilityExplanation",
        "CapabilityEligibilityReason",
        "explain_capability_eligibility",
        "CapabilityFallbackEligibility",
        "eligible_fallback_ids",
        "evaluate_fallback_eligibility",
        "CapabilityLineage",
        "CapabilityLineageHop",
        "build_capability_lineage",
        "CapabilityNegotiationCandidate",
        "CapabilityNegotiationRequest",
        "CapabilityNegotiationResult",
        "negotiate_capabilities",
        "CapabilityEffects",
        "CapabilityPrecondition",
        "EffectKind",
        "TriState",
        "evaluate_preconditions",
        "CapabilityGraphSnapshot",
        "validate_capability_publication",
        "CapabilitySnapshotStore",
        "CapabilitySnapshotPublication",
        "CapabilitySnapshotProvenance",
        "CapabilityRebuildMode",
        "CapabilityPublicationConflictError",
        "compare_capability_snapshots",
        "CapabilitySnapshotDiff",
        "CapabilitySourceRevision",
        "build_capability_snapshot",
        "require_snapshot",
    }

    assert len(schemarouter.__all__) == len(set(schemarouter.__all__))
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



def test_native_vendor_modules_are_lazy_on_core_import() -> None:
    code = r"""
import sys

import schemarouter

native_modules = (
    "schemarouter.adapters.graph_native",
    "schemarouter.adapters.record_native",
    "schemarouter.adapters.vector_native",
)
assert all(name not in sys.modules for name in native_modules), {
    name: name in sys.modules for name in native_modules
}

from schemarouter import QdrantVectorBackend

assert QdrantVectorBackend.__name__ == "QdrantVectorBackend"
assert "schemarouter.adapters.vector_native" in sys.modules
assert "schemarouter.adapters.graph_native" not in sys.modules
assert "schemarouter.adapters.record_native" not in sys.modules
"""
    subprocess.run([sys.executable, "-c", code], check=True)


def test_retired_decision_contract_is_not_installed() -> None:
    from importlib.util import find_spec

    assert find_spec("schemarouter.decisions") is None
    for symbol in (
        "CallableDecisionBackend",
        "DecisionBackend",
        "DecisionCallable",
        "DecisionOption",
        "DecisionOptionTextCallable",
        "DecisionRequest",
        "DecisionResult",
        "DecisionSelection",
        "EmbeddingCallable",
        "EmbeddingDecisionBackend",
        "FirstOptionDecisionBackend",
        "choose_async",
        "choose_sync",
    ):
        assert not hasattr(schemarouter, symbol), symbol
    assert callable(schemarouter.E5CachedEmbedder)


def test_retired_catalog_model_analyzer_is_not_installed() -> None:
    from importlib.util import find_spec

    assert find_spec("schemarouter.analyzers") is None
    for symbol in ("ModelCallable", "ModelIntent", "ModelQueryAnalyzer"):
        assert not hasattr(schemarouter, symbol), symbol
    assert callable(schemarouter.PaperQueryUnderstanding)


def test_retired_lexical_fieldgroup_helpers_are_not_installed() -> None:
    from schemarouter import concept_retrieval, field_group_retrieval

    assert not hasattr(schemarouter, "retrieve_authorized_field_group")
    assert not hasattr(schemarouter, "retrieve_authorized_concepts")
    assert not hasattr(field_group_retrieval, "retrieve_authorized_field_group")
    assert not hasattr(concept_retrieval, "retrieve_authorized_concepts")
    assert callable(schemarouter.NativeSchemaPostingIndex.lookup)
    assert callable(schemarouter.NativeSchemaPostingIndex.lookup_concepts)


def test_retired_lexical_host_diagnostics_are_not_installed() -> None:
    from importlib.util import find_spec

    assert find_spec("schemarouter.host_field_contract") is None
    assert find_spec("schemarouter.operation_intent") is None
    for name in (
        "AuthorizedContractSelection",
        "HostFieldContract",
        "RequiredEnumValue",
        "select_authorized_field_contract",
        "OperationIntentHypothesis",
        "infer_operation_intent",
    ):
        assert not hasattr(schemarouter, name), name


def test_retired_lexical_planner_modules_and_exports_are_not_installed() -> None:
    from importlib.util import find_spec

    for module in ("planner", "planning_context", "planning_stages"):
        assert find_spec(f"schemarouter.{module}") is None
    for symbol in ("KeywordAnalyzer", "QueryAnalyzer", "SchemaPlanner"):
        assert not hasattr(schemarouter, symbol), symbol


def test_lexical_selective_invocation_is_not_public() -> None:
    assert not hasattr(schemarouter, "ainvoke_selective")


def test_flat_lexical_request_is_not_installed() -> None:
    from schemarouter import models

    assert not hasattr(schemarouter, "PlanRequest")
    assert not hasattr(models, "PlanRequest")
    assert callable(schemarouter.PaperPlanRequest)


def test_retired_lexical_state_retrieval_is_not_installed() -> None:
    from importlib.util import find_spec

    assert find_spec("schemarouter.state_retrieval") is None
    for name in (
        "StateAwareCapabilityCandidate",
        "StateAwareCapabilityRetrieval",
        "evaluate_candidate_state",
        "filter_retrieval_by_state",
    ):
        assert not hasattr(schemarouter, name), name
    assert callable(schemarouter.evaluate_state_eligibility)
    assert callable(schemarouter.evaluate_preconditions)
    assert callable(schemarouter.TypedExecutionState)


def test_retired_lightweight_route_dtos_are_not_installed() -> None:
    import schemarouter.models as models

    for name in ("CapabilityRouteCandidate", "CapabilityRouteRetrieval"):
        assert not hasattr(schemarouter, name), name
        assert not hasattr(models, name), name
    assert not hasattr(schemarouter.SchemaRouter, "_project_route_retrieval_data_scope")


def test_retired_score_based_abstention_and_execution_are_not_installed() -> None:
    from importlib.util import find_spec

    for module in ("retrieval_abstention", "retrieval_execution_gate"):
        assert find_spec(f"schemarouter.{module}") is None, module
    for name in (
        "RetrievalAbstentionPolicy", "SelectiveCapabilityRetrieval",
        "apply_retrieval_abstention", "validate_selective_execution", "execute_selective_plan",
    ):
        assert not hasattr(schemarouter, name), name
    assert callable(schemarouter.validate_declared_operation_fit)
    assert callable(schemarouter.SchemaRouter.execute)
    assert callable(schemarouter.PaperQueryUnderstanding)


def test_retired_full_candidate_dtos_and_projection_are_not_installed() -> None:
    from schemarouter import models, runtime

    for name in ("CapabilityCandidate", "CapabilityRetrieval"):
        assert not hasattr(schemarouter, name), name
        assert not hasattr(models, name), name
    assert not hasattr(schemarouter.SchemaRouter, "_project_retrieval_data_scope")
    assert not hasattr(runtime, "_scoped_public_score_components")
    assert callable(schemarouter.SchemaRouter.prepare_field_routing)
    assert callable(schemarouter.SchemaRouter.execute)
