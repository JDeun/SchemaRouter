# 연구 지식 인덱스 — 에이전트와 유지보수자를 위한 안내

> **이 페이지는 탐색 안내이며 검증 근거가 아닙니다.** 연구 결과의 원본을 복제하거나
> 개발 단계 측정값을 독립 검증 결과로 승격하지 않습니다. 주제별 세부 근거와 구현
> 연결은 [영문 통합 인덱스](https://jdeun.github.io/SchemaRouter/research/knowledge-index/)에서 확인합니다.
>
> 정리 이슈: [#1712](https://github.com/JDeun/SchemaRouter/issues/1712),
> 세션 간 연구 트래커: [#200](https://github.com/JDeun/SchemaRouter/issues/200).

## 다음 순서로 읽으세요

1. [연구 프로그램과 현재 게이트](research-program-2026.md): 우선순위, 부정적 결과와 변경 금지 조건
2. [연구 운영 규칙](governance.md): 사전등록·동결·검증·세션 재개 순서
3. [오픈소스 도구 라우팅 조사](tool-routing-landscape.md): 이미 검증하거나 기각한 접근법
4. [선행연구 로드맵](prior-art-roadmap.md): 논문과 역사적 가설
5. [라우팅 현황](routing-status.md)과 [실험 인덱스](experiment-index.md): 과거 실험 해석
6. [실험 원장](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json)과
   [선행연구 등록부](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-prior-art-registry.json):
   성능 수치를 인용하기 전에 원본과 출처를 확인합니다.
7. [마일스톤 계획](https://github.com/JDeun/SchemaRouter/blob/main/.github/RESEARCH_MILESTONES.md):
   제안된 배정표이며, 완료 상태는 실제 GitHub 마일스톤에서 다시 확인합니다.

## 근거에서 구현으로 이동하는 경로

| 주제 ID | 연구 질문 | 원본 근거 | 구현 또는 인터페이스 | 추적 이슈 | 근거 상태 |
| --- | --- | --- | --- | --- | --- |
| SR-R01 | 스키마 타입과 출처 권한 | [연구 프로그램](research-program-2026.md) | [아키텍처](../architecture.md) | [#1450](https://github.com/JDeun/SchemaRouter/issues/1450) | 설계·일부 테스트, 외부 보안 검증 미완료 |
| SR-R02 | Native G5 그래프와 고정 K | [연구 프로그램](research-program-2026.md) | [Capability graph](https://github.com/JDeun/SchemaRouter/blob/main/src/schemarouter/capability_graph.py) | [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) | 개발 단계 근거, 독립 승격 대기 |
| SR-R03 | 한·영·일 검색과 no-fit | [연구 프로그램](research-program-2026.md) | [라우팅 현황](routing-status.md) | [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) | 동결된 부정 결과 보존, 후속 DEV는 블라인드 아님 |
| SR-R04 | 오픈소스 도구 선택과 통합 | [도구 라우팅 조사](tool-routing-landscape.md) | [Pydantic AI 검증](../project/external-validation-pydanticai.md) | [#644](https://github.com/JDeun/SchemaRouter/issues/644), [#645](https://github.com/JDeun/SchemaRouter/issues/645) | 제한적인 E0 연동, 범용 작업 성공 검증 아님 |
| SR-R05 | Open-set 거부와 선행연구 | [선행연구 로드맵](prior-art-roadmap.md) | [실험 인덱스](experiment-index.md) | [#388](https://github.com/JDeun/SchemaRouter/issues/388) | 과거 혼합·기각 결과 포함 |
| SR-R06 | 전체 도구 메뉴와 제한적 검색 | [연구 프로그램](research-program-2026.md) | [실험 원장](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json) | [#432](https://github.com/JDeun/SchemaRouter/issues/432) | 동결된 독립 부정 결과, 수정 금지 |
| SR-R07 | 연구 수명주기와 재현성 | [연구 운영 규칙](governance.md) | [실험 원장](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json) | [#200](https://github.com/JDeun/SchemaRouter/issues/200) | 절차 문서화, 개별 아티팩트 완전성 미감사 |

원본 코드로 연결되는 링크는 어디를 읽어야 하는지 알려줄 뿐, 해당 구현이
연구 게이트를 충족했다는 증거가 아닙니다. PR 병합, CI 통과, 개발 단계 실험,
독립 검증, 릴리스 승인은 서로 다른 상태입니다. 상태 변경 전 실제 이슈와 PR을 확인합니다.

## 새로운 실험을 시작하기 전에

1. 이 인덱스, 오픈소스 조사, 선행연구 등록부, 실험 원장을 검색합니다.
2. 같은 가설과 평가 범위에 관한 GitHub 이슈·열린 PR을 검색합니다.
3. 기존 결정과 부정적 근거, 남은 불확실성을 기록합니다.
4. 대표 이슈를 재개하거나 만들고 데이터·구성·기준선·기각 조건을 사전등록합니다.
5. **이슈 → 프로토콜 → 실행 결과·아티팩트 → 원장 → 결정 → 구현 PR**을 연결합니다.
6. 원본 근거와 결정 기록을 먼저 확정한 후에만 이 인덱스를 갱신합니다.
   과거 실험 결과를 조용히 바꾸지 않습니다.

## 에이전트의 검색·판단 규칙

- 이 짧은 인덱스부터 읽고 필요한 원본 문서만 선택적으로 엽니다.
- 요약이나 이전 대화 기억보다 원본 제공자가 선언한 스키마와 실험 원장을 우선합니다.
- 유사도, 양의 점수, 후보 검색 성공, CI 성공만으로 실행 권한이나 작업 성공을 주장하지 않습니다.
- 확인되지 않은 근거와 구현의 연결은 **미검증**으로 표시합니다.
- 번역본에 수치의 별도 원본을 만들지 않고 영문·국문 탐색 경로를 함께 관리합니다.
- 다음 세션에서는 [운영 규칙의 재개 순서](governance.md#session-resume)를 따른 뒤
  실제 GitHub 이슈·PR·CI 상태를 재확인합니다.
