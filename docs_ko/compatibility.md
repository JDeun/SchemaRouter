# 호환성 검증

SchemaRouter는 deterministic release gate와 external-service smoke test를 분리합니다.

## 지원 호환성 매트릭스

Declared dependency range와 PR마다 CI가 증명하는 범위를 구분합니다. CI는 각 declared range 안에서 현재 resolve된 version을 설치하며 range 내 모든 historical version을 exhaustive test했다고 주장하지 않습니다.

| Surface | Declared support | PR gate | Notes |
| --- | --- | --- | --- |
| Python | 3.10–3.14 | 5개 version full core | >=3.10; 3.15 RC non-blocking preview |
| LangChain | `langchain-core>=1.6,<2` | contract + runnable example | optional extra |
| LangGraph | `langgraph>=1.2,<2` | real StateGraph sync/async + example | optional |
| LlamaIndex | `llama-index-core>=0.14,<1` | contract + example | optional |
| Jev/TypeSafe | `typesafe-sdk>=0.7,<1` | adversarial contract | no live API required |
| Laya | `laya>=0.3.6,<1` | adversarial adapter + extra install | model weight download 없음 |
| Ollama | structured-output HTTP API | mock transport adversarial | SDK dependency 없음 |
| MCP | `mcp>=2,<3` | real HTTP + local stdio + boundary + scheduled evidence | public Internet availability 가정 안 함 |
| OpenTelemetry | >=1.44,<2 | in-memory hierarchy/error/privacy | core dependency 없음 |
| OpenAPI | built-in | deterministic + scheduled public smoke | SDK 없음 |
| GraphQL | built-in | introspection/selection fixture + public smoke | SDK 없음 |
| OData | built-in | CSDL/$select + OData.org smoke | SDK 없음 |
| OpenRPC/JSON-RPC | built-in | deterministic + pinned reference | public execution endpoint 가정 안 함 |
| OPTIMADE | built-in | deterministic + public smoke | client dependency 없음 |
| Provider profiles | built-in/local/plugin | deterministic + MP/Crossref/Tavily evidence | credential process-local, SDK auto-install 없음 |
| PyPI stable | wheel+sdist | scheduled/manual external smoke | fresh runner + pip check + checkout 밖 scenario |
| Lightweight extras | mcp+jev+otel | scheduled/manual | framework transitive dependency 없이 검증 |
| Integration extras | mcp+langchain+langgraph+llamaindex+jev+otel | scheduled/manual | installed package bridge 검증 |

Upper bound 확대/minimum 하향 전 relevant integration test를 target에 대해 통과시키고 release note에 문서화합니다.

## 필수 CI 검사

모든 PR의 blocking CI:

- Python 3.10–3.14 core
- Windows+3.14 smoke
- warnings-as-errors
- Pyright
- full branch coverage 84% floor + XML
- minimum runtime dependency
- executable quickstart
- wheel/sdist build+metadata
- clean wheel/sdist install+quickstart
- downstream venv에서 built wheel + separate adapter distribution discovery/load/schema/policy 검증
- LangChain/LangGraph/LlamaIndex contract+examples
- 제한된 후보·필드 선택에 대한 적대적 입력 테스트
- 외부 모델을 다운로드하지 않는 Jev/Laya 어댑터 테스트
- Ollama 모의 HTTP 전송 적대적 테스트
- 실제 MCP HTTP·stdio·클라이언트 팩토리 경계 테스트
- 결정론적 GraphQL·OData·OpenRPC 테스트
- Materials Project·Crossref·Tavily의 공급자 우선 등록 테스트
- 상태 기반 검색·그래프·스냅샷·마이그레이션·결정 추적 개인정보 보호 테스트
- 메모리 내 OpenTelemetry 내보내기 테스트
- strict MkDocs

Separate `Python Preview`는 3.15 RC를 bounded runtime으로 실행하며 visible signal이지만 release blocker가 아닙니다.

Release workflow는 successful current-main CI를 소비한 뒤 tag/artifact를 resolve합니다. GitHub Release+PyPI 뒤 exact version을 wheel, forced sdist, isolated mcp/jev/otel, combined extras로 checkout 밖에서 재설치합니다. PyPI propagation은 bounded retry로 처리하며 다른 version을 허용하지 않습니다.

## 통합 기능 유지보수 정책

Core는 optional ecosystem 없이 import/run되어야 합니다. Integration은 lazy import+bounded range를 사용하고 metadata translation은 가능하지만 execution은 schema identity/policy/binding/validation을 통과해야 합니다. Declared range 내 upstream break가 생기면 temporary narrowing 가능하되 문서화합니다. New major는 dedicated CI 전 unsupported입니다. Public example/security invariant는 compatibility contract입니다.

### Package layout decision

LangChain/LangGraph/LlamaIndex는 현재 main distribution optional extra로 유지합니다. Separate package는 independent cadence, material dependency pressure, upstream dedicated distribution requirement, thin translation layer를 넘어선 growth 중 하나가 발생할 때만 도입합니다. Jev/Laya/OTel도 같은 optional-extra 원칙입니다.

## 네이티브 데이터베이스 실사용 검증 등급

두 evidence level:

- **Contract/SDK-shape**: deterministic, required CI에서 release-blocking
- **Live acceptance**: real local/container client/service로 discovery, bounded read/search/traversal, projection, trusted principal/DataScope filter, no-raw-query boundary 검증

Tier A는 deterministic local container/in-process이며 adapter 변경 release에서 evidence로 review합니다.

| Tier A runtime | Evidence |
| --- | --- |
| PostgreSQL+pgvector | real container; vector discovery/search/projection/tenant |
| Qdrant | collection discovery/search/projection/filter |
| FalkorDB | graph discovery/read-only traversal |
| MongoDB | document discovery/query/projection/tenant |
| Chroma | in-process vector discovery/search/projection/filter |
| ClickHouse | record/time-series discovery/time range/projection/tenant |

Green Tier A가 모든 adapter blanket claim은 아닙니다. Elasticsearch/OpenSearch/Neo4j/ArangoDB/InfluxDB/Milvus/Couchbase는 dedicated live acceptance 전 deterministic contract coverage입니다.

Tier B는 Pinecone/DynamoDB/Azure Cosmos/Neptune 같은 hosted/credential-gated vendor이며 manual/scheduled secret environment에서만 실행합니다. Artifact는 exact client version, safe target identity, bounded outcomes를 기록합니다. Missing hosted credential은 ordinary CI non-goal입니다.

Native DB adapter 변경 release는 affected representative family의 recent green current-main Tier A run을 요구합니다. Public Internet provider smoke는 non-blocking입니다.

## External compatibility checks

Weekly/manual `Compatibility Smoke`는 OpenAPI/OPTIMADE/GraphQL/OData/OpenRPC/MCP, Materials Project/Crossref/Tavily, latest stable PyPI package를 검증합니다. PyPI smoke는 forced wheel/sdist, pip check, checkout 밖 public scenario를 실행합니다. Isolated mcp/jev/otel과 combined extras smoke도 source checkout이 아닌 stable package로 bridge를 실행합니다.

External-service failure는 third-party availability 때문에 PR blocker가 아닌 compatibility signal입니다. Live decision model은 required CI에서 제외하며 Jev/Laya/Ollama는 explicit benchmark로 실행합니다.

## Live OpenAPI smoke

APIs.guru를 import/execute합니다.

```text
https://api.apis.guru/v2/openapi.yaml
```

Local에서는 `SCHEMAROUTER_LIVE_OPENAPI_URL`로 다른 compatible service를 지정할 수 있습니다.

## Release interpretation

Green required CI는 controlled package/protocol behavior를 증명하고 recent external smoke는 real public service compatibility의 추가 evidence입니다. Release candidate 전 둘 다 review합니다.

## Scheduled live-smoke artifacts

Non-blocking adapter/provider matrix, PyPI, integration job은 machine-readable JSON artifact를 생성합니다. Provider-first는 MP/Crossref/Tavily separate report, adapter matrix는 public OpenAPI/OPTIMADE/GraphQL/OData + pinned OpenRPC/MCP evidence를 포함합니다.

Report는 schema version, UTC time, SchemaRouter version, adapter/source identity, runtime environment, success/failure, bounded details를 기록하며 failure에서는 exception type만 기록하고 message는 생략합니다.

Artifacts는 30일 retain합니다. Unified `adapter-compatibility-matrix.json/.md`가 per-adapter report를 summarize하고 workflow summary에도 씁니다. Raw JSON이 future history/dashboard의 source of truth입니다. [Live adapter compatibility matrix](guides/live-compatibility-matrix.md) 참고.
