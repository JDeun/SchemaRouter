# Framework 성숙도 매트릭스

SchemaRouter는 의도적으로 LangChain보다 좁습니다. 목표는 general agent framework를 복제하는 것이 아니라 schema-aware tool planning/execution을 production-grade로 만들어 다른 ecosystem에 쉽게 삽입하는 것입니다.

현재 typed capability contract, bounded retrieval, sync/async/batch/stream/event API, input/output validation, retry, Python/OpenAPI/OPTIMADE/MCP/GraphQL/OData/OpenRPC ingestion, grounded documentation proposal, execution policy/budget/approval, schema drift, provider fallback/health, multi-provider evidence, scientific field contract, LangChain/LangGraph/LlamaIndex bridge, bounded decision backend, OpenTelemetry, SQLite registry/trace, plugin, package/security/docs CI가 구현되어 있습니다.

DAG/workflow checkpoint, general chat/message abstraction, prompt ecosystem, unrelated model wrapper, second graph runtime은 core 범위 밖입니다. mature framework에서 가져올 것은 일관된 execution vocabulary, machine-readable introspection, 낮은 tool-authoring 비용, optional integration, privacy-preserving observability입니다.

0.17.0의 stable runtime surface에는 provider-first 등록, governed execution, host-verified authorization/data scope, schema-introspected data-system onboarding, bounded decision backend, versioned snapshot/artifact, privacy-safe decision trace가 포함됩니다. 다음 maturity는 외부 ecosystem listing/usage, 더 넓은 live provider evidence, 조직별 policy integration처럼 repository 밖 근거가 필요한 영역입니다. stable runtime surface와 active research metric은 분리해 해석합니다.


## 0.17.0 성숙도 기준

안정된 실행 경계를 다시 열지 않고 다음 repository-local maturity가 추가되었습니다.

- provider 이름만으로 시작하는 `ProviderProfile` 등록 경로와 Materials Project/Crossref/Tavily
  acceptance coverage;
- 기존 stateless retrieval을 유지하는 explicit state-aware filtering 및 corrective backfill;
- semantic-indexed/incremental capability dependency graph와 bounded SCC cycle 분석;
- content-addressed snapshot, atomic CAS publication, versioned artifact/snapshot migration;
- eligibility/state/health/drift/policy/constraint/negotiation/fallback/lineage를 합치는 privacy-safe
  capability decision trace와 CLI/dashboard inspection.

이 기능들은 agent loop, workflow engine, transaction coordinator, autonomous authorization을
core에 추가하지 않습니다.
