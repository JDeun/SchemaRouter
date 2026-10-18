# 공개 로드맵

이 로드맵은 기여자가 어떤 경계를 변경할 수 있는지 알 수 있도록 **안정 제품**, **연구**, **생태계 통합**, **커뮤니티 성장**을 구분합니다.

날짜를 약속하는 문서가 아니라 조정 관점의 문서입니다. 현재 작업과 acceptance criteria의 정본은 GitHub issue입니다.

## 안정 제품

**현재 안정 릴리스:** SchemaRouter 0.17.0 (Beta / pre-1.0).

안정 코어는 typed capability retrieval 및 schema-aware execution boundary입니다. 제품 작업은 local execution authority, schema/fingerprint validation, 명시적 side-effect policy, protocol-neutral contract를 보존해야 합니다.

현재 `main`의 최근 제품 후속 작업:

- 이슈 #743 — 실행 상태를 명시적으로 반영한 교정 재검색
- 이슈 #744 — 확장 가능한 인덱스 기반·증분 갱신형 기능 의존성 그래프
- 이슈 #745 — 검증된 스냅샷의 원자적 재구축 및 공개
- 이슈 #746 — 버전별 기능 아티팩트·스냅샷 마이그레이션 및 의미 무결성
- 이슈 #747 — 개인정보를 보호하는 통합 기능 의사결정 추적
- 이슈 #748 — Materials Project, Crossref, Tavily acceptance를 포함한 provider-first registration

현재 조정 항목:

- [#606 — Product completeness / next stable release gate](https://github.com/JDeun/SchemaRouter/issues/606)
- [안정 코어 계약](../stable-core.md)
- [릴리스 체크리스트](../release-checklist.md)
- [신뢰성, 안정성 및 공개 근거](trust-and-evidence.md)

하나의 provider를 지원하기 위해 core architecture를 다시 열지 않습니다. Adapter, trusted SDK binding, framework bridge 또는 decision plugin을 우선합니다.

## 초기 논문의 스키마 그래프 검색 — 향후 최우선 방향

**SchemaRouter는 에이전트가 아니라, 필드 중심의 도구 검색과 타입화된
계약을 제공하는 계층입니다.** [초기 SchemaRouter 논문](https://arxiv.org/abs/2608.21375)은
Tool·Endpoint·Parameter·OutputField·DomainConcept·FieldGroup·Unit·
SourceType·License/Provenance 사이의 신뢰된 관계를 **내부 스키마 그래프**로
관리하는 방향을 제시합니다. 질의의 개념과 필요 필드를 이 관계로 해석하고
권한·데이터 범위·가용성에 적합한 **소수의 도구·필드 후보**를 반환합니다.
실제 도구 선택, 인자 작성 및 다음 단계 결정은 **외부 에이전트의 책임**이고
실행 시에는 호스트가 명시적으로 권한·스키마를 다시 검증합니다.
그래프 DB는 선택 가능한 저장 수단이지, 그래프 기반 검색의 완성 증거가 아닙니다.

**이미 있는 기능과 앞으로 구현할 부분을 혼동하지 않습니다.**
`retrieve_authorized(query, k=5)`는 기존부터 권한별 Top-K를 제공합니다.
새 목차/K5 출력 래퍼 또는 에이전트 루프 개발은 초기 논문의
**질의→개념→필드 관계 검색** 개선이 아닙니다. producer→consumer
의존성 그래프, 스냅샷 아티팩트도 기본 검색 경로에 개념 관계가
연결됐다는 근거와는 별도로 확인해야 합니다.

**개발 순서 및 변경 금지 조건:**

1. [#1530 — 논문과 실제 검색 코드 대조](https://github.com/JDeun/SchemaRouter/issues/1530):
   Intent·DomainConcept/alias·FieldGroup·단위·타입·출처·라이선스·
   필드 프로젝션·그래프 버전별로 실제 연결 여부와 테스트 근거를 기록합니다.
2. [#1532 — P0 숨김 필드 메타데이터](https://github.com/JDeun/SchemaRouter/issues/1532)
   및 [#1450 — 권한/소스 변경](https://github.com/JDeun/SchemaRouter/issues/1450):
   비인가 필드명 노출과 스키마·권한 변경 검증을 검색 성능 승격보다
   우선합니다. 그래프 관계가 비인가 도구/필드를 노출하거나 실행
   권한을 만들 수 없습니다.
3. [#1531 — 선언된 개념→필드 관계 E0 실험](https://github.com/JDeun/SchemaRouter/pull/1531):
   명시된 한국어/일본어 별칭→semantic ID를 검증하고, 이후
   필드 그룹·엔드포인트·단위/한정자·출처/라이선스를 기존 권한별
   검색 경계에서 평가합니다. 논문 Algorithm 1 전체 구현이나
   독립적 성능 입증이 아니므로 기본값·K=5는 유지합니다.
4. [#1339 — EN/KO/JA 초기 도구·필드 재현율](https://github.com/JDeun/SchemaRouter/issues/1339)
   및 [#1477 — 외부 에이전트의 실제 작업 완료](https://github.com/JDeun/SchemaRouter/issues/1477):
   연산·인자·필드 정확도, OOD/no-fit, 스키마 바이트와 실제 토큰,
   CPU p50/p95/p99를 함께 측정합니다. 독립 작성자의 원본 작업·정답과
   권한 근거 [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)가
   없으면 **BLOCKED_EXTERNAL**로 표기하고 동결된 #432를 바꾸지 않습니다.
5. [#1356 — v0.18 배포](https://github.com/JDeun/SchemaRouter/pull/1356):
   독립 작업 성능·보안·소스 정합성·CPU 예산 검증 전에는 **HARD HOLD**입니다.

**부정적 결과도 보존합니다:** [#1528](https://github.com/JDeun/SchemaRouter/pull/1528)의
합성 측정에서 100~500개 도구의 전체 목차가 선택된 K5 상세 스키마보다
훨씬 많은 바이트를 차지하거나 32KiB 상한을 넘었습니다.
목차 전체를 LLM에 전달하거나 K/상한을 높이는 방향은 채택하지 않습니다.
단순 출력 래퍼 [#1529](https://github.com/JDeun/SchemaRouter/pull/1529)는
그래프 검색 개선이 아니어서 병합하지 않고 종료했습니다.

이 항목은 **향후 아키텍처 기준**이며 논문 전체 구현, 상용 수준
다국어 검색 성능 또는 새 안정 기능이 완성됐다는 주장이 아닙니다.

## 연구

연구에서는 제품 기본값이 아닌 대안을 시험할 수 있습니다.

현재 공개 근거 및 작업:

- [#15 — 실제 결정 라우팅 벤치마크 근거](https://github.com/JDeun/SchemaRouter/issues/15)
- [0.14 실증 근거 점검](../research/0.14-paper-evidence-checkpoint.md)
- [연구 근거 패키지](../research/paper-evidence-package.md)
- [연구 거버넌스](../research/governance.md)

제품 변경에 맞추기 위해 frozen workload, split, promotion gate, negative result, historical evidence를 다시 작성해서는 안 됩니다. 새로운 hypothesis에는 새로운 versioned experiment가 필요합니다.

## 생태계 및 통합

목표는 기존 agent/tool ecosystem을 대체하는 것이 아니라 그 옆에서 SchemaRouter를 사용할 수 있게 하는 것입니다.

현재 조정 항목:

- [#10 — LangChain/LlamaIndex ecosystem distribution](https://github.com/JDeun/SchemaRouter/issues/10)
- LangChain / LangGraph bridge
- LlamaIndex bridge
- MCP·OpenAPI·OPTIMADE·GraphQL·OData·OpenRPC·HTTP/JSON 수집
- System One·Jev·Laya·Ollama의 제한된 결정 백엔드
- OpenTelemetry integration
- third-party SourceAdapter 및 decision-backend entry point

Integration은 선택 사항으로 유지되어야 하며 SchemaRouter execution validation이나 policy를 우회해서는 안 됩니다.

## 커뮤니티 및 채택

커뮤니티 작업은 기술적 경계를 약화하지 않으면서 프로젝트를 더 쉽게 발견하고, 시험하고, 검증하고, 기여하고, 채택할 수 있게 하기 위한 것입니다.

현재 조정 항목:

- [#576 — 성장 작업 총괄](https://github.com/JDeun/SchemaRouter/issues/576)
- [#581 — 기여자·커뮤니티 경험](https://github.com/JDeun/SchemaRouter/issues/581)
- [#582 — 개발자 중심 출시·콘텐츠](https://github.com/JDeun/SchemaRouter/issues/582)
- [#584 — 외부 채택·사례 연구·독립 검증](https://github.com/JDeun/SchemaRouter/issues/584)
- [채택 현황 점수표](adoption-scorecard.md)
- [발견 가능성과 포지셔닝](discoverability.md)
- [개발자 출시 안내서](launch-playbook.md)
- [출시 및 외부 연락 기록](launch-log.md)
- [외부 채택 및 검증](external-adoption.md)
- [외부 사례 연구 양식](case-study-template.md)

Stars는 후행 신호입니다. 허영성 홍보보다 재현 가능한 example, downstream integration, external reproduction, 반복 사용을 우선합니다.

## 외부 기여자에게 적합한 작업

좋은 contribution surface에는 다음이 포함됩니다.

- 문서화된 schema를 가진 structured protocol/provider용 bounded adapter
- 기존 integration의 집중된 compatibility test
- 지원 경로를 재현 가능하게 만드는 docs/example
- finite-option validation을 갖춘 decision-backend plugin
- SchemaRouter authority를 보존하는 framework bridge
- machine-readable artifact를 포함한 benchmark reproduction
- 명시적 failing test가 있는 작은 reliability/developer-experience defect

구현 전에 maintainer 설계가 필요한 변경:

- 새로운 execution-authority semantics
- destructive-operation policy 변경
- persisted-format compatibility guarantee 변경
- frozen research workload 또는 promotion gate 변경
- release credential/signing/publishing trust 이동
- SchemaRouter를 범용 agent runtime으로 전환

## Issue label

Label은 우선순위 연출이 아니라 작업 형태의 신호로 사용합니다.

- `good first issue`: 범위가 제한되고 공개 acceptance criterion이 있으며 숨겨진 infrastructure가 없는 작업
- `help wanted`: 외부에서 수행 가능하며 여러 파일에 걸칠 수 있는 작업
- `bug`: 재현 가능한 correctness/reliability defect
- `enhancement`: 지원되는 제품/integration 개선
- `research`: 결과가 안정 제품 보장이 아닌 empirical/benchmark 작업

작업에 미해결 architecture decision 또는 private dependency가 생기면 maintainer는 `good first issue`를 제거해야 합니다.

## GitHub Discussions 결정

**현재는 Discussions 도입을 의도적으로 보류합니다.**

현재 프로젝트는 적은 트래픽을 Issues와 Discussions로 나누기보다 실행 가능한 하나의 issue queue에서 더 큰 이점을 얻습니다. Launch/adoption 작업 이후 실행 가능한 defect/feature가 아닌 반복 Q&A 또는 설계 대화가 생기면 다시 검토합니다.

향후 활성화한다면 처음에는 다음만 사용합니다.

- Q&A
- Ideas
- Show and tell
- Announcements (maintainer만 게시)

Security report는 채널과 무관하게 비공개로 유지합니다.

## 로드맵 변경 방법

로드맵 변경은 그 동기가 된 issue를 인용해야 합니다. 항목을 완료했다고 해서 관련 code/docs가 merge되고 필요한 경우 안정 릴리스로 배포되기 전까지 새로운 안정 보장을 의미하지 않습니다.
