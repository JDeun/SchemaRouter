# 아키텍처와 적대적 설계 검토

SchemaRouter는 LLM/RAG tool ecosystem을 위한 **typed capability retrieval, planning, execution layer**입니다. general agent framework, model router, graph runtime, MCP replacement가 아닙니다.

핵심 원칙은 하나입니다.

> model output과 remote schema는 capability를 설명할 수 있지만 execution authority는 trusted local code만 부여합니다.

RAG/agent stack에서는 structured retrieval/execution boundary에 위치합니다. registry가 canonical capability를 보존하고 planner가 bounded candidate/field를 선택하며 executor가 current schema, fingerprint, local policy, approval, binding, input/output validation을 다시 확인합니다. retrieval 결과 자체는 권한이 아닙니다.

protocol별 ingestion은 adapter에 격리되고 canonical `ToolSpec → EndpointSpec → ParameterSpec/FieldSpec` 모델로 수렴합니다. runtime에 영향을 주는 transport identity는 fingerprinted `execution_metadata`에 두며 credential은 trusted invoker에만 남습니다.

persistent registry는 schema/catalog state만 저장합니다. invoker, credential, HTTP client, approval callback, policy는 직렬화하지 않으므로 restart 후 trusted binding을 다시 설정해야 합니다. research ranking이나 외부 framework가 이 authority boundary를 바꾸지 않는 것이 stable-core invariant입니다.
