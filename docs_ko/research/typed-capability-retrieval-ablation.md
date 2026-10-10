# 0.14 타입 기반 기능 검색 표현 방식 비교 실험

추적 이슈: #434

이 후속 실험은 기존 B1 에이전트 작업 효용성 평가가 다루지 않은 질문을 별도로 검증합니다.

> SchemaRouter의 구조화된 기능 메타데이터는 평탄화한 도구 명세보다 검색 성능을 개선하는가? 오프라인에서 생성한 사용자 의도 표현은 추가적인 가치를 제공하는가?

## B1과 분리하는 이유

B1(#420)의 실험 조건은 이미 동결됐습니다. 실제 도구 호출 에이전트에서 전체 카탈로그 노출과 SchemaRouter의 고정 Top-K 후보 노출을 비교하는 실험입니다.

이 실험 결과로 B1을 수정하거나 재해석해서는 안 됩니다. 서로 겹치지 않는 새 검색 평가 데이터를 사용해 **후속 에이전트가 도구를 선택하기 전 표현 방식 자체의 품질**을 측정합니다.

## 동결된 비교 조건

사전 등록 문서:

`benchmarks/agent-utility-v2-representation-preregistration.json`

| 조건 | 목적 |
| --- | --- |
| DESCRIPTION-ONLY | 설명 텍스트만 사용하는 하한 비교 기준 |
| RAW-SPEC | 일반적인 평탄화 도구 명세 기준선 |
| TYPED-MULTIFIELD | SchemaRouter의 리소스·작업·입력·출력·의미·단위·정책 필드를 분리해 유지 |
| INTENT-MANUAL | 기능에 따라 오프라인에서 사용자 의도 표현을 확장 |
| TYPED+INTENT | 타입 기반 필드와 사용자 의도 근거를 결합 |

TYPED-MULTIFIELD에서는 각 필드를 독립적으로 순위화한 뒤, 동결된 `k=60` 역순위 융합으로 결과를 합칩니다.

## 독립적인 새 평가 데이터

#418/#420의 기존 결과 행을 재사용하지 않고 새로운 과제 집합을 사용합니다.

- 개발 평가: 독립적인 의미 과제 60개 × 언어 표현 6종 = 360개 행
- 확인 평가: 독립적인 의미 과제 120개 × 언어 표현 6종 = 720개 행
- 언어: 영어, 한국어, 스페인어, 일본어, 독일어, 식별자와 자연어가 혼합된 입력
- 카탈로그 크기: 엔드포인트 100 / 250 / 500 / 1000개
- 통계 분석 단위: 의미 과제. 언어·카탈로그별 반복 관측값은 독립 표본으로 취급하지 않음

Required strata에는 multi-step composition, sibling-operation ambiguity, semantic-ID collision, unit compatibility, read/write 및 destructive sibling, implicit argument, near-domain unsupported request, OOD가 포함됩니다.

## 주요 평가 근거

주요 측정 지표:

- Recall@1/@3/@5/@10
- required-tool-set FullCoverage@K
- MRR / nDCG@K
- 카탈로그 크기에 따른 확장성
- 검색 지연시간 p50/p95
- 색인 구축 비용과 크기

진단 지표에서는 다음 항목도 분리해 분석합니다.

- 의미 식별자의 기여도
- 단위·차원 구분
- 읽기·쓰기·파괴적 작업 간의 혼동
- 필드 수준 제거 실험
- Top-K 스키마 컨텍스트 크기

Frozen Qwen3-0.6B tokenizer revision은 B1과 context measurement를 비교할 수 있도록 schema-token cost를 추정하는 데만 사용합니다. Retrieval model이 아닙니다.

## 연구 통제 규칙

- B1의 개별 실패 행은 모델 조정 데이터로 사용할 수 없음
- #432 홀드아웃 결과 행도 모델 조정 데이터로 사용할 수 없음
- 확인 평가 결과를 보고 필드 가중치, 융합 규칙, K 또는 실험 조건을 변경할 수 없음
- Intent generation은 authoritative capability specification과 typed metadata만 사용 가능
- Generated intent는 source-capability provenance를 유지해야 함
- Final agent는 authoritative schema를 받으며 generated manual text를 execution authority로 받지 않음
- 이 실험만으로 end-to-end agent-utility claim을 할 수 없음

## 선행연구와의 대응 관계

네 개의 보완적인 연구 흐름에서 동기를 얻습니다.

- **Toollery (2026)** — capability candidate compression과 offline intent-manual construction
- **Multi-Field Tool Retrieval (2026)** — raw document flattening 대신 structured field-level representation
- **ToolSense (2026)** — 모호성 등급과 자연스러운 질의에 따른 검색 성능 진단
- **ToolSearcher (NeurIPS 2026)** — iterative large-scale tool search. Static ablation에 가져오지 않고 이후 dynamic-retrieval 연구용으로 유지

이 실험은 SchemaRouter의 타입 기반 스키마 그래프가 후속 실행에 필요한 메타데이터에 그치는지, 아니면 검색 성능에서도 측정 가능한 이점을 제공하는지 확인하기 위한 것입니다.
