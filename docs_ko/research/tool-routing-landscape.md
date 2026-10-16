# 도구 라우팅 오픈소스·프레임워크 기술 위키

**검토: 2026-10-16 · 연구 지식 베이스 · 제품 성능 검증이나 특정 프레임워크 추천이 아님**

이 문서는 앞으로 **도구 검색, 선택, 스키마 공개, 미지원 요청 거부, 실행 권한**을 연구할 때 맨 먼저 확인하는 안내 페이지입니다. 새 연구 결과를 모아 기존 연구를 덮어쓰는 문서가 아니라, **기존 원본 실험과 기각한 접근을 찾아가는 색인 및 의사결정 기록**입니다. 별도 GitHub Wiki가 아닌 저장소의 **국문·영문 MkDocs 문서**로 관리합니다. 버전 관리, 리뷰, 링크 검사와 GitHub Pages 내 검색을 동일하게 유지하기 위해서입니다.

## 먼저 확인: 이미 조사하고 실험했습니다

1. **2026-10-15 실제 로컬 CPU 패턴 비교:** [사전 연구 프로토콜](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/opensource-routing-patterns-dev-20261015.md), [전체 결과](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/opensource-routing-patterns-dev-20261015-results.md), [코드](https://github.com/JDeun/SchemaRouter/blob/main/scripts/evaluate_opensource_routing_patterns_dev.py). 실제 Aurelio·LlamaIndex 패키지를 동일 조건에서 실행한 비교가 아니라, **두 프로젝트의 공개 아이디어를 자체 구현**해 테스트했습니다. 영어·한국어·일본어 기존 공개 DEV에서 지원 54건, 미지원 18건을 비교했습니다.

   | 이미 시험한 방식 | 지원 요청 정확 | 미지원 요청 오선택 | 결론 |
   | --- | ---: | ---: | --- |
   | A1 다국어 예시 최대 코사인, 반드시 선택 | 30/54 | 18/18 | 거부 불가 |
   | A2 위 방식 + 원시 코사인 0.65·마진 0.03 | 9/54 | 7/18 | 정상 요청 32/54건 오거부 |
   | B1 MiniLM Top-3 + 다국어 CrossEncoder, 반드시 선택 | 33/54 | 18/18 | 후보 Top-3 재현율 52/54여도 최종 선택 33/54 |
   | B2 위 재정렬 + 원시 코사인 임계값 | 1/54 | 0/18 | 정상 요청 53/54건 오거부 |

   **4개 모두 제품 적용 기각(NOT PROMOTABLE).** 단, Aurelio의 현재 **v1 학습 기반 보정 확률**은 이전에 시험한 **고정 원시 코사인 임계값**과 다른 방법입니다. 이전 실험으로 새 버전을 검증했다고 말하지 않습니다.

2. **Pydantic AI ToolSearch는 이미 연동·실험했습니다.** [#644 보고서](../project/external-validation-pydanticai.md). 설치 패키지 기준 ToolSearch 통합과 12·50·100·250개 도구 규모의 자체 E0 평가가 있습니다. 합성 지원 요청 4건과 미지원 요청 1건을 검증한 것이며 외부 독립 검증이나 에이전트 완료율 측정이 **아닙니다**. 이 연구에서도 `score > 0`은 no-fit 확률이 아님을 기록했습니다.
3. **OpenAI Agents SDK MCP 필터도 이미 검증했습니다.** [#645 보고서](../project/external-validation-openai-agents.md). 도구 노출을 제한하면서도 SDK의 approval·guardrail·실행 권한을 유지하는지 확인했습니다. 이것은 **통합 정확성**, 작업 성공률은 아닙니다.
4. **실제 제공자 원본 도구에서 E5 효과는 상충합니다.** [ServiceNow 실제 MCP DEV](https://github.com/JDeun/SchemaRouter/blob/main/research/autoresearch/servicenow-native-e5-dev.md)에서는 K5 Lexical 17/20, E5 15/20으로 **악화**. [Open-Meteo 실제 OpenAPI CPU DEV](https://github.com/JDeun/SchemaRouter/blob/main/research/autoresearch/open-meteo-native-fixed-k5-semantic-dev.md)에서는 Lexical 18/27, E5 26/27로 **개선**. 후자의 10건 불일치는 E5 복구 9건·역전 실패 1건입니다. 미지원 요청은 각각 **4/4, 9/9 모두 비어 있지 않은 후보를 반환**했습니다. 이미 연구자가 알고 있는 DEV 문제이므로 독립 성능·안전한 거부의 증거가 아닙니다.
5. [기존 선행연구 로드맵](prior-art-roadmap.md)에서는 Adaptive Decision Boundary, OOS hard negative, energy·density, conformal 거부 등을 이미 평가했습니다. 다수는 정상 요청까지 거부했으므로 **다시 같은 DEV로 임계값을 맞추지 않습니다**. [과거 에이전트 held-out 결과](large-heldout-agent-utility.md)는 독립적으로 보존해야 하며 이후 DEV 승리가 과거 실패를 지우지 않습니다.

## 주요 외부 구현의 역할과 적용 가능성

| 외부 구현 | 공개 기능 / 참고할 설계 | SchemaRouter에 적용할 경계 | 검증 상태 |
| --- | --- | --- | --- |
| [Pydantic AI ToolSearch](https://pydantic.dev/docs/ai/capabilities/tool-search/)·[Toolsets](https://pydantic.dev/docs/ai/tools-toolsets/toolsets/) | 지연된 도구 정의 검색, 필터·승인·수명주기 분리 | 이미 구성한 SDK와 연결하고 SDK 실행·승인을 대체하지 않음 | **E0 실제 통합 완료** #644 |
| [LangChain 미들웨어](https://docs.langchain.com/oss/python/langchain/middleware/built-in)·LangGraph | 사전 도구 선택과 요청별 동적 노출 | SchemaRouter는 타입·권한 검증 계층, LangGraph는 에이전트 반복·상태 담당 | 어댑터 존재, 동일 조건 독립 성능 비교 없음 |
| [LlamaIndex RouterRetriever](https://developers.llamaindex.ai/python/framework-api-reference/retrievers/router/) | 후보 메타데이터를 이용한 retriever 선택 | 검색·선택 구조 참고, 원본 도구/인자·출력 필드 검증은 별개 | **영감 받은 자체 구현만** 평가 |
| [Aurelio Semantic Router v1](https://docs.aurelio.ai/docs/semantic-router/v1/user-guide/features/calibration) | Dense, 선택적 Sparse, 별도 라벨로 `fit()` 보정, `None` 무경로 라벨, 보정된 임계값 | 미지원 판정은 **별도 독립 데이터로 보정한 결정**이어야 함. 단순 코사인 컷오프와 혼동 금지 | 예전 원시 임계값 시험은 실패, **v1 보정 방식 미시험** |
| [Claude Tool Search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) | BM25·regex 검색 + 필요할 때 전체 도구 정의 확장 | 후보 발견과 스키마 공개를 분리. 클라우드 플랫폼 성능을 로컬 CPU 성능으로 간주 금지 | 구조 참고, 동일 환경 직접 실험 없음 |
| [Semantic Kernel function choice](https://learn.microsoft.com/en-us/semantic-kernel/frameworks/agent/agent-functions)·[filters](https://learn.microsoft.com/en-us/semantic-kernel/concepts/enterprise-readiness/filters) | 함수 선택·노출 설정 및 실행 필터 | 모델의 선택 제안과 실행 승인 분리 | 구조 참고 |
| [Haystack Routers](https://docs.haystack.deepset.ai/docs/routers), [RouteLLM](https://github.com/lm-sys/RouteLLM) | 파이프라인 분기 / 언어 모델 사이 비용·품질 라우팅 | **LLM 모델 라우팅 ≠ 원본 도구·필드 라우팅** | 카테고리 조사, 직접 성능 비교 없음 |

외부 API는 바뀔 수 있으므로 **참조 당시 버전·확인 날짜·근거 링크**를 기록합니다. 이 표는 설계와 구현 경계를 비교한 것이며, 프레임워크 간 동일한 환경에서 정확도·CPU 지연·토큰 절감률의 승자를 측정한 표가 **아닙니다**.

외부 기능을 제품 코드에 도입하기 전에는 해당 upstream 패키지의 **정확한 버전 또는 커밋**, 실제 호출되는 **API·도구 계약**, 스키마를 열람하고 도구를 실행할 **권한 주체와 보안 경계**, **라이선스와 사용 조건**을 공식 구현과 문서에서 재확인해야 합니다. 제조사나 연구 저자가 README에 제시한 자체 벤치마크 수치는 어디까지나 **그 프로젝트가 보고한 성능**이며, 우리가 독립적으로 재현한 SchemaRouter의 실험 결과로 취급해서는 안 됩니다.

## 현재 아키텍처 의사결정 초안 — 구현 승인이 아님

`EN/KO/JA 질의 → Principal 인증 → 권한·데이터 범위가 반영된 원본 도구 목록 → Lexical/BM25와 선택형 다국어 Dense 검색 → 원본 ID 기준의 고정 K 후보 통합 → 기능·인자·출력 필드 적합성 검사 → 미지원·정보 부족·모호함을 구별하는 별도 판단 → 상한 내 실제 스키마 공개 → 실행 직전 fingerprint·권한·승인·인자 검증 → 에이전트 완료 결과`.

아래 사항은 혼동하지 않습니다.

- **계속 유지:** 원본 tool/endpoint fingerprint, RBAC·ABAC·데이터 범위 필터, 타입이 있는 입력·출력 필드, 실행 시점의 재검증과 권한 철회 시 실패 차단.
- **아직 연구 단계:** BM25 + Dense + 후보 융합, 스키마/필드/작업 종류 검증의 통합, 독립 보정된 no-fit 판정. 후보 합집합을 만들면서 K=5보다 많은 도구를 모델에 제공하면 **같은 K 실험이라고 주장할 수 없습니다**.
- **서로 다른 네 상태:** `candidate_present_unverified`(후보만 있음), `verified_supported`(필수 기능 검증), `unsupported_after_calibration`(검증된 미지원), `insufficient_information_or_ambiguous`(정보 부족·모호함). 코사인 점수나 단순 모델 abstention은 그 자체로 미지원 판정이 아닙니다.
- **비교 금지:** 같은 DEV를 보고 정한 임계값, 고정 K가 다른 후보 합집합, 모델 입력 byte와 실제 공개 스키마 token을 혼합한 비용, 테스트용 한국어 문장 전달만으로 주장하는 실제 언어 성능.
- **최종 판단:** Recall@K가 높아도 필수 필드 누락·실행 실패·잘못된 최종 답변이 생길 수 있으므로 에이전트의 **실제 작업 완료율**까지 측정해야 합니다.

## 이미 결정한 것과 아직 남은 것

| 과제 | 현재 상태 | 앞으로의 처리 |
| --- | --- | --- |
| Pydantic AI ToolSearch 조합 | **E0 구현·검증** | #644의 동일한 5건을 새 연구로 포장하지 않음 |
| OpenAI Agents SDK 동적 MCP 필터 | **E0 구현·검증** | #645 재사용, 승인 체계 대체 금지 |
| 예시 코사인 고정 임계값·일반적인 CrossEncoder 거부기 | **시험 후 제품 적용 기각** | 실패한 DEV 데이터에 맞춰 재튜닝 금지 |
| E5 | **제공자마다 DEV 결과 상반, no-fit 실패** | 기본값 승격 금지 |
| BM25+Dense+typed 적합성+별도 no-fit | **통합 파이프라인 설계 후보** | 분리된 유사 연구를 더 만들지 말고 하나의 사전 등록된 통합 비교 |
| 독립 EN/KO/JA·미지원 요청·멀티스텝 실제 에이전트 평가 | **미완료** | #1339, #1346 열린 상태 유지; #1356 출시 보류 |

**향후 실험 조건:** 동일한 실제 원본 도구·Principal 가시 범위, K=5, 공개 스키마 토큰·바이트 상한, 누락 필드 및 인자 검증, 미지원 false accept / 정상 요청 false refusal, 100/250/500개 카탈로그, GitHub Linux CPU 지연 p50/p95, 실제 에이전트 완료율을 함께 측정합니다. 새로운 **독립 작성·미노출·도구 제공자 분리** 테스트 세트를 선등록하고, 결과가 나쁘더라도 그대로 남깁니다.

## 다음 세션 필수 확인 순서

1. 이 문서와 [선행연구 로드맵](prior-art-roadmap.md), [설계·실험 이력](design-and-experiment-history.md), [현황](routing-status.md)을 먼저 읽습니다.
2. [선행연구 레지스트리](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-prior-art-registry.json), [전체 실험 기록](https://github.com/JDeun/SchemaRouter/blob/main/benchmarks/research-experiment-ledger.json), [실험 인덱스](experiment-index.md), 이슈 [#200](https://github.com/JDeun/SchemaRouter/issues/200)·[#1339](https://github.com/JDeun/SchemaRouter/issues/1339)·[#1346](https://github.com/JDeun/SchemaRouter/issues/1346)·[#1450](https://github.com/JDeun/SchemaRouter/issues/1450)을 검색합니다.
3. 새 기법을 발견하면 **공식 링크 / 버전·커밋 / 확인 날짜 / 실제 API·권한 경계 / 기존 해당 실험 / 증거 수준 / 다음 검증 질문**을 기록합니다. 이미 기각된 실험을 이름만 바꿔 다시 하지 않습니다.
4. 출처는 반드시 분리합니다: **공식 기능 문서**, **타 프로젝트의 자체 벤치마크**, **자체 합성 E0 통합 테스트**, **과거 공개 DEV**, **실제 원본·실제 모델 CPU 실험**, **새 독립 테스트·실제 에이전트 E2**.
5. 오픈소스 비교의 목적은 인기 순위가 아니라 **구현 중복 방지와 반증 가능한 다음 개발 의사결정**입니다. 사용자 요청의 핵심인 상용 수준 성능은 독립적인 실제 성공률이 증명할 때만 주장합니다.

이 페이지는 채팅의 기억이나 매번 새로 조사하는 결과보다 우선하여 참고할 **연구 기억·의사결정 색인**입니다.