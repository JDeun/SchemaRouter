# 아키텍처와 적대적 설계 검토

SchemaRouter는 LLM/RAG tool ecosystem을 위한 **typed capability retrieval, planning, execution layer**입니다. general agent framework, model router, graph runtime, MCP replacement가 아닙니다.

핵심 원칙은 하나입니다.

> model output과 remote schema는 capability를 설명할 수 있지만 execution authority는 trusted local code만 부여합니다.

RAG/agent stack에서는 structured retrieval/execution boundary에 위치합니다. registry가 canonical capability를 보존하고 planner가 bounded candidate/field를 선택하며 executor가 current schema, fingerprint, local policy, approval, binding, input/output validation을 다시 확인합니다. retrieval 결과 자체는 권한이 아닙니다.

protocol별 ingestion은 adapter에 격리되고 canonical `ToolSpec → EndpointSpec → ParameterSpec/FieldSpec` 모델로 수렴합니다. runtime에 영향을 주는 transport identity는 fingerprinted `execution_metadata`에 두며 credential은 trusted invoker에만 남습니다.

persistent registry는 schema/catalog state만 저장합니다. invoker, credential, HTTP client, approval callback, policy는 직렬화하지 않으므로 restart 후 trusted binding을 다시 설정해야 합니다. research ranking이나 외부 framework가 이 authority boundary를 바꾸지 않는 것이 stable-core invariant입니다.


## 현재 typed capability infrastructure

현재 main은 기존 실행 경계를 바꾸지 않고 다음 계층을 추가합니다.

- `provider_profiles`: 사용자가 provider 이름으로 시작하면 알려진 OpenAPI/OPTIMADE/HTTP/SDK
  access method로 해석합니다.
- `capability_graph`: semantic producer index와 incremental rebuild를 사용하고 SCC 기반 bounded
  cycle witness를 제공합니다.
- `capability_snapshot` / `capability_publication`: content-addressed snapshot과 검증된 atomic
  successor publication을 제공합니다.
- `capability_artifact`: versioned portable artifact, legacy migration, semantic integrity 검증을
  제공합니다.
- `capability_decision_trace`: 기존 eligibility/state/health/drift/policy/negotiation/fallback
  결과를 privacy-safe하게 하나의 설명으로 묶습니다.

이 계층들은 orchestration, autonomous retry, transaction coordination, authorization 확대를
수행하지 않습니다.


## 추가 불변조건

현재 typed capability infrastructure는 다음 경계를 추가로 지킵니다.

1. Provider-first 등록은 알려진 access method를 해석할 수 있지만 SDK를 자동 설치하거나
   credential을 저장하거나 execution authority를 부여하지 않습니다.
2. State-conditioned corrective re-retrieval은 같은 host-visible/available capability surface
   안에서만 backfill하며 stable stateless retrieval facade를 바꾸지 않습니다.
3. Capability graph indexing/incremental rebuild는 탐색·갱신 최적화일 뿐이며 canonical
   compatibility comparator가 계속 최종 권한을 가집니다. Compatibility context가 바뀌면
   full rebuild가 필요합니다.
4. Capability snapshot publication은 atomic합니다. Reader는 완성된 predecessor 또는 successor
   중 하나만 보며 partially rebuilt graph를 관측하지 않습니다. Runtime health는 immutable
   snapshot identity에 포함되지 않습니다.
5. Capability artifact/snapshot migration은 명시적 version contract를 사용하고 corrupt/unknown
   future format을 fail-closed합니다. Migration은 secret, invoker, execution authority를
   복원하지 않습니다.
6. Decision trace는 host-visible structured result만 합칠 수 있으며 hidden inventory, rank
   score, payload, credential, chain-of-thought를 노출하거나 policy/execution 결정을 바꾸지
   않습니다.
