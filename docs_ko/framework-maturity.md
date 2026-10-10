# Framework maturity matrix

SchemaRouter는 의도적으로 LangChain보다 좁은 범위를 가집니다. 목표는 범용 agent framework를 재현하는 것이 아니라 schema-aware tool planning/execution을 production-grade로 만들고 더 큰 ecosystem에 쉽게 내장되도록 하는 것입니다.

이 문서는 research metric이 아니라 framework-level maturity를 추적합니다.

> **0.17.0 성숙도 참고:** 안정 핵심 기능에는 공급자 중심 기능 등록, 정책 통제형 실행,
> 호스트에서 확인한 권한 및 데이터 범위, 데이터 시스템의 스키마 파악 기반 등록,
> 후보를 제한하는 의사결정 백엔드, 버전이 지정된 스냅샷·아티팩트,
> 개인정보를 보호하는 의사결정 추적이 포함됩니다. 검색은 등록된 기능 계약만
> 반환하며 **실행 권한을 부여하지 않습니다.** 연구 근거는 안정 제품의 보장 사항과
> 별도로 관리합니다. [연구 현황](research/routing-status.md)을 참고하십시오.

| Capability | Current main | Direction |
| --- | --- | --- |
| Typed tool / endpoint / parameter / field contracts | Implemented | Core invariant |
| Capability retrieval | First-class deterministic `retrieve` / `aretrieve` + executable-ready variants over registered routes | Add alternate indexes/representations only behind explicit contracts and evidence |
| Provider-first onboarding | Built-in/local/plugin `ProviderProfile` registry with explicit method/credential/dependency status; Materials Project, Crossref, and Tavily acceptance coverage | Expand provider catalog without adding provider branches to planner |
| State-aware capability retrieval | Explicit fixed-Top-K filtering plus separate eligible-Top-K corrective backfill over the same visible surface | Keep host state explicit and orchestration authority outside core |
| Capability dependency graph | Semantic-indexed construction, incremental rebuild, deterministic SCCs, bounded cycle witnesses, sparse 1k/10k/50k benchmark | Add distributed storage only if real registry scale requires it |
| Capability snapshots / artifacts | Content-addressed snapshots, atomic CAS publication, versioned portable artifacts/snapshot documents, deterministic legacy migration | Add external artifact stores/signing only behind host-owned infrastructure |
| Unified decision traces | Privacy-safe aggregation of retrieval/eligibility/state/health/drift/policy/constraint/negotiation/fallback/lineage results with CLI/dashboard inspection | Add trusted export sinks without hidden-inventory or payload leakage |
| Natural-language planning | Deterministic scoring + exact-recall candidate index cached by registry version | Keep planning/execution authority separate from external agent selection |
| Sync / async invocation | Implemented | Stable public surface |
| Batch execution | Implemented, including completion-order APIs | Stable public surface |
| Result streaming | Sequential by default + explicit read-only parallel completion streaming | Keep dependency/DAG semantics out of core |
| Typed event streaming | Implemented | Extend exporter ecosystem without exposing payloads |
| Input / output / config schema introspection | Implemented | Keep machine-readable |
| Retry policy | Read-only gate + explicit non-retryable invocation marker + built-in OpenAPI/OPTIMADE HTTP classification | Extend protocol-specific classifiers only where recovery semantics are well-defined |
| Python callable tools | Implemented | Improve docstring parameter descriptions |
| Structured-source adapter registry | Implemented with explicit entry-point plugins | Expand certified third-party adapters |
| OpenAPI ingestion | Common subset + operation-over-path parameter overrides + default path/query/header serialization + flattened object bodies + generic typed JSON root bodies + discriminator-aware tagged oneOf bodies + schema-less body reporting + spec-ignored header filtering + collision-safe generated operation names + multi-2xx JSON/no-content response validation + local refs + opt-in bounded same-origin cross-document refs + static same-origin $id/$anchor resolution + OpenAPI 3.0 nullable normalization + allOf object flattening + oneOf/anyOf response-field discovery + compatibility report | Keep dynamic refs, non-default parameter styles, and automatic variant selection fail-closed; expand only behind typed contracts |
| OPTIMADE ingestion and execution | Implemented in v0.2 | Add provider federation / index meta-database traversal |
| MCP ingestion and execution | Implemented with Streamable HTTP, trusted stdio subprocesses, and caller-owned transport-neutral client factories | Expand OAuth/gateway examples |
| GraphQL / OData / OpenRPC ingestion | Implemented on current main with native selection/projection or RPC semantics | Extend only where protocol semantics are deterministic |
| Human-readable API documentation | Grounded proposal flow | Add multi-page/browser discovery |
| Runtime policy | Category defaults + ordered operation-scoped allow/deny/approval rules + execution budgets | Add external organization policy adapters only behind the trusted local boundary |
| Runtime JSON Schema validation / projection | Full raw validation + explicit nested object projection paths + trusted server-side field selectors | Add typed array-element projection only if needed |
| Schema drift analysis | Conservative endpoint/tool compatibility reports; exact fingerprints still gate execution | Add CI/reporting integrations without weakening drift rejection |
| Planning explanations | Structured score components, field-selection reasons, ignored-argument records, and decision-selection source | Keep explanations structural; never expose model chain-of-thought |
| In-plan concurrency | Explicit flat `parallel_read_only` fan-out with preflight validation, completion streaming, and shared budgets | Keep DAG/dependency/write orchestration out of core |
| Provider/access fallback | Precompiled read-only same-provider/cross-provider routes with semantic field compatibility and typed fallback events | Expand provider federation only through explicit contracts |
| Multi-provider corroboration / aggregation | Explicit cross-provider corroboration plus strict trusted-identifier identity resolution and provenance-preserving scientific observations | Keep fuzzy identity and truth adjudication outside core |
| Scientific field contracts | Explicit JSON value shape, optional exact units, affine canonical normalization, exact trusted qualifiers, qualifier-aware routing, and fail-closed fallback compatibility | Keep ontology/unit inference outside core; add richer scientific semantics only through explicit trusted contracts |
| Provider parameter aliases | Trusted exact/alias binding with ambiguity fail-closed behavior and independent fallback compilation | Keep model-generated parameter remapping out of the execution boundary |
| Access health | Finite passive cooldown + optional trusted background probes with early reopen | Integrate external health sources without model authority |
| LangChain / LangGraph / LlamaIndex integrations | Implemented optional adapters and native graph node | Expand ecosystem listings |
| Bounded decision backends | Semantic candidate recall, broad capability-fit, operation-fit, same-tool endpoint disambiguation, candidate/field selection, and conservative evidence-sufficiency surfaces; provider-neutral callable/embedding + optional Jev/Laya/Ollama, all opt-in | Gather live decision evidence and keep model authority bounded |
| Jev / TypeSafe decision provider | Implemented optional adapter | Gather live workload evidence before claiming quality gains |
| Local Laya decision provider | Optional local choice adapter with auto language routing, confidence abstention, lazy/preloaded checkpoints, and shared benchmark support | Gather checkpoint/hardware-specific evidence before choosing defaults |
| Local Ollama decision provider | Implemented over structured-output HTTP API | Benchmark specific local models/hardware before quality claims |
| Decision benchmark harness | Versioned multilingual stress/calibration/fresh-confirmation corpora, machine-readable freeze/terminal evidence, JSON/CSV/HTML reporting, and an explicit 85/97/100/1 + 250 ms standing target; latest closed cycle has no promoted target candidate | Continue only with preregistered materially new capability evidence and independent fresh confirmation |
| Framework callbacks / exporters | Typed redacted events + optional OpenTelemetry exporter | Add additional trusted sinks as needed |
| Middleware interception | Trusted ordered before/after execution hooks with detached snapshots | Add organization-specific hook libraries only when needed |
| Composition / DAG runtime | Out of scope for core | Integrate with LangGraph rather than duplicate it |
| Replayable run trace persistence | SQLite append-only event traces + non-executing replay | Add alternate trusted stores/export paths as needed |
| Persistence / checkpoints | Workflow checkpoints remain out of scope | Delegate orchestration state to LangGraph or another runtime |
| HTTP serving layer | Not implemented | Consider optional server package |
| Pluggable registry boundary | `ToolRegistry` protocol + transactional `SQLiteRegistry` | Add distributed/remote implementations only when needed |
| Release / compatibility policy | Implemented | Enforce during RC reviews |
| Package artifact CI | Implemented with clean wheel/sdist smoke, public-surface consumer acceptance scenarios, built-wheel optional-extra resolution/import smoke, framework-example execution, provenance, and SPDX SBOM attestations | Keep artifact verification blocking |
| Security automation | Weekly/PR dependency audit + push/PR/scheduled CodeQL + OpenSSF Scorecard + immutable Action pins | Triage findings without weakening fail-closed runtime policy |
| Documentation site | Implemented with MkDocs Material | Keep strict docs build blocking |
| Integration certification suite | Implemented baseline + retained machine-readable OpenAPI/OPTIMADE smoke artifacts | Extend the live compatibility matrix |

## 성숙한 framework에서 가져와야 할 것

### 1. One execution vocabulary

주요 구성 요소가 동일한 실행 메서드를 사용하면 프레임워크를 더 쉽게 익힐 수 있습니다. 따라서 SchemaRouter는 다음 인터페이스를 제공합니다:

- `invoke` / `ainvoke`
- `batch` / `abatch`
- `stream` / `astream`
- `astream_events`
- `with_config`

이 메서드들도 계획기, 정책, 스키마 검증 또는 바인딩 변경 검사를 우회하지 않습니다.

### 2. Introspection as a public contract

`input_schema`, `output_schema`, `config_schema`는 외부에 공개된 기계 판독형 인터페이스입니다. 서비스 계층, UI 생성, 테스트 및 프레임워크 연동에 사용하도록 설계됐습니다.

### 3. Tool authoring must be cheap

Python callable은 `add_callable()`로 직접 등록할 수 있고, 선택적으로 `@schema_tool`을 붙일 수 있습니다.
불투명한 SDK에는 명시적인 `ToolSpec`과 신뢰된 invoker 바인딩을 사용합니다.
OpenAPI, OPTIMADE, MCP, GraphQL, OData, OpenRPC는 내장된 구조화 입력 경로이며,
`AdapterRegistry`는 추가 프로토콜 로직을 핵심 플래너 밖에 둡니다.
기존 LangChain 또는 LlamaIndex 도구도 정본 기능 모델로 가져올 수 있습니다.

### 4. Integrations should be optional

코어 패키지가 모든 외부 의존성을 한데 모으는 집합체가 되어서는 안 됩니다. 생태계 연결 어댑터와 결정 제공자는 선택적 설치 항목과 지연 임포트 뒤에 배치합니다.

### 5. Observability must not weaken privacy

이벤트 페이로드는 기본적으로 마스킹됩니다. 인수와 결과 페이로드는 `RunConfig(include_payloads=True)`를 명시적으로 지정했을 때만 표시됩니다.

## 가져오지 말아야 할 것

- 범용 채팅·메시지 추상화
- 프롬프트 템플릿 생태계
- 스키마 기반 계획과 관련 없는 모델 공급자 래퍼
- 메모리·체크포인트 시스템
- 또 하나의 그래프 런타임
- 스키마 계약을 약화시키는 암묵적 형식 변환

이러한 기능은 주변 프레임워크가 담당하는 편이 적절합니다. SchemaRouter는 도구 스키마를 위한 컴파일러·런타임 경계에 집중해야 합니다.

## 다음 maturity gate

### Gate A — published non-prerelease baseline

패키지, 문서, 릴리스 자동화, 결정론적 호환성 테스트 및 공개 OpenAPI·OPTIMADE 스모크 테스트가 갖춰져 있습니다.

### Gate B — ecosystem-ready

Completed locally:

- 실행 가능한 LangChain, LangGraph, LlamaIndex 예제
- 공개된 생태계 호환성 및 유지보수 정책
- 적대적 계약 테스트를 포함한 선택적 Jev 의사결정 공급자
- 제한된 선택 검증 및 공통 벤치마크 지원을 갖춘 선택적 로컬 Laya 의사결정 공급자
- 점수 임계값·여유 점수에 따른 기권 및 유효하지 않은 벡터의 안전한 거부를 지원하는 공급자 중립 임베딩 유사도 의사결정 백엔드
- 애플리케이션이 소유한 리랭커를 위한 쿼리·후보 쌍별 의사결정 백엔드. 점수를 제한해 검증하며 핵심 패키지에 모델·런타임 의존성을 추가하지 않음
- 식별자를 보존하고 결정론적 폴백을 제공하는 제한된 필드 선택 계약
- 출처·라이선스·단위·소스 유형을 사전 검사하고 공급자에게는 거부 권한만 주는 보수적인 증거 충분성 계약
- 공급자 중립적인 의사결정 벤치마크 하네스
- 실제 Materials Project·Crossref 검증 및 명시적 Tavily 인증 처리를 포함한 공급자 중심 등록 프로필
- 안정적인 상태 비의존 검색 인터페이스를 유지하는 명시적 상태 조건부 재검색
- 제한된 SCC 순환 분석을 제공하는 인덱스·증분 방식의 기능 의존성 그래프
- 원자적 기능 스냅샷 게시와 버전별 아티팩트·스냅샷 마이그레이션 및 무결성 검사
- 검사 기능, CLI, 대시보드와 연동하는 통합 개인정보 보호형 기능 의사결정 추적
- 레지스트리 버전에 따른 캐시 무효화 및 전체 탐색과의 결과 일치 테스트를 갖춘 정확 재현율 후보 인덱스
- 기능 적합성·엔드포인트 구분·작업 적합성 평가를 위해 1,200개 사례의 다국어·적대적 v2 코퍼스와 별도 동결된 보정·홀드아웃 코퍼스
- OpenAPI 호환성 보고
- 명시적 활성화가 필요한 동일 출처·문서 간 OpenAPI 참조의 제한된 번들링
- 인증된 MCP 전송 경계
- 호출별 승인 및 실행별 예산
- 허용·거부·승인 효과를 명시한 작업 범위의 로컬 정책
- 지문 검사를 우회하지 않는 보수적인 엔드포인트·도구 스키마 차이 보고
- 결정론적·런타임 관찰 신호로부터 구성된 계획 설명
- 실행 전 검증과 공통 실행 예산을 사용하는 단층 읽기 전용 병렬 fan-out
- 필드 우선 서버 측 투영 계약 및 최종 로컬 투영
- 유한한 쿨다운과 신뢰된 상태 프로브 복구를 갖춘 제한된 공급자·접근 경로 폴백
- 개인정보 보호형 OpenTelemetry 내보내기
- 명시적 허용 목록으로 로드하는 서드파티 어댑터 플러그인
- 속성 기반 OpenAPI 기본 직렬화 검증
- 외부 자산에 의존하지 않는 의사결정 벤치마크 HTML 보고와 여러 실행 이력 시각화
- 기계가 읽을 수 있는 공개 OpenAPI·OPTIMADE 호환성 스모크 아티팩트의 보존
- 지원 Python 버전, Windows, 최소 의존성, wheel·sdist 설치를 아우르는 소비자 관점의 공개 API 검증. 빌드한 wheel의 MCP·Jev·OpenTelemetry 임포트·초기화 스모크와 LangChain·LangGraph·LlamaIndex 실행 예제도 포함

Still external or follow-up work:

- 상위 생태계의 목록 등재·논의 요청
- 실제 호스팅 공급자를 이용한 더 넓은 벤치마크 근거. 로컬·오픈 라우팅 근거에는 이미 소비한 v10 MiniLM 및 v11 pairwise-BGE 일반화 홀드아웃이 포함됨
- 동적인 OpenAPI·JSON Schema 참조 의미 체계와 플래너의 자동 스키마 변형 선택

### Gate C — production operations

Implemented locally:

- 호출·시도·원격 요청·시간·비용에 대한 결정론적 실행 예산
- 신뢰된 동기·비동기 호출별 승인
- 민감 정보가 제거된 이벤트 스트림으로부터의 OpenTelemetry span 내보내기
- 인증된 MCP·커스텀 클라이언트 팩토리 경계
- 명시적인 허용 목록 기반 어댑터 플러그인 로드
- `ToolRegistry` 프로토콜 뒤에 위치한 트랜잭션형 영속 SQLite 레지스트리
- OpenAPI 호환성 보고
- 트랜잭션을 사용하는 SQLite 도구 레지스트리 영속화
- 검증된 SQLite 실행 이벤트 추적의 영속 저장과 실행 없는 재생
- 스냅샷 전용 및 안전한 거부 동작을 보장하는 신뢰된 동기·비동기 실행 전후 훅
- 의존성 취약점 감사, CodeQL 검사, OpenSSF Scorecard 공급망 분석, 서명된 릴리스 빌드 출처 기록 및 SPDX SBOM 증명
- 원격 자산을 사용하지 않고 생성하는 벤치마크 요약·이력 대시보드
- 버전이 있는 기계 판독 아티팩트로 보관하는 예약 호환성 스모크 테스트

Remaining larger follow-up work:

- 기록 화면에 측정 날짜가 포함된 실제 모델·제공자 결과 표시
- 조직별 정책·승인 시스템 통합
