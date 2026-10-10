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

각 통합 기능의 선언된 의존성 범위와 실제 선택 설치 패키지는 다음과 같습니다. Python 3.10 이상이 필수이며, CI는 현재 해결된 의존성 버전을 시험하는 것이지 범위에 포함된 모든 과거 버전을 전수 시험하는 것이 아닙니다.

- LangChain: `langchain-core>=1.6,<2`, `schemarouter[langchain]`
- LangGraph: `langgraph>=1.2,<2`, `schemarouter[langgraph]`; 실제 `StateGraph` 동기·비동기 계약을 검증
- LlamaIndex: `llama-index-core>=0.14,<1`, `schemarouter[llamaindex]`
- Jev/TypeSafe: `typesafe-sdk>=0.7,<1`, `schemarouter[jev]`; 필수 CI에서는 외부 API를 호출하지 않음
- Laya: `laya>=0.3.6,<1`, `schemarouter[laya]`; 필수 CI는 모델 가중치를 다운로드하지 않음
- MCP: `mcp>=2,<3`, `schemarouter[mcp]`; 실제 로컬 stdio subprocess 및 Streamable HTTP 계약을 검증
- OpenTelemetry: `opentelemetry-api/sdk>=1.44,<2`, `schemarouter[otel]`; 코어의 필수 의존성은 아님

상한 버전을 확대하거나 최소 지원 버전을 낮추기 전에는 해당 대상으로 통합 테스트를 통과해야 하며, 변경 사항을 릴리스 노트에 문서화해야 합니다.

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

필수 CI에는 다음 세부 검증도 포함됩니다. Pyright는 배포 패키지의 정적 타입을 검사합니다. 전체 테스트의 분기 커버리지는 차단 기준 84%와 XML 산출물로 확인합니다. 최소 런타임 의존성 검사에서는 선언된 하한 버전을 확인합니다. Wheel 및 sdist 각각을 별도의 깨끗한 환경에 설치하고 quickstart를 실행하며, 별도 `schemarouter.adapters` 배포 패키지의 메타데이터만을 이용한 탐색·명시적 로드·스키마 검증·로컬 실행 정책 강제를 확인합니다. 플래너는 식별자 보존, 잘못된·알 수 없는 ID, abstention, 동기·비동기 경로 및 결정론적 fallback을 검사합니다. 상태 인식 검색, 인덱싱된 증분 capability graph, 원자적 snapshot publication, 포맷 마이그레이션과 결정 trace의 privacy도 검사합니다.

프레임워크 quickstart도 별도 CI에서 실제로 수행합니다. LangChain은 `examples/langchain_quickstart.py`, LangGraph는 `examples/langgraph_quickstart.py`, LlamaIndex는 `examples/llamaindex_quickstart.py`를 실행해 문서상의 연결 경로가 동작함을 확인합니다. Python 버전은 3.10, 3.11, 3.12, 3.13, 3.14를 각각 검사하며, 특정 버전 범위 전체의 모든 과거 의존성 조합을 증명한다는 뜻은 아닙니다.

별도 `Python Preview` 워크플로는 Python 3.15 RC를 제한된 실행시간 안에서 시험합니다. 실패는 전방 호환성 신호로 표시하지만 릴리스의 차단 조건은 아닙니다.

PyPI 공개 패키지의 경량 통합은 정확히 `schemarouter[mcp,jev,otel]`로, 통합 프레임워크까지 포함한 전체 조합은 `schemarouter[mcp,langchain,langgraph,llamaindex,jev,otel]`로 검증합니다. 선택적 extra는 실제 설치된 wheel에서 확인해야 하며 소스 체크아웃의 우연한 전이 의존성에 기대서는 안 됩니다.

Release workflow는 successful current-main CI를 소비한 뒤 tag/artifact를 resolve합니다. GitHub Release+PyPI 뒤 exact version을 wheel, forced sdist, isolated mcp/jev/otel, combined extras로 checkout 밖에서 재설치합니다. PyPI propagation은 bounded retry로 처리하며 다른 version을 허용하지 않습니다.

## 통합 기능 유지보수 정책

SchemaRouter 코어는 LangChain, LangGraph, LlamaIndex, Jev/TypeSafe, Laya, MCP, OpenTelemetry를 설치하지 않아도 import와 실행이 가능해야 합니다. 통합 모듈은 지연 import와 한정된 의존성 버전 범위를 사용합니다. 외부 프레임워크·제공자의 메타데이터는 변환할 수 있지만, 실행은 반드시 SchemaRouter의 스키마 식별성, 정책, 바인딩 검사, 검증 경계를 통과해야 합니다.

이미 선언된 범위 내에서 새로운 upstream 버전이 호환성을 깨면 브리지를 수정하는 동안 지원 범위를 임시로 좁힐 수 있습니다. 이 변경은 문서화해야 합니다. 전용 CI를 추가하기 전에는 새로운 upstream 주요 버전을 지원한다고 주장하지 않습니다. 공개 예제와 문서화된 보안 불변조건도 호환성 계약에 포함됩니다.

### Package layout decision

현재 LangChain·LangGraph·LlamaIndex 브리지는 `schemarouter[langchain]`, `schemarouter[langgraph]`, `schemarouter[llamaindex]`처럼 주 배포 패키지의 선택적 extras로 유지합니다. `langchain-schemarouter` 같은 독립 패키지는 다음 중 하나 이상이 성립할 때만 검토합니다.

1. 통합 기능에 독립적인 릴리스 주기가 필요할 때
2. 의존성의 압박으로 인해 코어 패키지의 유지보수 범위가 실질적으로 확대될 때
3. 업스트림 유지관리자가 검색 가능성이나 인증을 위해 독립 배포를 요구할 때
4. 통합 기능이 얇은 변환 계층을 넘어 크게 확장될 때

Jev와 Laya도 각각 `schemarouter[jev]`, `schemarouter[laya]` 선택적 extras이며 제공자 런타임을 코어의 필수 의존성으로 만들지 않습니다. OpenTelemetry 역시 `schemarouter[otel]` 선택적 exporter 통합으로 유지합니다.

## 네이티브 데이터베이스 실사용 검증 등급

두 evidence level:

- **Contract/SDK-shape**: deterministic, required CI에서 release-blocking
- **Live acceptance**: real local/container client/service로 discovery, bounded read/search/traversal, projection, trusted principal/DataScope filter, no-raw-query boundary 검증

Tier A는 결정론적 로컬 컨테이너 또는 프로세스 내 런타임을 사용하며, 네이티브 DB 어댑터가 변경된 릴리스에서 검증 근거로 검토합니다. 호환성 워크플로는 **정확한 서비스 이미지 태그와 해결된 클라이언트 버전**을 JSON 산출물로 기록합니다.

| Tier A runtime | Evidence |
| --- | --- |
| PostgreSQL+pgvector | real container; vector discovery/search/projection/tenant |
| Qdrant | collection discovery/search/projection/filter |
| FalkorDB | graph discovery/read-only traversal |
| MongoDB | document discovery/query/projection/tenant |
| Chroma | in-process vector discovery/search/projection/filter |
| ClickHouse | record/time-series discovery/time range/projection/tenant |

Green Tier A가 모든 adapter blanket claim은 아닙니다. Elasticsearch/OpenSearch/Neo4j/ArangoDB/InfluxDB/Milvus/Couchbase는 dedicated live acceptance 전 deterministic contract coverage입니다.

Tier B는 Pinecone, DynamoDB, Azure Cosmos DB, Amazon Neptune처럼 호스팅 서비스나 인증정보가 필요한 제공자를 다룹니다. 검사 실행은 저장소 또는 환경의 비밀정보를 사용하는 수동·예약 실행에 한정하며, 일반 PR의 필수 CI에 추가해서는 안 됩니다. 산출물에는 정확한 클라이언트 버전, 공개해도 안전한 대상·서비스 식별성, Tier A와 동일한 범위가 제한된 계약 검증 결과를 기록해야 합니다. 호스팅 인증정보가 없다는 사실은 일반 CI의 명시적 비목표이지, 해당 제공자의 실사용 검증 성공 근거가 아닙니다.

Native DB adapter 변경 release는 affected representative family의 recent green current-main Tier A run을 요구합니다. Public Internet provider smoke는 non-blocking입니다.

## External compatibility checks

Weekly/manual `Compatibility Smoke`는 OpenAPI/OPTIMADE/GraphQL/OData/OpenRPC/MCP, Materials Project/Crossref/Tavily, latest stable PyPI package를 검증합니다. PyPI smoke는 forced wheel/sdist, pip check, checkout 밖 public scenario를 실행합니다. Isolated mcp/jev/otel과 combined extras smoke도 source checkout이 아닌 stable package로 bridge를 실행합니다.

External-service failure는 third-party availability 때문에 PR blocker가 아닌 compatibility signal입니다. Live decision model은 required CI에서 제외합니다. Jev는 `TYPESAFE_API_KEY`와 `--jev`로 명시적으로 실행하고, 로컬 Laya는 `--laya`, 신뢰하는 로컬 Ollama 모델은 `--ollama-model <installed-model>`로 따로 벤치마킹합니다.

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

GitHub Actions는 이 artifact를 30일 동안 유지합니다. 종합 보고서 `adapter-compatibility-matrix.json`과 `adapter-compatibility-matrix.md`는 adapter별 보고서를 요약하고 동일 내용을 workflow step summary에도 기록합니다. 추후 이력·대시보드의 source of truth는 원본 JSON이며, 제3자 서비스의 일시적 장애를 release-blocking gate로 전환하지 않습니다. [Live adapter compatibility matrix](guides/live-compatibility-matrix.md) 참고.
