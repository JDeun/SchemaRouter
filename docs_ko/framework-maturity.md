# Framework maturity matrix

SchemaRouter는 의도적으로 LangChain보다 좁은 범위를 가집니다. 목표는 범용 agent framework를 재현하는 것이 아니라 schema-aware tool planning/execution을 production-grade로 만들고 더 큰 ecosystem에 쉽게 내장되도록 하는 것입니다.

이 문서는 research metric이 아니라 framework-level maturity를 추적합니다.

> **0.17.0 성숙도 참고:** 안정 핵심 기능에는 공급자 중심 기능 등록, 정책 통제형 실행,
> 호스트에서 확인한 권한 및 데이터 범위, 데이터 시스템의 스키마 파악 기반 등록,
> 후보를 제한하는 의사결정 백엔드, 버전이 지정된 스냅샷·아티팩트,
> 개인정보를 보호하는 의사결정 추적이 포함됩니다. 검색은 등록된 기능 계약만
> 반환하며 **실행 권한을 부여하지 않습니다.** 연구 근거는 안정 제품의 보장 사항과
> 별도로 관리합니다. [연구 현황](research/routing-status.md)을 참고하십시오.

| 기능 | 현재 메인 브랜치 상태 | 향후 방향 |
| --- | --- | --- |
| Typed tool / endpoint / parameter / field contracts | 구현 완료 | 핵심 불변 조건 |
| Capability retrieval | 등록된 경로에 대한 결정적 `retrieve` / `aretrieve`와 실행 준비 상태 기반 변형을 일급 API로 지원 | 별도 인덱스·표현은 명시적 계약과 근거가 있을 때만 추가 |
| Provider-first onboarding | 내장·로컬·플러그인 `ProviderProfile` 등록부에서 접근 방법·자격 증명·의존성 상태를 명시적으로 관리하며 Materials Project, Crossref, Tavily 인수 테스트를 지원 | 플래너에 공급자별 분기 코드를 추가하지 않고 공급자 카탈로그 확대 |
| State-aware capability retrieval | 동일한 가시 후보 집합에서 고정 Top-K 필터링과 적격 Top-K 교정 보충 검색을 구분 | 호스트 상태는 명시적으로 유지하고 오케스트레이션 권한은 코어 밖에 둠 |
| Capability dependency graph | 의미 인덱스 기반 구축, 증분 재구성, 결정적 SCC, 제한된 순환 증거 및 희소 그래프 1k/10k/50k 벤치마크 지원 | 실제 레지스트리 규모가 요구할 때만 분산 저장소 추가 |
| Capability snapshots / artifacts | 내용 주소 기반 스냅샷, 원자적 CAS 게시, 버전별 이식 가능한 아티팩트·스냅샷 문서 및 결정적 이전 형식 마이그레이션 지원 | 외부 아티팩트 저장소와 서명은 호스트 소유 인프라가 준비된 경우에만 추가 |
| Unified decision traces | 검색·적격성·상태·건강·변경·정책·제약·협상·대체·계보 결과를 개인정보 보호 방식으로 집계하고 CLI·대시보드 검사 지원 | 숨겨진 기능 목록이나 페이로드를 유출하지 않는 신뢰된 내보내기 대상 추가 |
| Natural-language planning | 결정적 점수화와 레지스트리 버전별로 캐시된 정확 재현율 후보 인덱스 | 계획·실행 권한과 외부 에이전트의 선택 권한을 분리 |
| Sync / async invocation | 구현 완료 | 안정적인 공개 API |
| Batch execution | 완료 순서대로 결과를 반환하는 API를 포함해 구현 완료 | 안정적인 공개 API |
| Result streaming | 기본은 순차 실행이며 읽기 전용 병렬 완료 스트리밍은 명시적으로 활성화 | 의존성·DAG 의미 체계는 코어 밖에 유지 |
| Typed event streaming | 구현 완료 | 페이로드를 노출하지 않고 exporter 생태계 확대 |
| Input / output / config schema introspection | 구현 완료 | 기계 판독 가능한 형식 유지 |
| Retry policy | 읽기 전용 게이트, 명시적 재시도 불가 오류 표식 및 내장 OpenAPI/OPTIMADE HTTP 오류 분류 지원 | 복구 의미가 명확한 프로토콜에 한해 오류 분류 확장 |
| Python callable tools | 구현 완료 | docstring 기반 매개변수 설명 개선 |
| Structured-source adapter registry | 명시적인 진입점 플러그인을 포함해 구현 완료 | 검증된 타사 어댑터 확대 |
| OpenAPI ingestion | 일반 지원 범위, 작업 수준 우선 매개변수, 기본 path/query/header 직렬화, 객체 본문 평탄화, 타입이 지정된 JSON 루트 본문, 엄격한 태그 기반 `oneOf` discriminator, 본문 스키마 누락 보고, 명세상 무시하는 헤더 필터링, 이름 충돌을 방지하는 작업 이름 생성, 여러 2xx JSON·본문 없음 응답 검증, 로컬 참조, 명시적 활성화가 필요한 동일 출처 문서 간 참조 제한 해석, 동일 출처 정적 `$id`/`$anchor`, OpenAPI 3.0 nullable 정규화, `allOf` 객체 평탄화, `oneOf`/`anyOf` 응답 필드 탐색 및 호환성 보고 | 동적 참조·기본값 외 매개변수 스타일·자동 변형 선택은 안전하게 거부하고 타입 계약이 마련된 경우에만 확장 |
| OPTIMADE ingestion and execution | v0.2에서 구현 완료 | 공급자 연합 및 인덱스 메타 데이터베이스 순회 추가 |
| MCP ingestion and execution | Streamable HTTP, 신뢰된 stdio 하위 프로세스, 호출자 소유 전송 중립 클라이언트 팩토리로 구현 완료 | OAuth·게이트웨이 예제 확대 |
| GraphQL / OData / OpenRPC ingestion | 각 프로토콜의 고유 선택·투영 또는 RPC 의미를 유지하면서 현재 메인 브랜치에서 구현 완료 | 프로토콜 의미를 결정적으로 정의할 수 있는 범위에서만 확장 |
| Human-readable API documentation | 근거 확인을 포함한 계약 제안 절차 제공 | 여러 페이지·브라우저 기반 탐색 추가 |
| Runtime policy | 작업 종류별 기본값, 순서 있는 작업 범위 허용·거부·승인 규칙 및 실행 예산 | 신뢰된 로컬 경계 내에서만 외부 조직 정책 어댑터 추가 |
| Runtime JSON Schema validation / projection | 원시 응답 전체 검증, 명시적 중첩 객체 투영 경로, 신뢰된 서버 측 필드 선택자 | 필요성이 확인될 때만 타입 기반 배열 요소 투영 추가 |
| Schema drift analysis | 보수적인 엔드포인트·도구 계약 호환성 보고; 정확한 지문 검사는 계속 실행을 제한 | 변경 거부 경계를 약화하지 않는 CI·보고 연동 추가 |
| Planning explanations | 구조화된 점수 구성, 필드 선택 사유, 무시한 인자 기록 및 의사결정 선택 출처 | 설명은 구조적으로 제공하되 모델의 숨겨진 추론 과정은 노출하지 않음 |
| In-plan concurrency | 실행 전 검증, 완료 순서 스트리밍, 공통 예산을 갖춘 명시적 단층 `parallel_read_only` 병렬 호출 | DAG·의존성·쓰기 오케스트레이션은 코어 밖에 유지 |
| Provider/access fallback | 필드의 의미적 호환성과 타입 기반 대체 이벤트를 갖춘 사전 컴파일된 읽기 전용 동일·교차 공급자 경로 | 공급자 연합은 명시적인 계약 아래에서만 확대 |
| Multi-provider corroboration / aggregation | 명시적인 공급자 간 상호 검증, 신뢰된 식별자 엄격 일치와 과학적 관측의 출처 보존 | 유사 식별자 추정 및 진위 판단은 코어 밖에 유지 |
| Scientific field contracts | 명시적 JSON 값 구조, 선택적인 정확한 단위, 아핀 정규 단위 변환, 신뢰된 정확한 한정 조건, 한정 조건 인식 라우팅 및 호환성 미확인 대체 거부 | 온톨로지·단위 추론은 코어 밖에 두고 신뢰된 명시적 계약으로만 과학적 의미 확장 |
| Provider parameter aliases | 모호하면 거부하는 신뢰된 정확·별칭 바인딩과 독립적인 대체 경로 컴파일 | 모델이 생성한 매개변수 재매핑을 실행 경계에서 허용하지 않음 |
| Access health | 한정된 수동 쿨다운과 조기 복구할 수 있는 선택적 신뢰 상태 프로브 | 모델에 권한을 주지 않고 외부 건강 상태 소스 연동 |
| LangChain / LangGraph / LlamaIndex integrations | 선택적 어댑터와 네이티브 그래프 노드 구현 완료 | 생태계 목록 등재 확대 |
| Bounded decision backends | 의미 기반 후보 재현율, 광범위 기능 적합성, 작업 적합성, 같은 도구의 엔드포인트 구분, 후보·필드 선택, 보수적 근거 충분성 판단을 지원하며 공급자 중립 callable·embedding 및 선택적 Jev/Laya/Ollama는 모두 명시적 활성화 방식 | 실제 의사결정 실험 근거를 수집하되 모델 권한은 제한 |
| Jev / TypeSafe decision provider | 선택적 어댑터 구현 완료 | 품질 개선을 주장하기 전에 실제 작업 부하의 근거 수집 |
| Local Laya decision provider | 언어별 체크포인트 자동 선택, 신뢰도 기준 선택 보류, 지연·사전 적재 및 공통 벤치마크를 갖춘 선택적 로컬 선택 어댑터 | 기본값 결정 전 체크포인트·하드웨어별 근거 수집 |
| Local Ollama decision provider | 구조화 출력 HTTP API를 사용해 구현 완료 | 품질 주장 전 구체적인 로컬 모델·하드웨어 벤치마크 |
| Decision benchmark harness | 버전별 다국어 스트레스·보정·신규 확인 코퍼스, 기계 판독형 동결·종결 근거, JSON/CSV/HTML 보고 및 명시적인 85/97/100/1 + 250 ms 상시 목표; 최근 종료된 실험 주기에서 승격된 목표 후보 없음 | 실질적으로 새로운 기능의 사전 등록된 근거와 독립적인 신규 확인에 한해 후속 연구 |
| Framework callbacks / exporters | 민감 정보를 가린 타입 이벤트와 선택적 OpenTelemetry exporter | 필요한 경우 신뢰된 수신 대상 추가 |
| Middleware interception | 분리된 스냅샷을 받는 순서 있는 신뢰된 실행 전·후 훅 | 필요한 경우에만 조직별 훅 라이브러리 추가 |
| Composition / DAG runtime | 코어 범위 밖 | 중복 구현 대신 LangGraph와 연동 |
| Replayable run trace persistence | SQLite 추가 전용 이벤트 추적 및 실행 없는 재생 | 신뢰된 대체 저장소·내보내기 경로 추가 |
| Persistence / checkpoints | 워크플로 체크포인트는 범위 밖 | 오케스트레이션 상태를 LangGraph 등 외부 런타임에 위임 |
| HTTP serving layer | 미구현 | 선택적 서버 패키지 검토 |
| Pluggable registry boundary | `ToolRegistry` 프로토콜과 트랜잭션형 `SQLiteRegistry` | 필요한 경우에만 분산·원격 구현 추가 |
| Release / compatibility policy | 구현 완료 | 출시 후보(RC) 검토 시 정책 강제 |
| Package artifact CI | 깨끗한 wheel/sdist 스모크, 공개 API 관점의 소비자 인수 테스트, 빌드된 wheel의 선택적 의존성 해결·임포트 스모크, 프레임워크 예제 실행, 출처 증명 및 SPDX SBOM 증명 구현 | 아티팩트 검증을 필수 차단 검사로 유지 |
| Security automation | 주간·PR 의존성 감사, push·PR·예약 CodeQL, OpenSSF Scorecard 및 변경 불가능한 Actions SHA 고정 | 런타임의 안전 거부 정책을 약화하지 않고 발견 사항 처리 |
| Documentation site | MkDocs Material로 구현 완료 | 엄격한 문서 빌드를 필수 차단 검사로 유지 |
| Integration certification suite | 공개 OpenAPI/OPTIMADE 스모크의 기계 판독형 아티팩트를 보존하는 기본 검증 구현 | 실제 호환성 매트릭스 확장 |

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
