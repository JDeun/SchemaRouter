# 공개 API

최상위 `schemarouter` package는 일반 사용자를 위한 안정적인 public surface를 제공합니다.

## SchemaRouter

::: schemarouter.SchemaRouter

## AdapterRegistry

::: schemarouter.AdapterRegistry

## AdapterContext

::: schemarouter.AdapterContext

## AdapterLoadResult

::: schemarouter.AdapterLoadResult

## OPTIMADESourceAdapter

::: schemarouter.OPTIMADESourceAdapter

## ConfiguredSchemaRouter

::: schemarouter.ConfiguredSchemaRouter

## PlanRequest

::: schemarouter.PlanRequest

## PaperPlanRequest

::: schemarouter.PaperPlanRequest

## ToolResult

::: schemarouter.ToolResult

## ExecutionPolicy

::: schemarouter.ExecutionPolicy

## ExecutionBudget

::: schemarouter.ExecutionBudget

## ApprovalDeniedError

::: schemarouter.ApprovalDeniedError

## ExecutionBudgetExceededError

::: schemarouter.ExecutionBudgetExceededError

## MCPClientFactory

::: schemarouter.MCPClientFactory

## OpenAPICompatibilityReport

::: schemarouter.OpenAPICompatibilityReport

## AdapterPluginInfo

::: schemarouter.AdapterPluginInfo

## RegistryInspection

::: schemarouter.RegistryInspection

## ToolInspection

::: schemarouter.ToolInspection

## EndpointInspection

::: schemarouter.EndpointInspection

## TraceInspection

::: schemarouter.TraceInspection

## inspect_registry

::: schemarouter.inspect_registry

## inspect_tool

::: schemarouter.inspect_tool

## inspect_trace

::: schemarouter.inspect_trace

## inspect_traces

::: schemarouter.inspect_traces

## CallableDecisionBackend

이 계약은 배포 API에서 제거되었습니다. 과거 비교 실험에 한해 소스 체크아웃의 `scripts.research_legacy_decisions`를 사용합니다. [연구용 의사결정 백엔드](../concepts/decision-backends.md)를 참고하세요.

## ContractAmendmentError

::: schemarouter.ContractAmendmentError

## ProviderProfile

::: schemarouter.ProviderProfile

## ProviderResolution

::: schemarouter.ProviderResolution

## ProviderRegistrationResult

::: schemarouter.ProviderRegistrationResult

## CapabilitySnapshotStore

::: schemarouter.CapabilitySnapshotStore

## build_capability_artifact_from_graph

::: schemarouter.build_capability_artifact_from_graph

## migrate_capability_artifact

::: schemarouter.migrate_capability_artifact

## migrate_capability_snapshot

::: schemarouter.migrate_capability_snapshot

## CapabilityDecisionTrace

::: schemarouter.CapabilityDecisionTrace

## build_capability_decision_trace

::: schemarouter.build_capability_decision_trace

## render_capability_decision_trace

::: schemarouter.render_capability_decision_trace

## inspect_capability_decision_trace

::: schemarouter.inspect_capability_decision_trace

## ProviderProfileRegistry

::: schemarouter.ProviderProfileRegistry

## ProviderAccessMethod

::: schemarouter.ProviderAccessMethod

## update_capability_dependency_graph

::: schemarouter.update_capability_dependency_graph

## dependency_strongly_connected_components

독립적인 SCC, 순환 증거 및 충족 가능성 분석은 소스 체크아웃의 `scripts.research_legacy_capability_graph_analysis`에 보존한 과거 연구용 기능입니다. 설치 패키지에는 타입 기반 의존 그래프 생성, 증분 갱신, 인접 경로 조회를 유지합니다.

## validate_capability_publication

::: schemarouter.validate_capability_publication

## validate_capability_artifact

::: schemarouter.validate_capability_artifact

## validate_capability_snapshot

::: schemarouter.validate_capability_snapshot

## serialize_capability_snapshot

::: schemarouter.serialize_capability_snapshot
