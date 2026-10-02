# Framework 성숙도 매트릭스

SchemaRouter는 의도적으로 LangChain보다 좁습니다. 목표는 general agent framework를 복제하는 것이 아니라 schema-aware tool planning/execution을 production-grade로 만들어 다른 ecosystem에 쉽게 삽입하는 것입니다.

현재 typed capability contract, bounded retrieval, sync/async/batch/stream/event API, input/output validation, retry, Python/OpenAPI/OPTIMADE/MCP/GraphQL/OData/OpenRPC ingestion, grounded documentation proposal, execution policy/budget/approval, schema drift, provider fallback/health, multi-provider evidence, scientific field contract, LangChain/LangGraph/LlamaIndex bridge, bounded decision backend, OpenTelemetry, SQLite registry/trace, plugin, package/security/docs CI가 구현되어 있습니다.

DAG/workflow checkpoint, general chat/message abstraction, prompt ecosystem, unrelated model wrapper, second graph runtime은 core 범위 밖입니다. mature framework에서 가져올 것은 일관된 execution vocabulary, machine-readable introspection, 낮은 tool-authoring 비용, optional integration, privacy-preserving observability입니다.

다음 maturity는 외부 ecosystem listing/usage, 더 넓은 live provider evidence, 조직별 policy integration처럼 repository 밖 근거가 필요한 영역입니다. stable runtime surface와 active research metric은 분리해 해석합니다.
