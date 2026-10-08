# 공개 로드맵

이 로드맵은 기여자가 어떤 경계를 변경할 수 있는지 알 수 있도록 **안정 제품**, **연구**, **생태계 통합**, **커뮤니티 성장**을 구분합니다.

날짜를 약속하는 문서가 아니라 조정 관점의 문서입니다. 현재 작업과 acceptance criteria의 정본은 GitHub issue입니다.

## 안정 제품

**현재 안정 릴리스:** SchemaRouter 0.14.0 (Beta / pre-1.0).

안정 코어는 typed capability retrieval 및 schema-aware execution boundary입니다. 제품 작업은 local execution authority, schema/fingerprint validation, 명시적 side-effect policy, protocol-neutral contract를 보존해야 합니다.

현재 `main`의 최근 제품 후속 작업:

- #743 — explicit state-conditioned corrective re-retrieval
- #744 — scalable indexed/incremental capability dependency graphs
- #745 — atomic validated snapshot rebuild/publication
- #746 — versioned capability artifact/snapshot migration and semantic integrity
- #747 — unified privacy-safe capability decision traces
- #748 — Materials Project, Crossref, Tavily acceptance를 포함한 provider-first registration

현재 조정 항목:

- [#606 — Product completeness / next stable release gate](https://github.com/JDeun/SchemaRouter/issues/606)
- [안정 코어 계약](../stable-core.md)
- [릴리스 체크리스트](../release-checklist.md)
- [신뢰성, 안정성 및 공개 근거](trust-and-evidence.md)

하나의 provider를 지원하기 위해 core architecture를 다시 열지 않습니다. Adapter, trusted SDK binding, framework bridge 또는 decision plugin을 우선합니다.

## 연구

연구에서는 제품 기본값이 아닌 대안을 시험할 수 있습니다.

현재 공개 근거 및 작업:

- [#15 — live decision-routing benchmark evidence](https://github.com/JDeun/SchemaRouter/issues/15)
- [0.14 evidence checkpoint](../research/0.14-paper-evidence-checkpoint.md)
- [Research evidence package](../research/paper-evidence-package.md)
- [Research governance](../research/governance.md)

제품 변경에 맞추기 위해 frozen workload, split, promotion gate, negative result, historical evidence를 다시 작성해서는 안 됩니다. 새로운 hypothesis에는 새로운 versioned experiment가 필요합니다.

## 생태계 및 통합

목표는 기존 agent/tool ecosystem을 대체하는 것이 아니라 그 옆에서 SchemaRouter를 사용할 수 있게 하는 것입니다.

현재 조정 항목:

- [#10 — LangChain/LlamaIndex ecosystem distribution](https://github.com/JDeun/SchemaRouter/issues/10)
- LangChain / LangGraph bridge
- LlamaIndex bridge
- MCP, OpenAPI, OPTIMADE, GraphQL, OData, OpenRPC, HTTP/JSON ingestion
- System One / Jev / Laya / Ollama bounded decision backend
- OpenTelemetry integration
- third-party SourceAdapter 및 decision-backend entry point

Integration은 선택 사항으로 유지되어야 하며 SchemaRouter execution validation이나 policy를 우회해서는 안 됩니다.

## 커뮤니티 및 채택

커뮤니티 작업은 기술적 경계를 약화하지 않으면서 프로젝트를 더 쉽게 발견하고, 시험하고, 검증하고, 기여하고, 채택할 수 있게 하기 위한 것입니다.

현재 조정 항목:

- [#576 — growth parent](https://github.com/JDeun/SchemaRouter/issues/576)
- [#581 — contributor/community experience](https://github.com/JDeun/SchemaRouter/issues/581)
- [#582 — developer-focused launch/content](https://github.com/JDeun/SchemaRouter/issues/582)
- [#584 — external adopters/case studies/independent validation](https://github.com/JDeun/SchemaRouter/issues/584)
- [Adoption scorecard](adoption-scorecard.md)
- [Discoverability and positioning](discoverability.md)
- [Developer launch playbook](launch-playbook.md)
- [Launch and outreach log](launch-log.md)
- [External adoption and validation](external-adoption.md)
- [External case-study template](case-study-template.md)

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
