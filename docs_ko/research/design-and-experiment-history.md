# SchemaRouter 설계 및 실험 이력

> 진행 중인 연구·세션 로드맵: GitHub 이슈 #417  
> 과거 0.13 선행연구 로드맵: GitHub 이슈 #388  
> 선행연구 로드맵: `docs/research/prior-art-roadmap.md`  
> 기계 판독형 선행연구 레지스트리: `benchmarks/research-prior-art-registry.json`  
> 이전 세션 재개 추적 이슈: GitHub 이슈 #200  
> 기계 판독형 실증 근거 원장: `benchmarks/research-experiment-ledger.json`

이 문서는 최초 저장소 구현 이후 이어진 SchemaRouter의 주요 설계와 연구의 흐름을 정리합니다. 릴리스 노트보다 범위가 넓으며 아키텍처 설계 의도, 실증 연구 질문, 채택하지 않은 대안, 평가 데이터 사용 규칙, 라우팅 설계를 변경한 이유를 기록합니다.

아키텍처의 불변 조건, 평가 계약 또는 실증적 결론에 영향을 주지 않는 일반적인 버그 수정은 Git 기록에 남기되, 여기서는 별도 연구 사건으로 분류하지 않습니다.

## 1. 시작: 스키마 인식 실행 경계

### 최초 커밋 → v0.1 프레임워크 핵심

Source revision: `55e2563966b7c656a59f6fe1862ff7d01ef87bee`

최초 설계에서 정립한 다음 핵심 원칙은 지금도 프로젝트에 적용됩니다:

```text
natural-language intent
        ↓
registered typed schema
        ↓
bounded plan
        ↓
policy + validation
        ↓
execution
```

모델이나 오케스트레이터는 실행 권한의 최종 주체가 아닙니다. 등록된 스키마와 로컬 런타임이 그 권한을 갖습니다.

초기 단계에서 내린 주요 설계 결정은 다음과 같습니다:

- 도구·엔드포인트·매개변수·필드·계획·결과에 대한 타입 계약;
- 스키마 인식 계획과 필드 투영;
- 인수와 원시 결과의 JSON Schema 검증;
- 변경·파괴적·미분류 원격 작업을 안전하게 거부하는 동작;
- 스키마·호출기 변경에 대한 보호;
- 모델에 보이는 인수와 인증정보의 분리;
- OpenAPI·MCP·Python 호출 함수 수집;
- SchemaRouter를 범용 에이전트 프레임워크로 만들지 않는 LangChain 통합.

이 원칙은 이후 실험을 해석하는 기준이 되는 프로젝트 불변 조건입니다.

## 2. v0.2: 어댑터 생태계와 OPTIMADE

Source revision: `1de6b4e14f4bb6607f58e6fc73b6b62d21e9473d`

두 번째 아키텍처 단계에서는 명시적인 어댑터 계약을 중심으로 데이터 소스 수집 방식을 일반화했습니다.

주요 추가 사항:

- `SourceAdapter` / `AdapterRegistry`;
- 일급 OPTIMADE 검색;
- 필드를 인식하는 `response_fields` 투영;
- 호출 구조를 인식하는 프로토콜 호출기;
- 실제 호환성 스모크 검증 근거;
- 명시적인 전송·인증정보 경계.

이를 통해 SchemaRouter는 고정 integration 집합에서 capability-schema substrate로 이동했습니다.

## 3. v0.3: bounded decision backends

Key source revisions:

- `7c25ae95439a9cc07a5ab7b6d81db50dea791d89`
- `dfe4b85f12ae7356e085d93897b56f73272088db`
- `ac7833feceef21a1949fb70308ba86159037db21`

Research/design question:

> Semantic/model assistance가 executable authority를 만들어낼 수 없도록 제한된 상태에서도 routing을 개선할 수 있는가?

그 답을 `DecisionBackend`로 구현했습니다. Model은 locally authorized된 유한한 option ID 집합만 보고 선택하거나 abstain할 수 있으며 새로운 executable destination을 만들 수 없습니다.

This phase added:

- 제공자 중립적인 제한 결정;
- 결정적 폴백;
- 선택적으로 활성화하는 세부 `DecisionPolicy`;
- Jev/TypeSafe 연동;
- LlamaIndex 연동;
- 승인·예산·텔레메트리 및 플러그인 계약;
- 최초로 저장소에 포함된 다국어·적대적 벤치마크 코퍼스.

### decision-routing-v1

- 144 cases;
- multilingual/adversarial coverage;
- JSON/CSV benchmark reporting;
- accuracy, abstention, invalid-plan and latency metrics.

Historical workflow-level provenance for the earliest runs is being fully backfilled under issue #196. The corpus and commit history are retained.

## 4. v0.4: persistence, local decisions and evidence surfaces

v0.4 line에서는 이후 routing research의 기반이 된 여러 architectural layer를 추가했습니다:

- LangGraph `StateGraph` 연결 계층;
- 제공자 중립적인 임베딩 결정 백엔드;
- 로컬 Ollama 제한 결정 백엔드;
- 트랜잭션 기반 SQLite 레지스트리;
- 재생 가능한 실행 추적;
- 제한된 출력 필드 선택;
- 명시적인 중첩 투영 경로;
- 보수적인 근거 충분성 판단;
- 정확 일치를 유지하는 후보 색인;
- 동일 출처에 제한된 OpenAPI 외부 참조;
- 신뢰할 수 있는 실행 전후 후크.

중요한 design progression은 단순히 “route를 선택”하는 것에서 “explicit evidence, output-field, execution-state contract를 유지하면서 route를 선택”하는 것으로 이동한 것입니다.

### Historical negative experiment: generic no-route sentinel

이후 작업별 라우팅 연구가 시작되기 전에는 어휘 검색 결과가 없을 때 전체 등록 카탈로그를 제한된 결정 백엔드에 선택적으로 노출할 수 있었습니다. 일반적인 경로 없음 신호로 명시적인 `none_of_the_above` 선택지를 실험했습니다.

PR #85의 첫 번째 144사례 실험에서 빈 검색 확장과 해당 선택지를 함께 사용한 정확도는 전체 56.25%, 한국어 29.09%였습니다. 신뢰도 0.25 및 경로 없음 설정에서는 전체 54.17%, 한국어 25.45%, OOD·적대적 사례 50%를 기록했습니다.

The follow-up run showed why the mechanism was wrong: 16 explicit no-route selections contained 13 valid Korean in-domain requests and only 3 true no-route cases. PR #87 / commit `e41f57a0` removed the sentinel.

해당 선택지를 제거한 빈 검색 확장에서는 전체 정확도 61.81%, 한국어 43.64%를 기록했습니다. 같은 신뢰도 0.25·경로 없음 정책을 추가하면 전체 60.42%, 한국어 38.18%, OOD·적대적 사례 50%였습니다. 이에 따라 프로젝트는 빈 검색 확장, 신뢰도 게이트, 후보 선택 포기 및 오프라인 임계값 보정 기능을 유지했습니다.

현재 0.11 research 관점에서 generic catch-all sentinel을 이름만 바꿔 다시 도입해서는 안 됩니다. Negative capability evidence는 별도의 typed boundary signal로 표현하고 non-authoritative 상태를 유지해야 합니다.

## 5. v0.5: runtime/OpenAPI correctness

이 phase에서는 주로 execution semantics를 강화했습니다:

- 일시적 장애를 인식하는 재시도 분류;
- 실제 경과 시간으로 제한되는 재시도·승인·후크 실행;
- OpenAPI 작업 매개변수 재정의의 정확성;
- 이름 충돌을 방지하는 엔드포인트 명명;
- 필수 요청 본문의 보존;
- 프로토콜·인증 헤더 분리;
- 여러 성공 응답 계약 처리.

이 변경들은 benchmark 대상 plan이 planning-only abstraction이 아니라 실제 executable하고 contract-valid한 behavior에 대응해야 한다는 점에서 이후 experiment에 중요합니다.

## 6. v0.6: operational observability and local inference

Project에는 다음이 추가됐습니다:

- read-only inspection API and CLI;
- self-contained HTML dashboard;
- Laya local decision backend;
- expanded OpenAPI composition and serialization fidelity.

이를 통해 UI나 model surface에 mutation authority를 부여하지 않고도 routing decision과 runtime state를 inspect할 수 있어야 한다는 operational principle을 확립했습니다.

## 7. v0.7: field-first, route-second

이는 중요한 architectural shift였습니다.

Routing question은 다음과 같이 바뀌었습니다:

> 실제로 필요한 data field는 무엇이며 현재 유효한 provider/access path 중 어떤 것이 이를 충족할 수 있는가?

주요 변경 사항:

- 제공자·접근 경로 식별;
- 제한된 읽기 전용 폴백;
- 서버 측 필드 투영;
- 타입이 지정된 과학 데이터형·단위·한정자 계약;
- 신뢰할 수 있는 매개변수 별칭;
- 스키마 변경 분류;
- 작업 범위별 정책 규칙;
- 구조화된 `PlanExplanation`;
- 제한된 병렬 읽기 분기;
- 복구 가능한 접근 경로의 상태.

모든 source가 scientific/numeric한 것은 아니므로 unit metadata는 optional로 유지했습니다. Paper나 web/document search 같은 text source도 유효한 unitless capability입니다.

### Benchmark/reproducibility methodology added during the 0.7 line

Project는 empirical evidence 보존 방식도 formalize했습니다:

- 여러 실행 결과를 포함한 벤치마크 이력과 기계 판독형 호환성 산출물(#83);
- JSON/CSV/HTML 산출물을 보존하는 요청 시 전체 코퍼스 연구 워크플로(#84);
- 선택적인 빈 어휘 검색 복구, 후보 선택 포기 및 오프라인 임계값 보정 도구(#85);
- 벤치마크 보고서의 정확한 소스 리비전, 코퍼스 SHA-256, 반복 횟수 및 사례 수 제한 메타데이터(#89).

이 변경은 methodology 측면에서 중요합니다. 이후 routing claim을 screenshot이나 chat note가 아니라 정확한 source/data configuration까지 추적할 수 있습니다.

## 8. v0.8: semantic routing stages and holdout discipline

이 phase에서는 이후 주요 research subject가 된 routing stage를 도입했습니다:

```text
lexical recall
    ↓
semantic candidate recall
    ↓
candidate-fit / no-route gate
    ↓
operation-fit inside leading tool domain
    ↓
endpoint disambiguation
    ↓
validated plan
```

중요한 boundary:

- 의미 기반 후보 검색은 등록된 후보만 추가할 수 있음;
- 후보 적합성 판단은 경로를 억제할 수 있지만 권한을 만들 수 없음;
- 작업 적합성 판단은 형제 작업으로만 제한됨;
- 엔드포인트 구분은 허용된 도구 도메인 내부에서만 이뤄짐;
- 작업 별칭은 명시적인 신뢰 스키마이며 모델이 작성하지 않음.

### Corpus lineage

동일한 evidence에 반복 tuning하는 것을 피하도록 benchmark protocol을 발전시켰습니다:

- v2 — 분할이 고정된 다국어 스트레스 코퍼스 1,200건;
- v3 — 별도로 보존한 기능 적합성 홀드아웃 600건;
- v4 — 작업 적합성 홀드아웃;
- v5 — 작업 개발·보정용 원본;
- v6 — 작업 회귀 홀드아웃 600건;
- v7 — 변경 이후의 새로운 홀드아웃;
- v8 — 별칭 인식 홀드아웃으로, 이후 진단 경로에서 실수로 사용된 사실이 확인됨;
- v9 — 이를 대체하는 새로운 별칭 인식 일회성 홀드아웃;
- v10 — 작업 일반화를 위한 새로운 홀드아웃.

Known v9 result:

- overall 51.167%;
- supported exact route 38.281%;
- near-domain unsupported rejection 70.833%;
- OOD rejection 100%.

Known v10 result:

- overall 55.667%;
- supported exact route 42.188%;
- near-domain unsupported rejection 77.083%;
- OOD rejection 100%.

v8 incident는 methodology evidence로 보존합니다. Diagnostic tuning에 사용된 holdout은 “reset”되지 않으며 consumed 상태로 남고 새 holdout으로 교체합니다.

동시에 라우팅 오류 분류 체계와 실패 단계 귀속도 명시적으로 추가했습니다. 이를 통해 이후 연구에서 후보 검색, 기능 적합성, 작업 적합성, 잘못된 도구 선택, 잘못된 엔드포인트 선택을 구분할 수 있었습니다. 작업 적합성의 의미 표현은 v10 일회성 일반화 실행 전에 v5 개발·보정 데이터만 사용해 단순화했습니다.

## 9. v0.9: bounded pairwise reranking

Source revision: `880451eb0e4adadd5e96290c8c576820614fbc7a`

Cross-encoder/reranker 방식의 `PairwiseDecisionBackend`를 도입했습니다.

Scorer는 authorized `(query, option)` pair만 받으며 score는 local에서 opaque option ID로 다시 매핑합니다.

### v11 generalization holdout

Frozen BGE pairwise candidate:

- overall accuracy: 51.667%;
- supported exact route: 25.781%;
- near-domain unsupported rejection: 97.396%;
- OOD rejection: 100%.

Post-consumption MiniLM diagnostic:

- supported exact route: 40.625%;
- near-domain unsupported rejection: 77.604%.

Interpretation:

BGE는 unsupported-operation rejection을 크게 개선했지만 supported recall과 latency를 악화시켰습니다. 따라서 unconditional routing default로 승격하지 않고 optional primitive로 유지했습니다.

이를 통해 이후 research에서 반복되는 핵심 원칙이 확립됐습니다. Selection quality와 rejection quality는 동일한 objective가 아닙니다.

## 10. v0.10 contrastive BGE cycle

Cycle: `0.10-operation-contrastive-v1`

Research question:

> Sibling-contrastive pairwise scoring이 supported/rejection balance를 개선할 수 있는가?

Development selection에는 v5 development만 사용했으며 selected candidate는 confirmation 전에 freeze했습니다:

- BGE reranker;
- sibling-contrastive transform;
- beta = 1.0;
- operation-fit min score = 0.01;
- min margin = 0.0.

Development:

- supported: 65.625%;
- near-domain unsupported rejection: 95.833%.

Calibration confirmation:

- supported: 62.5%;
- rejection: 97.917%.

### v12 hygiene classification

v12 had been inspected before architecture selection, so it was classified as design-known stress evidence, not blind evidence.

### v13 blind-final

Generated only after full candidate freeze.

Result:

- 600 cases;
- supported: 61.719%;
- near-domain unsupported rejection: 98.438%;
- OOD rejection: 100%;
- false routes: 3;
- invalid plans/errors: 0.

Decision:

정확히 freeze된 profile은 optional profile로서 blind-final preregistered floor를 통과했습니다. v13은 영구적으로 consumed 상태이며 retuning에 사용할 수 없습니다.

## 11. v0.10 cheap-first cascade

Cycle: `0.10-operation-cascade-v2`

Question:

> Cheap MiniLM decision이 easy case를 처리하고 필요할 때만 BGE로 escalate하면서 quality를 유지할 수 있는가?

The selected development candidate reduced mean latency by about 10.47% and passed development floors.

Fresh same-job calibration:

- supported: 61.458%;
- near-domain rejection: 94.792%;
- mean latency reduction vs full BGE: 14.983%.

The preregistered rejection floor was 95%.

Decision:

Calibration retuning 없이 한 case 차이로 reject했습니다.

이 negative result는 중요한 paper evidence입니다. Performance miss가 작더라도 confirmation-only calibration rule을 지켰음을 보여줍니다.

## 12. v0.10 graph-projection cycle

Cycle: `0.10-operation-graph-projection-v3`

Question:

> Graph topology가 routing authority를 소유하고 semantic model은 bounded soft evidence만 제공하도록 할 수 있는가?

Architecture explored:

- hard schema graph paths;
- semantic graph seed;
- bounded propagation;
- selective pairwise escalation;
- graph corroboration;
- static option embedding cache.

중요한 measurement correction도 있었습니다. 초기 sequential baseline/candidate timing은 warm-cache/order bias에 취약하다고 판단했고 이후 latency evidence에는 warmup + counterbalanced paired execution을 사용했습니다.

Frozen development candidate:

- 1,200개 사례;
- 지원 사례: 63.281%;
- 유사 도메인 거부율: 95.313%;
- OOD: 100%;
- 잘못된 경로: 18건;
- 대응 쌍 정답 변화 +47 / -5;
- 평균 및 p95 지연시간이 유의미하게 개선됨;
- 사전등록된 개발 게이트를 모두 통과함.

### Invalidated calibration attempt

Workflow run `36285424108` generated a corpus but was cancelled before metric inspection because a structural audit found unsupported-family reuse from development.

해당 attempt는 integrity event로 보존하지만 empirical evidence에서는 제외합니다.

### Fresh calibration

Frozen candidate:

- supported: 68.75%;
- near-domain rejection: 91.667%;
- false routes: 16;
- mean/p95 latency improved strongly;
- +14 / -2 paired correctness.

Decision:

Unsupported rejection이 95% confirmation floor에 미달해 reject했습니다. Calibration은 consumed 처리했고 retuning에는 사용하지 않았습니다.

이 failure는 confirmation data에서 threshold를 수정하는 대신 새로운 cycle로 직접 이어졌습니다.

## 13. v0.11 routing-quality cycle

Cycle: `0.11-operation-routing-quality-v4`

새로운 research question은 다음과 같습니다:

> Explicit unknown handling을 갖춘 typed multi-view evidence가 exact routing과 unsupported-operation rejection을 동시에 개선할 수 있는가?

Standing development gates:

- supported exact route >= 70%;
- near-domain unsupported rejection >= 96%;
- false-route <= 2%;
- invalid plan / authority violation / execution error = 0;
- paired mean and p95 latency non-regression.

Standing production target:

- supported exact route >= 85%;
- unsupported rejection 97–99%;
- false-route <= 1%.

### Fresh v4 development corpus

- 1,800 cases;
- 1,152 supported;
- 576 near-domain unsupported;
- 72 OOD;
- six language groups;
- 16 supported routes;
- corpus SHA: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

Baseline:

- supported exact route: 44.01%;
- near-domain rejection: 94.10%;
- false-route: 5.25%;
- wrong tool: 3;
- wrong endpoint: 130.

### Typed evidence infrastructure

PRs #185 / #186 introduced:

- typed `DecisionEvidence`;
- explicit `score_kind`;
- `match / no_match / unknown`;
- `EvidenceProjector`;
- no arithmetic across incompatible score kinds;
- explicit on-unknown policy.

이는 infrastructure이며 그 자체가 performance claim은 아닙니다.

### Hierarchical tool → operation ablation

PR #189.

Hypothesis:

Tool-domain selection과 operation selection을 분리하면 routing confusion이 줄어들 것이라는 hypothesis입니다.

Result:

- supported exact route: 42.62%;
- rejection unchanged at 94.10%;
- false routes unchanged at 34;
- wrong tool unchanged at 3;
- wrong endpoint increased 130 → 166;
- paired +91 / -107.

Decision: reject했습니다.

해석: tool-domain selection은 dominant error source가 아니었으며 이 implementation은 within-tool operation choice를 악화시켰습니다.

### Accepted operation-fit selector ablation

PR #190.

Observation before the experiment:

Operation-fit은 더 나은 registered endpoint를 자주 식별했지만 planner는 해당 decision을 gate로만 사용하고 accepted route ID를 버리고 있었습니다.

A preregistered opt-in selector was implemented.

Result:

- 지원 사례 정확한 경로: 44.01% → 54.08%;
- 잘못된 엔드포인트: 130 → 14;
- 잘못된 도구는 3건으로 유지;
- 대응 쌍 변화 +129 / -13;
- 151건의 경로 변화는 모두 채택된 작업 적합성의 첫 번째 경로에서 발생;
- 거부율: 94.10%로 변화 없음;
- 잘못된 경로 비율: 5.25%로 변화 없음;
- 유효하지 않은 계획·오류: 0건.

Decision:

Standalone candidate rejected, selector primitive retained.

Interpretation:

Endpoint selection은 unsupported-operation rejection과 독립적으로 개선할 수 있습니다.

### Stage signal diagnostics

Behavior-preserving diagnostics measured candidate-fit geometry.

Key observations:

- 후보 적합성 단계의 선택 포기 총 365건;
- 지원 요청에서 선택 포기 94건;
- 그중 43건은 후보 적합성의 첫 번째 경로가 이미 기대 경로였음;
- 유사도 0.25에서는 지원 사례의 게이트 통과율 91.84%;
- 그러나 유사 도메인 게이트 거부율은 35.07%에 불과했음.

Interpretation:

하나의 global similarity threshold가 high-recall positive selector이면서 동시에 강한 unsupported-capability boundary가 될 수는 없습니다.

### Bounded retrieve → rerank diagnostic

PR #205 / work item #204 tested the preregistered architecture that removed the generic candidate-fit gate and let the existing contrastive BGE reranker score all already-authorized semantic-recall candidates.

Zero-threshold run은 ranking-ceiling diagnostic이지 promotable router가 아닙니다.

Result on the same fresh 1,800-case v4 development corpus:

- raw supported top-route exactness: 90.71% (1045 / 1152);
- invalid plans / execution errors: 0 / 0;
- mean / p95 latency: 1014 / 1916 ms on the GitHub CPU runner.

The raw score distributions showed strong separation between most supported-correct winners and no-route requests, although route-specific tails remained.

Using the preregistered **winner-first** semantics (rank first, then apply only the raw winner's route-local threshold, and abstain instead of falling through), the following development-only score frontier resulted:

| canonical false-route budget | supported exact-route | false-route rate | actual near-domain rejection | actual OOD rejection |
| ---: | ---: | ---: | ---: | ---: |
| 0 / 648 | 70.57% | 0.00% | 100.00% | 100.00% |
| 6 / 648 | 74.05% | 0.93% | 99.13% | 98.61% |
| 12 / 648 | **75.78%** | **1.85%** | **98.09%** | **98.61%** |

이 결과로 immediate research conclusion이 다음과 같이 바뀌었습니다:

- 현재 정확도·거부율·잘못된 경로에 대한 개발 게이트를 통과하기 위해 별도의 NLI/음성 모델이 필요하지는 않음;
- 임계값을 적용하는 순서는 중요한 안전 변수였음;
- 모든 요청마다 BGE 후보 4개의 점수를 계산하는 방식은 비용이 너무 높으므로 지연시간이 여전히 핵심 미해결 게이트임.

Artifact provenance:

- 워크플로: `36310955824`
- 산출물: `10929374346`
- 산출물 다이제스트: `47a1d7a5716b100edd654607816a6cceeb630be09091348fcc788928a73fdb09`
- 소스 리비전: `f43535b6ef0acbc5492b9791e6757e28a343d9fa`
- 코퍼스 SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`

### Winner-only threshold mechanism and evidence infrastructure

PR #208 added opt-in `rank_then_gate` semantics to `PairwiseDecisionBackend` and was merged into the active #195 research stack. The default historical `filter_then_rank` behavior remains unchanged.

이후 PR #210에서는 #186의 점수 유형을 안전하게 처리하는 `EvidenceProjector`를 같은 스택으로 옮겼지만 계획기에 연결하지는 않았습니다. 따라서 두 번째 결정 신호를 성급히 도입하지 않고도 후속 견고성 연구에 사용할 명시적인 `match / no_match / unknown` 근거를 유지했습니다.

### Recall-width latency ablation

Work item #214 / PR #216 preregistered a width-only development ablation.

The selection rule was fixed before execution:

1. 후보 검색 폭 2와 3을 평가;
2. 동일한 승자 경로만 대상으로 한 잘못된 경로 예산 12의 프런티어 도출;
3. 지원 사례 정확 경로 70% 이상, 정식 잘못된 경로 비율 2% 이하, 유사 도메인 거부율 하한 96% 이상, 유효하지 않은 계획·오류 0건을 유지하는 최소 폭 선택;
4. 모두 통과하지 못하면 폭 4 유지.

The chosen width must still pass a separately executed paired latency gate before the candidate is frozen.

## 14. Current research direction

Tracked in issue #197.

The next candidate must combine:

1. 채택된 작업 적합성 선택기;
2. 새로운 개발 데이터에서 정당화된 경우에만 경로·경계별 로컬 보정;
3. 점수 유형에 안전한 타입 기반 근거;
4. 명시적인 부정 기능 근거;
5. 명시적인 알 수 없음 처리;
6. 허용된 스키마 후보 안에서만 재순위화.

Architectural principle은 변하지 않습니다:

> Semantic evidence는 registered authority 위에서 rank, veto 또는 abstain할 수 있지만 authority를 만들 수는 없습니다.

## 15. Research governance and session continuity

Canonical tracker: #200

Related work items:

- #196 — historical design/experiment backfill;
- #197 — active 0.11 composite candidate;
- #198 — freeze/calibration/blind confirmation;
- #199 — follow-up paper evidence package.

At the start of a new session:

1. #200 확인;
2. 활성 하위 이슈 확인;
3. `benchmarks/research-experiment-ledger.json` 확인;
4. 현재 사전등록·결과 매니페스트 확인;
5. 진행 중인 PR·워크플로 상태 점검;
6. 선행 조건을 충족하는 첫 미완료 작업부터 재개.

Chat history는 project state를 파악하기 위한 필수 source가 아닙니다.

## 16. Evidence policy for the follow-up paper

Every empirical result should preserve, where available:

- 소스 리비전;
- 데이터셋의 역할;
- 튜닝 사용 가능 여부;
- 사전등록·동결 상태;
- 워크플로 실행 ID;
- 산출물 ID;
- 산출물 SHA-256;
- 코퍼스 SHA-256;
- 정확한 설정;
- 결과 지표;
- 판단: 채택·거부·진단 전용;
- 실패 사유;
- 해당 근거가 영구적으로 사용 완료됐는지 여부.

Rejected 및 invalidated experiment도 record의 일부로 유지합니다.

Machine-readable ledger는 향후 paper table과 reproducibility appendix를 생성하는 canonical source입니다.


## 17. Complete repository-history audit

최초 커밋부터 이 재구성에 사용한 연구 주기 기준 시점까지의 mainline 이력을 모두 열거해 감사했습니다.

정본 감사 매니페스트:

- `benchmarks/repository-history-audit.json`
- 열거된 mainline 커밋: **140개**
- 최초 리비전: `5691c3c922f0209231f112c06096fe8744681fc5`
- 감사 대상 main head: `526d0c588bbec053fba54c55d982cc67d2a74d56`

해당 시점에 커밋 제목으로 분류한 결과:

- 기능(feature) 42개
- 수정(fix) 21개
- 연구(research) 14개
- 릴리스(release) 10개
- 문서(documentation) 10개
- 테스트(test) 9개
- CI 7개
- 보안(security) 4개
- 벤치마크(benchmark) 4개
- 성능(performance) 3개
- 기타 유지보수(chore) 15개
- 최초 커밋 및 기타 1개

이 전수 열거는 앞선 서술보다 범위가 넓습니다. 공식 0.10/0.11 실험 매니페스트가 도입되기 전의 초기 구현을 연구 기록에서 조용히 제외하지 않기 위한 것입니다.

반려되거나 병합되지 않은 연구 브랜치는 mainline 커밋 이력에 나타나지 않는 것이 정상입니다. 이들의 PR, 브랜치, 워크플로 실행, 아티팩트, 판단 근거는 별도의 `benchmarks/research-experiment-ledger.json`에 유지합니다.

이 감사에는 상호 보완적인 두 축이 있습니다.

1. **mainline 이력의 완전성:** 저장소 최초 생성 이후 모든 커밋을 열거합니다.
2. **연구 근거의 완전성:** 병합되지 않았거나 기각된 실험도 PR이 닫힐 때 사라지지 않고 실험 원장에 남도록 합니다.


## 18. Width-2 frozen winner-gate executable result

작업 항목 #227 / PR #228에서는 사전 등록된 width-2, 점수 전용, route-local `rank_then_gate` 후보를 새로운 v4 개발 코퍼스 **1,800개 사례**에서 실행했습니다. 임계값 맵은 정본 width-selection 아티팩트 `10930665000`에서 실행 전에 동결했으며, calibration이나 blind 평가 근거를 사용하지 않았습니다.

품질·안전성 결과:

- 지원되는 요청의 정확 경로 선택: **72.57%** (통과 기준 70% 이상)
- 근접 도메인의 미지원 요청 거부율: **98.09%** (통과 기준 96% 이상)
- 정본 false route: **12/648 = 1.85%** (통과 기준 2% 이하)
- OOD 거부율: **98.61%**
- 무효 계획 / 실행 오류: **0 / 0**

품질 기준은 통과했지만 동일 러너에서 측정한 대응 지연 시간 기준은 통과하지 못했습니다.

- 기준선 평균/p50/p95: **531.031 / 605.144 / 697.912 ms**
- 후보 평균/p50/p95: **765.187 / 582.750 / 1836.868 ms**
- 평균 지연 시간 증가: **44.09%**
- p95 지연 시간 증가: **163.19%**

**결정: 개발 단계 지연 시간 기준에서 기각.** 이 후보는 확인 평가용으로 동결되지 않았으며 #198 calibration/blind 평가 단계로 승격해서는 안 됩니다. 이 부정적 결과는 width 2에서 승자 전용 route-local 게이트가 품질·안전성 경계를 넘더라도, BGE를 매번 호출하면 CPU 평균 및 꼬리 지연 시간이 허용 범위를 벗어남을 보여 줍니다.

출처:

- 소스 리비전: `fdaf3f77e95b504e81739c69cd1d9889d36afabb`
- 워크플로 실행: `36315784179`
- 아티팩트: `10931078672`
- 아티팩트 SHA-256: `00517181c286197fe61156d04348eb9519bc8dab3681d20650216bfb923b37e1`
- 코퍼스 SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`

다음 개발 단계 한정 근거 수집 작업은 #226이었습니다. 엔드포인트 행동 이름과 신뢰 가능한 `operation_aliases`만 사용하여 비용이 낮은 다국어 행동 신호를 측정하는 것이었습니다. 실행 동작을 바꾸는 빠른 경로, 거부(veto), 증거 투영은 모두 별도의 사전 등록 절차를 거쳐야 했습니다.


## 19. Cheap action-only evidence diagnostic

작업 항목 #226 / PR #230에서는 기존 다국어 MiniLM을 사용해 동작을 유지하는 근거 표현을 시험했습니다. 표현에는 정규화된 엔드포인트 작업 이름과 신뢰할 수 있는 `operation_aliases`만 포함했고, 도구·엔드포인트 설명, 필드, 매개변수, 코퍼스 템플릿 및 미지원 작업 레이블은 제외했습니다.

DEV result:

- 원시 지원 요청의 최상위 경로 정확도: 73.00%;
- 영어 / 스페인어 / 혼합 / 일본어 / 독일어 / 한국어 원시 정확도: 86.46 / 80.73 / 76.56 / 73.96 / 64.06 / 56.25%;
- 질의 임베딩 및 코사인 유사도 계산 평균/p50/p95: 13.836 / 13.604 / 15.515 ms;
- 고정된 16개 선택지 임베딩 비용: 68.724 ms로 캐시 가능.

The high-precision direct-accept frontier was narrow:

- score >=0.50 and margin >=0.10: 155/1800 accepted, 98.06% precision, 8.61% overall coverage;
- score >=0.55 and margin >=0.15: 67/1800 accepted, 100% observed precision, 3.72% overall coverage.

Decision: signal을 cheap bounded selector/supporting evidence surface로 유지하되 global direct fast path로 promote하지 않습니다. High-precision coverage가 너무 작아 BGE p95 bottleneck을 제거하지 못합니다.

Provenance:

- 소스 리비전: `521dcc65e0269d68c76a372606f8d22b2ac57aa1`;
- 워크플로 실행: `36319105106`;
- 산출물: `10932010750`;
- 산출물 SHA-256: `ae12b6a9abb3f6d7bc2d53792ce75b12bcb853971c8f6367f97a8f949c499011`;
- 코퍼스 SHA-256: `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

PR #230 was merged into the active v4 research integration branch because it adds diagnostic instrumentation only; it does not change default routing behavior.

## 20. Action-guided single-pair BGE diagnostic

Work item #231 / PR #232 tested whether the cheap action-only signal could choose one candidate from the already-authorized width-2 recall set before invoking BGE on only one query-route pair.

Result:

- 지원 사례 원시 정확 경로: 74.48%;
- 평균 / p95 지연시간: 445.96 / 476.42 ms;
- 엄격한 잘못된 경로 6/648 경계:
  - 지원 사례 정확도: 62.15%;
  - 잘못된 경로 비율: 0.93%;
  - 유사 도메인 거부율 하한: 98.96%;
- 정식 잘못된 경로 12/648 경계:
  - 지원 사례 정확도: 65.36%;
  - 잘못된 경로 비율: 1.85%;
  - 유사 도메인 거부율 하한: 97.92%;
- 무효한 계획 / 실행 오류: 0 / 0.

Decision: reject했습니다. Single-pair BGE는 CPU latency 문제를 상당 부분 해결했지만 충분한 supported recall을 보존하지 못했습니다.

Provenance:

- workflow: `36319879567`;
- artifact: `10932093354`;
- artifact SHA-256: `47f1a8dcab2f1956a939df995c0f19137e96d92b8a4451753abdf039598934aa`.

## 21. Cheap embedding architecture diagnostics

### Bounded action embedding

Work item #233 / PR #236 tested cached multilingual MiniLM action-only evidence inside the bounded width-2 set.

Valid revision-2 result:

- raw supported top-route exact: 73.35%;
- canonical 12/648 supported exact: 47.92%;
- near-domain rejection: 97.92%;
- false-route: 1.85%;
- mean / p95 latency: 44.29 / 47.98 ms.

An earlier run was invalidated before result inspection because projected metrics could have used only scored rows rather than the fixed 1,800-case denominator.

Decision: rejected. The architecture was fast, but score/margin open-set gating collapsed supported recall.

### Single-query MiniLM dual view

Work item #240 / PR #241 scored two cached route representations from one query embedding:

- schema/domain view;
- action/alias view.

원시 점수에서는 스키마/작업 가중치 0.25/0.75 전략이 지원 사례 정확도 75.00%로 가장 좋았습니다. 정식 12/648 지점에서는 정확도가 54.77%, 유사 도메인 거부율 97.92%, 잘못된 경로 비율 1.85%에 그쳤지만, 평균/p95 지연시간은 약 14.02 / 15.31 ms로 감소했습니다.

Decision: rejected for quality, retained as evidence that representation capacity rather than runtime had become the limiting factor.

## 22. Multilingual embedding backbone screen

Work item #242 / PR #243 kept the dual-view architecture fixed and changed only the multilingual embedding backbone.

### E5-base

- best raw exact: 84.46%;
- best canonical 12/648 exact: 62.41%;
- latency: 50.19 / 56.20 ms mean/p95.

### GTE multilingual base

- best raw exact: 89.15% using schema/action 0.25/0.75;
- best canonical 12/648 exact: 63.11%;
- latency: 69.37 / 76.58 ms mean/p95.

GTE proved that >=85% ranking capacity was available, but its native score geometry was not a sufficient open-set boundary.

### BGE-M3 embedding

BGE-M3 was the first embedding-only architecture to combine high ranking quality with a strong open-set frontier:

- 최고 원시 정확도: 88.45%;
- 잘못된 경로 12/648 기준:
  - 지원 사례 정확도: 83.85%;
  - 유사 도메인 거부율: 97.92%;
  - 잘못된 경로 비율: 1.85%;
- 잘못된 경로 6/648 기준:
  - 지원 사례 정확도: 83.33%;
  - 유사 도메인 거부율: 98.96%;
  - 잘못된 경로 비율: 0.93%;
- p95 지연시간: 약 168 ms.

Decision: BGE-M3 selected as the main strict open-set optimization line.

## 23. GTE winner + BGE rejector

Work item #244 / PR #249 tested a factorized architecture:

1. GTE 0.25/0.75 dual-view selects one registered route;
2. BGE reranker scores only that winner;
3. BGE may accept/reject but may not switch routes.

All four preregistered action/capability × max-length variants preserved raw GTE ranking at 89.15%, but the best canonical open-set result was only:

- supported exact: 76.13%;
- near-domain rejection: 97.92%;
- false-route: 1.85%;
- best end-to-end mean / p95 latency: 293.89 / 328.11 ms.

Decision: rejected. A cross-encoder winner relevance score was not a clean enough open-set separator to preserve GTE's ranking headroom.

## 24. Frozen BGE-M3 candidate and numerical-stability finding

Work item #245 / PR #247 froze the BGE-M3 50/50, budget-6 profile and executed it through the actual `SchemaPlanner`.

Safety and authority behavior reproduced exactly:

- 계획기·직접 실행 간 불일치: 0 / 1800;
- 무효한 계획: 0건;
- 실행 오류: 0건;
- 두 번째 순위 후보로 넘어간 사례: 0건;
- 잘못된 경로: 6/648 = 0.93%;
- 유사 도메인 거부율: 98.96%;
- OOD 거부율: 100%;
- 계획기 평균 / p95 지연시간: 188.73 / 206.00 ms.

However, the frozen projection expected 960 supported-correct cases and executable confirmation produced 959/1152 = 83.25%.

Artifact inspection localized the single-case drift:

- case: `v4-dev-papers-citations-ko-08`;
- route: `papers.citations`;
- frozen min score: `0.46308739913552904`;
- rerun score: `0.4630872644672503`;
- difference: approximately -1.35e-7.

The route winner and planner/direct behavior did not change; only the accept/reject boundary flipped.

Decision: not promoted.

이 결과로 추가 운영 요건이 확인됐습니다. 동결된 임계값을 실제 관측된 부동소수점 표본 점수에 정확히 맞춰서는 안 됩니다. 후속 후보는 중간점 임계값, 보수적 양자화·보호 구간, 미세 교란 검증처럼 수치적 안정성의 의미를 명시적으로 정의해야 합니다.

Provenance:

- workflow: `36323685913`;
- artifact: `10933122169`;
- artifact SHA-256: `a63e6954d8cf44db21bc89b336ca8f67bacc77af933fe870c33bc9298bf6a1a1`.

## 25. BGE-M3 fine global fusion

Work item #246 / PR #248 preregistered schema weights 0.30–0.60 with no post-run interpolation.

Best strict 6/648 result:

- schema/action fusion: 0.55 / 0.45;
- supported exact: 965/1152 = 83.77%;
- near-domain rejection: 98.96%;
- false-route: 0.93%;
- wrong-supported accepted: 62;
- mean / p95 latency: 180.34 / 195.97 ms.

Best secondary 12/648 result:

- supported exact: 970/1152 = 84.20%;
- near-domain rejection: 97.92%;
- false-route: 1.85%.

The final >=85% strict target requires at least 980/1152 correct cases, so the best global fusion was 15 cases short.

Decision: global fine-fusion search exhausted without passing the production target.

Provenance:

- workflow: `36324755106`;
- artifact: `10934145256`;
- artifact SHA-256: `60dfbb1d32f1f27873bd8fad4aa4888af80856365196e3ab6fb5be6b1e7f0af7`.

## 26. 당시 active optimization: 마지막 15 case 복구

#246의 route-level analysis에서 route마다 선호하는 schema/action weight가 다르다는 점을 확인했습니다. Holding the global 0.55 weight produced 1,019 raw supported-correct cases, while independently choosing the best preregistered grid weight for each route yields a diagnostic raw ceiling of **1,046**, a +27-case headroom.

The largest examples include:

- `inventory.search`: 50.00% raw exact at global 0.55 versus 69.44% at route-local 0.35;
- `papers.search`: 81.94% versus 90.28% at route-local 0.30.

### #256 route-local stable fusion

Work item #256 / PR #257 is the lower-cost active line.

실행 전에 route-local weight map을 freeze하고 boundary construction을 다음과 같이 변경합니다:

- 관측된 표본 점수를 임계값으로 직접 사용하지 않음;
- 인접한 고유 승자 점수의 중간값을 후보 임계값으로 사용;
- 선택된 점수 임계값은 소수점 여섯 자리까지 보수적으로 올림;
- 최종 지표는 점수·마진에 ±1e-6 및 ±1e-5 교란을 주어 검증.

Primary gate:

- supported exact >=85%;
- near-domain rejection >=97%;
- false-route <=1%;
- OOD rejection 100%;
- p95 <=250 ms;
- the same primary quality/safety gates must survive ±1e-6 perturbation.

### #255 conditional zero-false rescue

Work item #255 / PR #258 runs in parallel as a more expensive fallback.

It keeps the immutable #246 strict 0.55/0.45 base and invokes a pinned BGE cross-encoder only on base abstentions, with a primary rescue budget of zero additional false routes.

The validator may only rescue the same raw rank-1 winner; it cannot switch to rank 2 or create execution authority.

두 line 모두 DEV-only입니다. Fully frozen candidate가 development, numerical-stability, runtime gate를 모두 통과할 때까지 calibration/blind evidence는 blocked 상태를 유지합니다.


## 27. Parallel numerical-stability experiment

Work item #256 / PR #257 runs in parallel with the rejected-winner rescue line.

Motivation:

전역 0.55/0.45 BGE-M3 기준은 최종 목표에 근접했지만, #246에서는 경로마다 선호하는 스키마·작업 융합 가중치가 다름도 확인됐습니다. 이미 사전등록된 #246 격자에서 경로별 가중치를 고르면 원시 지원 요청 순위 정확도의 상한이 **1046/1152**로, 전역 0.55 순위기의 1019/1152보다 높습니다.

The route-local fusion map was frozen before execution. To avoid repeating the #245 numerical-boundary failure, its threshold protocol is stability-oriented:

- 점수 임계값은 관측된 표본 점수가 아니라 인접 승자 점수 사이의 중간값으로 정함;
- 선택된 최소 점수는 소수점 여섯 자리로 올림;
- 올림 처리 후 전체 모집단의 최종 지표를 다시 계산;
- 엄격 프로필은 적대적인 ±1e-6 점수·마진 교란에도 정확도 85% 이상, 유사 도메인 거부율 97% 이상, 잘못된 경로 1% 이하를 유지해야 함;
- ±1e-5는 보조 스트레스 진단으로 보존.

This experiment is diagnostic only. Even a passing map requires a separate frozen executable confirmation before any calibration or blind evaluation.


## 28. Late-stage strict-base, stability, and rescue results

Sections 26–27 described #255/#256 while they were still active. Their terminal results, and the numerically robust successor base, are recorded here so the paper/research narrative has an unambiguous current state.

### #255 — zero-additional-false cross-encoder rescue

작업 항목 #255 / PR #258에서는 엄격한 BGE-M3 0.55/0.45 기준선을 변경하지 않고, 기준선이 기권한 경우에만 고정된 BGE 리랭커를 호출했습니다.

추가 오탐 경로 0개를 요구한 1차 결과:

- 기준선: **965/1152 = 83.77%** 지원 요청 정확 선택
- 기준선 false route: **6/648 = 0.93%**
- 추가로 올바르게 복구한 지원 사례: **5개**
- 추가 false route: **0개**
- 결합된 정확 선택: **970/1152 = 84.20%**
- 근접 도메인 거부율: **98.96%** 유지
- 결합 평균/p95 지연 시간: **301.05 / 473.75 ms**

**결정: 기각.** 동일 승자에 적용한 크로스 인코더 복구는 안전했지만 목표인 85%를 넘기기 위해 필요했던 15개 사례 중 3분의 1인 5개만 복구했습니다.

출처:

- 워크플로: `36325681661`
- 아티팩트: `10934276251`
- 아티팩트 SHA-256: `a51ae289ed3dd4dd2e9bdb06bbf70e26f32f1df030a119feeb9883cd131b8e25`


### #256 — route-local stable fusion

작업 항목 #256 / PR #257에서는 사전 등록된 #246 그리드에서 선정한 route-local 스키마/행동 가중치를 동결하고, 실제 관찰 점수와 일치하는 임계 경계 대신 중간점과 올림한 임계값을 사용했습니다.

결과:

- 게이트 적용 전 지원 요청 정확 선택: **90.54%**
- 엄격한 예산 **6/648**:
  - 지원 요청 정확 선택: **963/1152 = 83.59%**
  - 근접 도메인 거부율: **98.96%**
  - false route: **0.93%**
- 2차 예산 **12/648**:
  - 지원 요청 정확 선택: **84.46%**
  - 근접 도메인 거부율: **97.92%**
  - false route: **1.85%**
- 적대적 수치 안정성 진단 **±1e-6**, **±1e-5**에서도 엄격 기준 지표 변화 없음
- 평균/p95 지연 시간: **180.50 / 197.16 ms**

**결정: 기각.** Route-local fusion을 통해 90% 이상의 순위화 성능 여유는 확인했지만, open-set 허용 경계 때문에 false route 1% 이하 제약에서 정확 선택률 85% 이상을 달성하지 못했습니다.

출처:

- 워크플로: `36325721448`
- 아티팩트: `10933809684`
- 아티팩트 SHA-256: `ca4df26ba5307b8e5aad22e2443f9e69713428b0898303939d8fd1cba3d443c0`


### #259 — numerically robust frozen BGE-M3 base

실패한 #245 확인 평가에서는 실제 관찰 점수와 같은 리터럴 임계값이 런타임 편차 약 **1.35e-7**만으로도 한 사례의 결과를 뒤집을 수 있음을 확인했습니다.

작업 항목 #259 / PR #260에서는 실행 전에 다음 항목을 동결했습니다.

- BGE-M3 리비전 `5617a9f...`
- 스키마/행동 융합 가중치 **0.55 / 0.45**
- #246의 엄격한 예산 6에 따른 route-local 임계값
- 승자 전용 rank-then-gate
- rank-2 후순위 대체(fallthrough) 금지
- 비교 허용오차(epsilon) **1e-6**:
  - `top_score + epsilon >= min_score`
  - `top_margin + epsilon >= min_margin`

실행 확인 평가는 다음 결과로 통과했습니다.

- 지원 요청 정확 선택: **83.7674%**
- 근접 도메인 거부율: **98.9583%**
- OOD 거부율: **100%**
- false route: **6/648 = 0.9259%**
- 무효 계획 / 실행 오류 / rank-2 후순위 대체: **0 / 0 / 0**
- planner와 직접 실행 간 결과 불일치: **0 / 1800**
- planner 평균/p95 지연 시간: **118.26 / 134.95 ms**

**결정: 후속 조건부 복구 실험을 위한 수치적으로 안정적인 엄격 기준선으로 확인.** 이는 개발 단계의 확인 결과일 뿐 독립적 일반화 근거는 아닙니다.

출처:

- 소스 리비전: `9e9b1049eac779adbc5781bfc45a447966ae32e8`
- 워크플로: `36325967632`
- 아티팩트: `10934635124`
- 아티팩트 SHA-256: `aabe4321e039dbb2e0b0805553e4dfd7d6c4bcf63893e23da028ceb668608462`


### #262 — cross-model zero-false abstention rescue

작업 항목 #262 / PR #263은 당시 진행 중이었던 개발 단계(DEV) 진단 실험입니다.

#259 기준선은 변경하지 않았습니다. 복구(rescue)는 기준선이 실행을 기권한 경우에만 가능하며, BGE-M3의 원시 1순위 경로와 **같은 경로**만 복구할 수 있습니다. 2순위 경로를 선택하거나 실행 권한을 변경할 수 없습니다.

사전 등록한 비교 조건은 두 가지였습니다.

1. **GTE 일치 조건:** GTE의 0.25/0.75 가중치 기반 1순위 경로가 동결된 BGE-M3 원시 1순위 경로와 일치해야 복구할 수 있습니다.
2. **GTE 일치 + BGE 리랭커:** 같은 일치 조건에, 1순위 승자만 평가하는 고정 크로스 인코더 점수를 추가합니다.

1차 복구 안전 예산은 **추가 false route 0개**입니다.

목표:

- 결합된 지원 요청 정확 선택률 85% 이상
- 근접 도메인 거부율 97% 이상
- 전체 false route 1% 이하
- 추가 false route **0개**

당시 실행한 워크플로는 `36326745694`입니다. Calibration 및 blind 평가 근거는 소비하지 않았습니다.


## 29. 당시 resume point

당시 canonical state는 다음과 같습니다:

1. #259는 견고성이 확인된 엄격한 기준 모델;
2. #255와 #256은 종료된 부정적 결과;
3. #262만 현재 활성 품질 개선 실험;
4. #198 보정·블라인드 확인은 여전히 차단됨;
5. #262가 통과하면 새로운 확인 전에 정확한 복구 프로필을 별도 실행 가능 후보로 동결;
6. #262가 실패하면 정확도 85%를 맞추려고 잘못된 경로 1% 이하 경계를 완화하지 않음.

The architectural invariant remains:

> Semantic model은 locally registered authority 안에서만 rank, reject 또는 rescue할 수 있으며 execution authority를 만들지 않습니다.


## 30. Cross-model rescue, fresh-surface failure, and typed open-set evidence

### #262 — cross-model zero-false abstention rescue

확인된 #259 BGE-M3 엄격 기준선에서 출발했습니다. #262는 복구 권한을 기준선이 기권한 사례로 제한하고 동일한 원시 BGE-M3 승자를 유지했습니다.

사전 등록한 두 조건:

1. GTE 0.25/0.75 이중 관점의 1순위 경로가 동결된 BGE-M3 원시 1순위와 일치해야 합니다.
2. 위 일치 조건에 더해, 승자 전용 BGE 리랭커 점수를 사용합니다.

GTE만 사용한 조건은 추가 false route 없이 지원 요청에서 올바른 사례 **12개**를 복구하여 **977/1152 = 84.81%**의 정확 선택률에 도달했습니다.

GTE + 승자 전용 리랭커 조건은 올바른 지원 사례 **17개**를 복구했으며, 잘못 복구한 지원 사례와 추가 false route 모두 **0개**였습니다.

- 지원 요청 정확 선택: **982/1152 = 85.2431%**
- 근접 도메인 거부율: **98.9583%**
- OOD 거부율: **100%**
- 전체 false route: **6/648 = 0.9259%**

**결정:** 교차 모델 조건은 튜닝 DEV의 모든 목표를 넘었으며, 별도로 동결하여 실제 실행 환경에서 확인할 후보로 선정했습니다.


### #265 / PR #270 — frozen candidate and fresh-surface confirmation

#262에서 선택된 후보는 확인 평가 전에 다음 조건으로 동결했습니다.

- 변경 불가능한 #259 BGE-M3 기준선
- 동일 승자에 대한 GTE 일치 조건
- 복구를 허용한 경로는 **8개**로 제한
- 양수 리랭커 임계값을 요구하는 **4개 경로**에서만 고정 BGE 리랭커 사용
- 전역 비교 허용오차 epsilon **1e-6**
- 2순위 폴백 및 경로 실행 권한 확장 금지

동일 코퍼스의 실행 확인은 동결된 DEV 예상 결과를 정확하게 재현했습니다.

- 정확 선택률: **85.2431%**
- 근접 도메인 거부율: **98.9583%**
- false route: **0.9259%**
- Planner/직접 실행 불일치: **0**
- GTE 호출 비율: **28.17%**
- 리랭커 호출 비율: **4.28%**
- Planner p95 지연: **239.32 ms**

사전 등록한 두 번째 단계에서는 기존 사례와 하나도 겹치지 않는 결정론적 새 표면(fresh-surface) DEV 코퍼스를 사용했습니다.

결과:

- 지원 요청 정확 선택률: **86.7188%**
- 근접 도메인 거부율: **77.7778%**
- false route: **128/648 = 19.7531%**
- 복구 전 기준선 false route: **122개**
- 복구로 추가된 false route: **6개**
- Planner/직접 실행 불일치: **0**
- 무효 계획 / 실행 오류: **0 / 0**

**결정: 기각.**

이는 후기 연구의 핵심 부정적 결과입니다.

> 경로 순위화 능력은 새로운 요청 표현으로 일반화되었지만, 양수 경로 점수를 이용한 open-set 허용 경계는 일반화되지 않았습니다.

이 실패한 새 표면 코퍼스는 확인 단계 전용 근거입니다. 임계값이나 행별 규칙을 다시 튜닝하는 데 **영구적으로 사용하지 않습니다**.


## 31. #273 — contradiction-only multilingual NLI veto

긍정적 경로 점수의 보정을 피하기 위해 #273은 경로별 긍정 승인 임계값을 제거하고 BGE-M3의 원시 Top-1만 경로 권한으로 사용했습니다. 다국어 NLI 모델에는 모순 확률이 사전등록된 전역 임계값을 초과할 때 승자를 거부하는 권한만 부여했습니다.

Runtime remained practical:

- BGE-M3 ranking mean/p95: 151.15 / 177.15 ms;
- NLI single-pair mean/p95: 14.13 / 15.29 ms;
- sequential mean/p95: 165.28 / 192.02 ms.

However, both supported and unsupported pairs were overwhelmingly classified as neutral, not contradiction.

Correct-supported winners:

- contradiction median: 0.1034;
- neutral median: 0.8432.

Near-domain unsupported:

- contradiction median: 0.0876;
- neutral median: 0.8627.

No preregistered contradiction threshold reached the 85/97/1 target.

Decision: rejected.

해석: generic textual contradiction은 registered operation capability의 부재와 동일하지 않습니다. Open-set rejection에는 explicit negative-capability semantics가 필요합니다.

## 32. #275 — explicit negative-capability prototype veto

#275에서는 도구 도메인마다 4개씩 총 **32개**의 명시적인 미지원 행동 프로토타입을 추가했습니다. 경로 실행 권한의 유일한 기준은 여전히 원시 BGE-M3 등록 1순위입니다.

사전 등록한 **588개** 조합에서 다음 요소를 평가했습니다.

- 승자 도메인의 최소 유사도
- 선택적 승자/최상위 도메인 일치 조건
- 부정 프로토타입의 최소 유사도
- 행동에 대한 부정 증거의 우위 점수

원시 BGE-M3의 지원 요청 1순위 정확도는 **88.45%**, p95 지연은 **139.79 ms**로 유지되었습니다.

명시적 부정 증거는 실제로 의미적 분리 신호를 제공했습니다.

- 올바른 지원 사례의 부정 우위 점수 중앙값: **-0.0935**
- 근접 도메인 미지원 사례의 중앙값: **+0.1708**

그러나 모든 승격 기준을 만족하는 규칙은 없었습니다.

주된 실패 원인은 부정 기능 신호 자체가 아니었습니다. OOD를 100% 거부하려면 승자 도메인의 절대 점수에 대한 단일 거부 규칙이 필요했지만, 그러면 원래 올바르던 지원 요청의 낮은 점수 구간까지 제거되어 재현율이 지나치게 떨어졌습니다.

**결정: 결합 구조는 기각하고 부정 기능 신호의 발견은 유지합니다.**

구조를 다음 세 부분으로 나누어야 한다는 결론을 얻었습니다.

1. 경로 순위화
2. 근접 도메인의 부정 기능 거부
3. OOD 소속 여부 판단

이 셋을 하나의 경로별 양수 임계값에 합쳐서는 안 됩니다.


## 33. #266 and #271 — rejected rescue ablations

Two additional abstention-rescue ablations confirmed that the remaining gap was not easily recoverable from the existing strict base.

### #266 — robust-base same-winner cross-encoder rescue

- base abstentions: 767;
- correct-winner headroom: 54;
- zero-additional-false rescues: 5;
- composed exact: 84.20%;
- composed p95: 472.69 ms.

Decision: rejected.

### #271 — native BGE-M3 abstention geometry

Using only existing BGE-M3 score/margin/agreement geometry:

- zero-additional-false rescues: 4;
- composed exact: 84.11%;
- near-domain rejection: 98.96%;
- false-route: 0.93%.

Decision: rejected.

이 ablation들은 open-set architecture를 strict-base rescue에서 explicit typed capability evidence 쪽으로 이동해야 한다는 근거를 제공합니다.

## 34. #277 — global signed capability bank

작업 항목 #277 / PR #278에서는 경로별 양수 허용 임계값을 제거하고, 전역적으로 부호를 가진 기능 공간(global signed capability space)을 평가했습니다.

- 등록된 양수 작업 프로토타입: **16개**
- 명시적인 미지원 부정 프로토타입: **32개**
- 경로 실행 권한의 유일한 기준: BGE-M3 원시 등록 1순위
- OOD에 대한 낮은 기능 영역(envelope) 거부 규칙
- 근접 도메인 미지원 요청에 대한 부정-양수 우위 점수
- 선택적인 양수 점수와 원시 승자의 일치 조건은 거부(veto)에만 사용

사전 등록해 고정한 그리드는 **504개 규칙**이었습니다.

결과:

- 원시 지원 요청 1순위 정확도: **88.4549%**
- 평균 / p95 지연: **157.09 / 181.00 ms**
- 승격 기준을 통과한 규칙: **0개**

false route 1% 이하 및 OOD 거부율 100%를 동시에 보존하면서 가장 근접한 규칙은 다음과 같았습니다.

- 규칙: `e0.450-n0.350-a+0.050-noagree`
- 지원 요청 정확 선택: **81.8576%**
- 근접 도메인 거부율: **98.9583%**
- false route: **6/648 = 0.9259%**
- 잘못 거부된 원래 올바른 지원 승자: **76개**

**결정: 기각.**

> 전역 부호형 기능 은행은 안전성 경계를 강제할 수 있지만, 근거의 해상도가 너무 낮아 올바른 지원 요청의 승자를 과도하게 제거합니다.

#275에서 도출한 책임 분리를 강화하는 결과입니다. 경로 조건에 따른 명시적 부정 기능 증거는 근접 도메인의 미지원 행동 판별에 유용하지만, OOD 소속 판별은 낮은 양수·도메인 점수에 의존하지 않는 별도 신호가 필요합니다.

출처:

- 워크플로: `36356550905`
- 아티팩트: `10944407595`
- 아티팩트 SHA-256: `00eb49f680d7b1bdfa8c341c2f091c641e4912ca94c9f0bc81815db3e70b3643`


## 35. #279 — dual signed negative open-world detector

Work item #279 / PR #280 separated near-domain and OOD veto evidence while keeping BGE-M3 raw top-1 as the only route authority.

### Near-domain channel

- route-conditioned explicit unsupported-action prototypes from #275;
- maximum negative score;
- negative-over-raw-winner-action signed advantage.

### OOD channel

- 등록된 도메인 앵커: **8개**
- 넓은 배경 도메인 프로토타입: **16개**
- 최대 배경 점수
- 배경 점수에서 알려진 도메인 점수를 뺀 부호형 우위 점수

낮은 양수 점수 또는 경로별 양수 허용 임계값은 사용하지 않았습니다.

사전 등록해 고정한 그리드는 **1,764개 규칙**이었습니다.

결과:

- 원시 지원 요청 1순위 정확도: **88.4549%**
- 평균 / p95 지연: **183.79 / 200.07 ms**
- 승격 기준 통과 규칙: **0개**

이 절충은 단일 부호형 점수의 구조적 한계를 보여 주었습니다.

- 지원 요청 정확 선택률 85% 이상을 보존한 최상위 규칙:
  - 정확 선택률 **85.8507%**
  - 근접 도메인 거부율 **86.8056%**
  - OOD 거부율 **69.4444%**
  - false route **98/648 = 15.1235%**
- 근접 도메인 거부율 97% 이상 및 OOD 거부율 100%를 만족한 최상위 규칙:
  - 정확 선택률 **65.3646%**
  - false route **15/648 = 2.3148%**
- OOD 거부율 100% 및 false route 1% 이하를 만족한 최상위 규칙:
  - 정확 선택률 **36.0243%**
  - 근접 도메인 거부율 **99.4792%**
  - false route **3/648 = 0.4630%**

배경 점수와 알려진 도메인 점수 사이의 우위 점수 분포는 0 근처에서 겹쳤습니다.

- 올바른 지원 사례: 중앙값 **-0.0890**, p95 **-0.0040**, 최대 **+0.0714**
- OOD 사례: 중앙값 **+0.0418**, p05 **-0.0212**, 최소 **-0.0359**

**결정: 기각.**

이 결과로 고정된 프로토타입 계열에 대한 스칼라 임계값 탐색 방향은 종료합니다. 임계값만 더 촘촘히 탐색하면 분포가 겹치는 영역 안에서 튜닝할 뿐 open-set 표현 자체의 문제를 해결하지 못합니다.

출처:

- 워크플로: `36358352642`
- 아티팩트: `10944663761`
- 아티팩트 SHA-256: `f04242ac79d22b35f29486b9f3b94b3ce1603400bfc87382ec73a412905cea83`


## 36. #281 — rank-based capability-set open-world veto

Work item #281 / PR #283 tested the final preregistered fixed-prototype heuristic family using only relative prototype ordering, with no scalar similarity threshold.

The route authority remained unchanged:

- BGE-M3 raw registered global top-1;
- no positive acceptance threshold;
- no rank-2 fallback;
- no pseudo-route;
- capability evidence could veto only.

### Near-domain local set

Within the raw winner domain, the experiment ranked:

- registered positive endpoint capability prototypes;
- four frozen explicit unsupported-action prototypes.

Five fixed near-domain veto modes covered local top-1/top-k negative composition and whether the best negative outranked the raw-route positive prototype.

### OOD global membership set

The experiment ranked:

- eight registered domain anchors;
- sixteen frozen broad background-domain prototypes.

Four fixed OOD modes covered background composition in top-1, top-2, top-3 and top-5.

The Cartesian product contained 20 fixed rules.

### Result

- 원시 BGE-M3의 지원 사례 Top-1: 1019/1152 = 88.4549%;
- 질의 점수 계산 평균 / p95 지연시간: 185.41 / 200.66 ms;
- 권한 위반 / 실행 오류: 0 / 0;
- 승격 게이트 통과 규칙: 0건;
- 전체 잘못된 경로 비율 1% 이하 규칙: 0건;
- 지원 사례 정확도 85% 이상 규칙: 0건.

Best supported-exact rule:

- `negative_top2_all__background_top2_all`;
- supported exact: 78.8194%;
- near-domain rejection: 81.9444%;
- OOD rejection: 83.3333%;
- false-route: 116/648 = 17.9012%.

Closest high-rejection rule:

- `negative_top1__background_top3_majority`;
- supported exact: 50.3472%;
- near-domain rejection: 98.2639%;
- OOD rejection: 100%;
- false-route: 10/648 = 1.5432%.

The rank geometry still contains useful semantic signal:

- 정답인 지원 사례의 로컬 Top-1 음성 판정률: 21.20%;
- 유사 도메인 미지원 사례의 로컬 Top-1 음성 판정률: 96.88%;
- 정답인 지원 사례의 소속 판단 Top-1 배경 판정률: 4.32%;
- OOD 소속 판단 Top-1 배경 판정률: 81.94%.

하지만 두 channel을 합성하면 85/97/1/100 target을 만족하기에는 overlap이 여전히 너무 큽니다. Top-k composition is additionally sensitive to prototype-bank cardinality (8 known anchors vs 16 background anchors).

Decision: reject했습니다. 이 capability-bank family에 대한 fixed-prototype heuristic refinement를 종료합니다.

이에 따라 #281에서 preregister한 stopping rule이 발동됩니다. Do not continue with finer scalar thresholds, larger top-k grids, route-specific exceptions or post-result hand rules. The next architecture must use a learned or externally pretrained open-set capability verifier/classifier under strict veto-only authority.

Provenance:

- source revision: `944df2e0f2dc8617e7b97e6a38d4e2f5684f5324`;
- workflow: `36359121048`;
- artifact: `10945431360`;
- artifact digest: `sha256:9d7fcfb8bff361137216c3bdc6182c5bb5cef50f2eee4d2f65e32711fff95b13`.

실패한 #270 fresh-surface corpus는 confirmation-only 상태이며 tuning에 사용할 수 없습니다. Calibration/blind evidence는 untouched 상태를 유지합니다.

## 37. 당시 resume point

당시 0.11 research state는 다음과 같습니다:

1. BGE-M3의 원시 경로 순위 능력은 충분함(튜닝 DEV에서 88.45%, #270의 새로운 지원 사례 순위도 85% 초과);
2. 확인된 엄격한 긍정 점수 임계값 기준은 기존 DEV에서 안전하지만 다른 데이터 표면에 견고하지 않음;
3. 일반적인 모순 NLI는 기능 부재를 표현하지 못함;
4. 고정 긍정·음성·배경 프로토타입 뱅크에는 신호가 있지만 스칼라·상대 순위 휴리스틱만으로 정확도 85% 이상 / 유사 도메인 거부율 97% 이상 / OOD 100% / 잘못된 경로 1% 이하를 동시에 충족하지 못함;
5. 고정 프로토타입 휴리스틱 개선은 종료;
6. #198 보정·블라인드 확인은 계속 차단;
7. 다음 동작 변경 실험은 원시 등록 승자를 거부할 수는 있으나 다른 경로를 만들거나 실행 권한을 부여할 수는 없는, 학습 또는 외부 사전학습 기반 `match / no_match / unknown` 검증기를 시험해야 함.

The architectural invariant remains:

> Semantic models may rank or veto only among locally registered authority. They do not create execution authority.

## 38. #285 — grouped-OOF learned winner verifier

Work item #285 / PR #286 tested the first learned open-set boundary after the fixed-prototype stopping rule.

The learned component was not a router. BGE-M3 raw registered global top-1 remained the sole route authority. The verifier could only output:

- `match` — permit the already-selected raw winner;
- `no_match` — abstain;
- `unknown` — abstain.

No rank-2 fallback, route switching, pseudo-route, or semantic authority creation was allowed.

### Evaluation protocol

To reduce surface memorization, the experiment used six-fold leave-one-language-out OOF over:

- de;
- en;
- es;
- ja;
- ko;
- mixed.

Language was a grouping variable only and was forbidden as a model feature.

The fixed feature schema contained:

- 19 runtime-observable BGE/prototype geometry values;
- one-hot raw winner route ID.

Forbidden classifier features included query text, benchmark IDs, expected route, category, language and unsupported-family labels.

Exactly two classifier families and twelve thresholds were preregistered, for 24 fixed rules:

- regularized logistic regression;
- shallow regularized histogram gradient boosting;
- thresholds from 0.50 to 0.995.

### Result

Three preregistered rules passed the full 85/97/1/100 DEV target under grouped OOF.

Selected rule by preregistered ordering:

- HGB @ p_match >= 0.50;
- 지원 사례 정확도: 1000/1152 = 86.8056%;
- 유사 도메인 거부율: 573/576 = 99.4792%;
- OOD 거부율: 72/72 = 100%;
- 잘못된 경로: 3/648 = 0.4630%;
- 결합 평균 / p95 지연시간: 158.02 / 171.76 ms;
- 권한 위반 / 오류: 0 / 0.

Verifier discrimination:

- logistic ROC-AUC: 0.98803;
- logistic average precision: 0.98871;
- HGB ROC-AUC: 0.98797;
- HGB average precision: 0.98902.

Per-language supported exact for the selected held-out predictions ranged from:

- 81.77% on de;
- to 91.15% on mixed.

Per-language unsupported rejection remained approximately 99.07–100%.

Decision: promote HGB p=0.50 to a separate frozen candidate.

이는 query-text feature나 benchmark label 없이 grouped OOF protocol에서 long-term target을 통과한 최초의 0.11 open-set design입니다.

Provenance:

- workflow: `36360129634`;
- source revision: `cfaafb84bb651a6d6d38c4ce741f05ac61f37e9e`;
- artifact: `10945581502`;
- artifact digest: `sha256:eb417bb3aafa4d2f86aee4e79476ea64f49a2a3608269835d4d3b82f971d8054`.

## 39. #287 — frozen HGB winner verifier

Work item #287 / PR #288 froze the #285-selected HGB verifier without changing classifier, features or threshold after OOF results were known.

### Freeze contract

- 분류기: `HistGradientBoostingClassifier`;
- 임계값: 0.50;
- scikit-learn: 1.7.2;
- 기존 튜닝 DEV 전체 1,800행에 정확히 한 번 학습;
- 하나의 joblib 파일로 직렬화;
- 확인 전에 SHA-256 고정;
- 동일한 직렬화 모델을 동일 코퍼스와 새로운 표면의 평가에 재사용;
- 어느 확인 단계에서도 재학습하지 않음;
- 원시 BGE-M3 등록 Top-1만 경로 선택 권한을 보유.

Frozen model SHA-256:

`8cdb8b526705482d2a51dee79f8f17ce10e19199e823cab651a434918c8aa239`

### Same-corpus executable confirmation — PASS

- supported exact: 1010/1152 = 87.6736%;
- near-domain rejection: 575/576 = 99.8264%;
- OOD rejection: 72/72 = 100%;
- false-route: 1/648 = 0.1543%;
- combined p95: 221.33 ms;
- authority violations / errors: 0 / 0.

이는 frozen implementation을 confirm한 것이며 independent generalization evidence는 아닙니다.

### New zero-overlap fresh-surface DEV — FAIL

Fresh corpus:

- 시드: `operation-routing-quality-v4-learned-verifier-confirmation-2026-09-28-a`;
- 데이터 표면 버전: `learned-verifier-confirmation-wrappers-v1`;
- 코퍼스 SHA-256: `c08068e7c68d466b04c96433abd17a6b5da62eaa47969b536f8551ed9db201c6`;
- 원래 튜닝 DEV와 정규화된 정확 일치 중복: 0건;
- 실패한 #270 시드·표면과 서로 다름: 예;
- 실패한 #270 산출물 읽기·사용: 아니요.

Fresh result:

- supported exact: 952/1152 = 82.6389%;
- near-domain rejection: 537/576 = 93.2292%;
- OOD rejection: 72/72 = 100%;
- false-route: 39/648 = 6.0185%;
- combined p95: 252.77 ms;
- authority violations / errors: 0 / 0.

언어별 지원 사례 정확도는 독일어 75.00%부터 혼합 언어 89.06%까지 분포했습니다. 미지원 사례 집단에서 가장 낮은 거부율은 `support.family_1`의 27.78%였습니다. 그러나 이 확인 집합은 튜닝용 근거가 아니므로 특정 오류만 겨냥한 수리에 사용할 수 없습니다.

Decision: rejected.

Interpretation:

> Grouped OOF validation은 일반적인 random-split leakage를 줄였지만 learned geometry boundary는 충분히 invariant한 endpoint capability semantics가 아니라 development-surface regularity를 포착했습니다.

The #287 stopping rule is active:

- 새 데이터 집합에서 임계값을 튜닝하지 않음;
- 경로·집단별 예외를 추가하지 않음;
- 동일한 튜닝 DEV에서 학습 모델의 복잡도를 늘리거나 재학습하지 않음;
- 새로운 확인 데이터나 오류를 학습 또는 특징 설계 근거로 사용하지 않음;
- 보정·블라인드 근거를 생성하지 않음.

Provenance:

- source revision: `e5b10ee01ec23af6113c562b51e1db0c6d003d7a`;
- workflow: `36362105765`;
- artifact: `10946681188`;
- artifact digest: `sha256:e7695598b07d5a0f9757f62c04f74f09b03c201de2bbb3f7699f6d8f18059938`.

## 40. Resume checkpoint after #287

The 0.11 architecture-search evidence now supports a stronger conclusion:

1. BGE-M3의 원시 경로 순위 능력은 충분함;
2. 긍정 점수 게이트는 데이터 표면 변화에 취약함;
3. 범용 모순 NLI는 기능의 부재를 나타내지 못함;
4. 고정 의미 프로토타입의 임계값과 상대 순위로는 안전한 개방 집합 경계를 만들지 못함;
5. 얕은 학습 검증기는 그룹별 OOF를 통과할 수 있어도 중복이 없는 새 표면 확인에서 실패함;
6. 사전등록된 중단 규칙에 따라 동일 DEV 기하학 위에서 지도학습 복잡도를 추가하는 것은 금지됨;
7. #198 보정·블라인드는 여전히 차단 상태로 유지됨;
8. 다음 아키텍처는 벤치마크와 독립적으로 학습한 외부 사전학습 의미 기반 기능 검증기를 사용해야 함.

Authority invariant는 변하지 않습니다:

> External semantic evidence는 locally registered raw winner를 veto할 수 있지만 다른 route를 선택하거나 execution authority를 만들 수는 없습니다.


## 41. System One provider abstraction and direct Laya routing

After #287 closed learned development-geometry refinement, the research line moved to externally
pretrained typed decision models rather than training another classifier on the same 1,800-row DEV
surface.

### Provider infrastructure — #291 / PR #292

SchemaRouter already had direct `JevDecisionBackend` and `LayaDecisionBackend` integrations.
#291 generalized the Jev-compatible wire boundary instead of adding one class per new model family.

PR #292 merged a generic `SystemOneDecisionBackend` to main:

- 호환 가능한 제공자는 `base_url`, `model`, `provider_name`으로 설정;
- 제공자는 로컬에서 허용된 유한한 선택지 ID만 전달받음;
- 반환 ID는 신뢰도 처리 전에 로컬에서 재검증;
- 잘못된 형식 또는 유한하지 않은 신뢰도는 안전하게 거부;
- `DecisionOption.metadata`와 인증정보는 모델의 결정 상태로 전달하지 않음;
- `JevDecisionBackend`는 얇은 특화 계층으로 이전 버전과 호환성을 유지;
- 호환 제공자는 엔드포인트·필드·인수·정책·실행 권한을 생성할 수 없음.

벤치마크 측의 동반 작업인 #297 / PR #298도 `main`에 병합되어, 공유 결정 라우팅 벤치마크가 System One 호환 제공자에 대해 모델 중립적으로 동작하게 됐습니다. 이제 새로운 호환 모델은 코드를 다시 수정하지 않고 설정만으로 벤치마크할 수 있습니다.

### Direct full-catalog Laya — #293 / PR #294

A preregistered direct-routing diagnostic then tested whether Laya itself could replace the BGE route
authority over all 16 registered endpoints.

Protocol:

- `laya==0.3.11`;
- CPU 실행;
- 영어·다국어 체크포인트 자동 라우팅;
- 사전 로드 활성화, max_loaded=2;
- 전체 16개 경로 카탈로그;
- BGE 검색 사용하지 않음;
- 고정된 신뢰도 임계값 8개;
- 실패한 #270/#287의 새로운 데이터 표면 제외.

Result:

- 원시 지원 사례 Top-1: 692/1152 = 60.0694%;
- 통과 규칙: 0/8;
- p>=0.50: 정확도 57.2917% / 유사 도메인 거부율 27.0833% / OOD 51.3889% / 잘못된 경로 70.2160%;
- p>=0.995: 정확도 24.0451% / 유사 도메인 거부율 77.6042% / OOD 97.2222% / 잘못된 경로 20.2160%;
- 평균 / p95 지연시간: 657.73 / 1041.43 ms;
- 오류 / 권한 위반: 0 / 0.

Raw supported top-1 by language:

- de 48.9583%;
- en 87.5000%;
- es 63.5417%;
- ja 55.2083%;
- ko 40.1042%;
- mixed 65.1042%.

Confidence did not solve the open-set boundary. Mean confidence was 0.8881 for correct supported
choices, 0.7087 for wrong supported choices, and 0.7132 for near-domain unsupported requests.

Decision: reject direct full-catalog Laya route authority. PR #294 was closed unmerged.

Provenance:

- source revision: `48e329ee949d0d7a42d93a7c06c7ecbc62edfedc`;
- workflow: `36365434284`;
- artifact: `10947876029`;
- artifact digest: `sha256:f361f12844cf1da0374ba345051f9c35a0f50c2735c5e7fc9f2b6dbe62d39add`.

이 negative result가 Laya를 veto signal로서 reject하는 것은 아닙니다. Laya의 native `noul` primitive는 16-way route choice와 다른 semantic question입니다.

## 42. Current resume point — external typed capability boundaries

Calibration/blind는 blocked 및 untouched 상태를 유지합니다.

Active experiments:

1. #289 / PR #290 — Qwen3 외부 의미 기반 기능 검증기
   - 변경할 수 없는 BGE-M3 원시 Top-1 경로 선택 권한;
   - Qwen3-Reranker-0.6B는 거부권만 보유;
   - SchemaRouter 데이터로 검증기를 학습하지 않음;
   - 고정된 yes 확률 임계값 8개.

2. #299 / PR #300 — 고정된 Kev-0.8B의 choice + noul
   - 고정된 Kev 소스 및 Hub 모델 리비전;
   - 등록된 경로 16개만 허용;
   - 단일 요청에 네이티브 System One `choice` 및 `noul` 사용;
   - 선택 신뢰도와 noul 기능 판단에 대한 별도의 고정 규칙군.

3. #301 / PR #302 — 고정된 Laya noul 거부권
   - BGE-M3 원시 등록 Top-1만 경로를 선택할 수 있음;
   - Laya는 해당 승자에 대한 네이티브 `P(true)` 기능 근거만 반환 가능;
   - `laya==0.3.11`;
   - 정확한 Hub 계열 리비전 `458d7563c5cab85ff9f7f6e06cf2dd166fb697e2`;
   - 워크플로가 모델을 구성하기 전에 불변 Hub 스냅샷을 로컬에 준비;
   - 고정 전역 `P(true)` 임계값 8개.

당시 architectural hypothesis는 다음처럼 더 좁아졌습니다:

> 경로 순위 결정과 개방 집합 기능 승인 여부는 별개의 문제로 유지해야 합니다. 등록된 경로를 구별하는 고용량 순위 결정은 BGE-M3가 담당하되, 외부에서 사전학습한 타입 기반 결정 모델은 교체 가능한 기능 경계로 평가합니다. 제공자가 `choice`를 지원한다는 이유만으로 직접적인 경로 선택 권한을 인정하지는 않습니다.

System One wire compatibility는 infrastructure이지 quality evidence가 아닙니다. Every model/checkpoint still
requires the same frozen v4 gate and, if promoted, a new zero-overlap fresh-surface confirmation.

## 43. #289 / PR #290 — external Qwen3 capability verifier

The first externally pretrained reranker-as-capability-verifier experiment is terminal and rejected.

동결된 프로토콜:
- BGE-M3 원시 등록 Top-1만 경로 선택 권한을 보유;
- 검증기: 리비전 `e61197ed45024b0ed8a2d74b80b4d909f1255473`의 `Qwen/Qwen3-Reranker-0.6B`;
- SchemaRouter 데이터로 검증기 학습 없음;
- 하나의 고정 기능 지시문 사용;
- 전역 yes 확률 임계값 8개;
- 검증기는 거부만 가능;
- 실패한 #270/#287의 새로운 집합, 보정·블라인드 근거는 제외.

결과:
- 원시 BGE의 지원 사례 Top-1: 88.4549%;
- 통과 규칙: 0/8;
- p=0.50: 정확도 82.8993% / 유사 도메인 거부율 77.9514% / OOD 97.2222% / 잘못된 경로 19.9074%;
- p=0.98: 정확도 68.7500% / 유사 도메인 거부율 97.3958% / OOD 100% / 잘못된 경로 2.3148%;
- p=0.99: 정확도 62.7604% / 유사 도메인 거부율 99.1319% / OOD 100% / 잘못된 경로 0.7716%;
- p=0.995: 정확도 52.7778% / 유사 도메인 거부율 100% / OOD 100% / 잘못된 경로 0%.

Mean verifier P(yes):
- correct supported winner: 0.9266;
- wrong supported winner: 0.6271;
- near unsupported: 0.2325;
- OOD: 0.0417.

Semantic signal은 실제로 존재하지만 upper tail overlap이 너무 커 하나의 안전한 global boundary를 만들 수 없습니다.

Runtime:
- Qwen single-request p95: 1864.44 ms;
- combined BGE + Qwen p95: 2059.42 ms;
- errors / authority violations: 0 / 0.

Decision: direct generic reranker yes/no gating을 reject합니다. Quality가 실패했으므로 runtime optimization으로 이를 rescue할 수 없습니다.

출처 추적:
- 소스 리비전: `68e812ab5c72bd42664e21f8c9f62a760465cb03`;
- 워크플로: `36363863046`;
- 산출물: `10947604859`;
- 산출물 다이제스트: `sha256:4e89707dce04d37aece8e803e00751ea86fdd12e5fd9282531ccecc830a9c96c`.

The active external typed-decision paths are now #299 (Kev) and #301 (pinned Laya native noul).
#303 remains a preregistered top-K provider-neutral contingency and is not active yet.

## 44. Replaceable typed-decision candidate registry

The fast-moving Jev/System One ecosystem is tracked separately from core product code in
`benchmarks/system-one-candidate-registry.json`.

레지스트리는 검색 후보마다 다음을 기록합니다.
- 저장소와 라이선스 상태;
- 전송 프로토콜 또는 호출 함수 연동 경로;
- 현재 벤치마크 상태;
- 모델 계열별 유의 사항;
- 동결된 승격 게이트와 신규 접수 점검표.

Current verified discovery entries include Laya, Kev, Decis, LiteVar System One, AnyJev,
Bespoke Nimble, and System One Open.

이 분리는 의도적입니다:

> Model discovery는 mutable research metadata이고 execution authority와 provider contract는 stable product interface입니다.

전송 규약이 호환되는 모델은 `SystemOneDecisionBackend`를 사용합니다. 그 외 타입 기반 모델은 먼저 `CallableDecisionBackend` / `--decision-callable`로 연결합니다. 새로운 모델을 시험한다는 이유만으로 코어에 모델 전용 연동을 영구적으로 추가할 필요는 없습니다.

이 정책을 지원하는 인프라는 다음과 같이 병합됐습니다.
- #291 / PR #292 — 범용 System One 백엔드;
- #297 / PR #298 — 범용 System One 벤치마크 CLI;
- #304 / PR #305 — 임의의 제한 결정 호출 함수를 벤치마크하는 경로. `c9678b95a6dc592a1c3b850a6aea8b1675ff94a4`로 병합;
- #306 / PR #308 — 재사용 가능한 타사 `schemarouter.decision_backends` 진입점의 검색·로드, 벤치마크 플러그인 선택, 보안 문서 및 후보 레지스트리 검증. `e782ebb87f80cdb2cefe5a716f77f546cd6309b1`로 스쿼시 병합.

최종 확장 계층 구조는 다음과 같습니다.
1. System One 전송 규약 호환 제공자 → `SystemOneDecisionBackend`;
2. 일회성 제한 연구 어댑터 → `CallableDecisionBackend`;
3. 재사용 가능한 비호환 연동 → 명시적인 타사 진입점 플러그인.

Discovery is metadata-only. Plugin code is imported only by exact trusted name; plugin execution is
not sandboxed, and local finite-option validation remains authoritative.

## 45. #301 / PR #302 — pinned Laya native noul veto

The winner-only Laya capability-boundary experiment is terminal and rejected.

동결된 프로토콜:
- BGE-M3 원시 등록 Top-1만 경로 선택 권한을 보유;
- Laya는 네이티브 `noul`을 통한 거부권만 행사;
- `laya==0.3.11`;
- 정확한 Hub 계열 리비전 `458d7563c5cab85ff9f7f6e06cf2dd166fb697e2`를 추론 전에 로컬에 준비;
- 고정 전역 P(true) 임계값 8개;
- 실패한 새로운 데이터 표면, 보정 및 블라인드 근거는 제외.

결과:
- 원시 BGE 지원 사례 Top-1: 88.4549%;
- 통과 규칙: 0/8;
- p=0.50: 정확도 83.2465% / 유사 도메인 거부율 7.9861% / OOD 8.3333% / 잘못된 경로 91.9753%;
- p=0.90: 정확도 5.2083% / 유사 도메인 거부율 95.4861% / OOD 91.6667% / 잘못된 경로 4.9383%;
- p=0.95: 정확도 1.5625% / 유사 도메인 거부율 99.4792% / OOD 100% / 잘못된 경로 0.4630%.

Mean P(true):
- correct supported BGE winner: 0.6842;
- wrong supported winner: 0.6214;
- near-domain unsupported: 0.6738;
- OOD: 0.7316.

OOD request가 correct supported traffic보다 평균적으로 더 capable하게 scoring되었으므로 현재 Laya base checkpoint는 이 workload에서 사용할 수 있는 capability-existence boundary를 제공하지 못합니다.

Runtime:
- BGE p95 200.21 ms;
- Laya single-request p95 906.09 ms;
- combined p95 1098.75 ms;
- errors / authority violations 0 / 0.

Provenance:
- source revision `46af3c3d0156b7b7bfd40686aa5639571f91a936`;
- workflow `36367249147`;
- artifact `10948736462`;
- artifact digest `sha256:5f7876d2c8e9c4a33eed62c05ba4df2889ad922322daeb5424d5f11bb18ec738`.

### Consequence for staged top-4 Laya

준비해 두었던 #310 브랜치도 같은 Laya P(true) 신호를 사용했습니다. 수동 연구 워크플로는 실행하지 않고 종료했습니다. 사전등록된 조건에서 정식 잘못된 경로 게이트를 처음 만족하는 승자 전용 임계값 p>=0.95를 적용하면, 원래 정답인 BGE 승자 1,019개 중 18개만 남습니다. 나머지 지원 사례 133개를 Top-4에서 모두 찾아 동일 임계값을 통과한다고 가정하는 불가능한 최선의 경우에도 정확도 상한은 151/1152 = 13.1076%입니다. 네 후보의 P(true) 최댓값을 사용해도 같은 임계값에서 승자 전용 후보보다 미지원 요청의 승인을 줄일 수는 없습니다.

#303 remains only as a provider-neutral top-K architecture contingency for a materially different
model/checkpoint. The only active model-quality experiment at this checkpoint is pinned Kev-0.8B
#299 / PR #300.

## 46. Current target-distance checkpoint — Kev active, AnyJev staged

The numeric 0.11 target remains:

- supported exact-route >= 85%;
- near-domain unsupported rejection >= 97%;
- OOD rejection = 100%;
- false-route <= 1%;
- authority violations / execution errors = 0;
- target p95 <= 250 ms.

중요한 구분은 다음과 같습니다:

> Target operating point 자체는 tuning/development surface에서 이미 반복해서 달성했습니다.
> 해결되지 않은 문제는 independent surface shift에서도 그 operating point를 보존하는 것입니다.

근거:
- 그룹별 OOF 및 동결된 학습 검증기는 DEV·동일 코퍼스에서 목표에 도달;
- #287의 새로운 확인에서는 정확도 82.64% / 유사 도메인 거부율 93.23% / 잘못된 경로 6.02%로 하락;
- 범용 Qwen3 기능 게이트(#289)와 고정된 Laya 네이티브 noul(#301) 모두 데이터 표면에 견고한 안전 경계를 제공하지 못함;
- Laya의 직접 경로 선택(#293)은 지원 사례 Top-1 60.07%로 능력의 한계가 드러남.

따라서 research problem은 더 이상 일반적인 route-ranking accuracy가 아닙니다. BGE-M3 already exposes
88.4549% raw supported top-1 capacity on the canonical DEV. The remaining bottleneck is a
replaceable open-set capability decision that can retain most of those correct winners while rejecting
unsupported requests with <=1% false routing.

### Active — #299 / PR #300 pinned Kev-0.8B

The only active model-quality run is Kev-0.8B native System One `choice+noul`.

Before inference:
- contracts passed;
- pinned Kev runtime installed;
- local server started successfully;
- canonical 1,800-case DEV SHA was verified;
- corpus audit passed.

The full 1,800-row typed-decision diagnostic is executing. No result-driven semantic changes are
permitted.

### Staged Kev composition — #314 / PR #315

A zero-new-inference Kev composition was preregistered before #299 result inspection.

- BGE-M3 원시 등록 Top-1만 경로 선택 권한을 유지;
- 동결된 #299의 정확한 `supported_probability`를 거부 전용 근거로 재사용;
- #299의 행별 Kev 요청 지연시간을 결합 지연시간 계산에 재사용;
- Kev의 경로 선택과 선택 신뢰도는 무시;
- 새로운 Kev 모델 호출은 금지;
- 고정 전역 임계값 8개 유지;
- 수동 워크플로는 정확한 #299 최종 산출물 ID가 필요하며 합성 전에 출처 실행·산출물 이름·사례 ID·확률·지연시간·실행 오류·권한 위반을 검증.

이는 learned component를 추가하지 않고 다음 research question을 분리해 검증합니다:

> if Kev's own 16-way route choice is weak, is its independently emitted global support-membership
> probability still a useful open-set gate for the stronger BGE route authority?

The staging PR is #315. It must remain unexecuted until #299 is terminal.

### Staged fallback — #311 / PR #313 AnyJev L0

A second architecture is fully staged but not executed while Kev is unresolved:

- AnyJev 소스 리비전 `45add301a7aa60ed3420c83d15c061e84e5bce61`;
- 레이블 없는 L0;
- 평가 배치 사전확률 대신 내용이 없는 사전확률 사용;
- Qwen3-0.6B 기본 리비전 고정;
- BGE 원시 Top-1만 경로 선택 권한을 유지;
- AnyJev 네이티브 `noul`은 거부 전용;
- 고정 전역 임계값 8개;
- SchemaRouter 데이터로 L1/L2 학습 없음;
- 워크플로는 수동 실행만 허용.

#312 was closed as a duplicate of #311 so the research line has one canonical fallback record.

운영 측면에서 프레임워크는 신속한 모델 교체를 지원할 준비가 됐습니다.
- Jev 전송 규약 호환 엔진은 `SystemOneDecisionBackend`를 사용;
- 임의의 제한 결정 모델은 `CallableDecisionBackend`와 범용 호출 함수 벤치마크 경로로 연결 가능;
- 모델 검색은 안정적인 실행 권한과 계속 분리.

### Precommitted Kev-family promotion policy

Before #299 terminal metrics were available, the cross-candidate selection rule was fixed:

1. 사전등록된 방식 그대로 #299 완료;
2. #299가 유효한 전체 행별 `supported_probability`를 생성하면 Kev 자체의 경로 선택이 실패하더라도 이미 준비된 #314 오프라인 합성을 실행;
3. 모든 게이트를 통과한 후보만 비교;
4. #299와 #314가 품질·런타임을 모두 통과하면 이미 확립된 BGE 등록 경로 권한을 유지하고 Kev를 거부 전용으로 제한하는 #314를 우선;
5. #314가 실패하고 #299가 통과하면 #299 승격;
6. 사후적인 언어·경로·집단별 부분집합, 프롬프트 변형 또는 실패한 새 데이터 표면을 이용해 선택하지 않음.

Outcome-driven architecture choice를 피하기 위해 이 selection policy는 result inspection 전에 commit했습니다.

## 47. Freeze and final-evaluation ownership

Architecture search 종료 단계에는 이제 explicit ownership boundary가 있습니다.

### #197 owns architecture closure

A DEV candidate that meets the standing target does not immediately enter calibration.

#197 must first:
1. select the exact passing DEV rule;
2. freeze source, architecture, authority semantics, models, runtime, representations and threshold;
3. write a machine-readable freeze manifest;
4. validate the manifest against the standing target and authority invariants;
5. generate a NEW zero-overlap fresh confirmation surface distinct from #270 and #287;
6. run the frozen candidate once without semantic retuning;
7. update the manifest to `fresh-confirmed` only if the fresh target also passes.

PR #316 introduces the reusable freeze-manifest template, validator and protocol documentation.

### #198 owns only the final consumed evidence

#198 remains blocked until a validated `fresh-confirmed` manifest exists.

After that point it owns:
1. a NEW 900-case calibration corpus and one evaluation;
2. only after calibration passes, a NEW 1,800-case blind-final corpus and one evaluation.

Calibration과 blind-final은 consumed evidence이며 tuning에 재사용하지 않습니다.

이를 통해 #198의 title/body가 freeze/fresh까지 소유하는 것처럼 읽히면서 동시에 tracker에서는 fresh confirmation까지 #198을 blocked로 취급하던 기존 procedural ambiguity를 제거했습니다. The canonical
sequence is now:

```text
architecture search
    ↓
DEV pass
    ↓
#197 exact freeze
    ↓
NEW zero-overlap fresh confirmation
    ↓
validated fresh-confirmed manifest
    ↓
#198 calibration
    ↓
#198 one-shot blind-final
```

동결 후에는 의미적 변경을 허용하지 않습니다. 품질은 통과했지만 지연시간에 실패한 후보는 사전등록된 런타임 전용 최적화만 수행할 수 있으며 의미를 변경해서는 안 됩니다. 최적화된 런타임 역시 #198 이전에 새로운 확인을 통과해야 합니다.

### Guarded staged-experiment activation

The staged fallback workflows no longer depend on a human UI click.

- #314 / PR #315는 #299의 최종 산출물이 나올 때까지 비활성 상태로 유지합니다. 소스 워크플로 실행 `36366508183`과 정확한 산출물 ID를 지정한 `benchmarks/operation-routing-v4-bge-kev-noul-compose.activation.json`에 `activate=true`를 커밋하면 활성화할 수 있습니다. 워크플로는 행을 읽기 전에 출처 실행과 산출물 식별 정보를 다시 검증합니다.
- #311 / PR #313은 Kev 계열이 승격 불가능해질 때까지 비활성 상태입니다. 활성화 표식에는 `activate=true`, `after_issue=299`, `reason="kev_family_non_promotable"`를 선언해야 합니다.

워크플로 정의 자체를 커밋하더라도 push 필터가 활성화 표식 경로에만 반응하므로 모델 평가는 시작되지 않습니다. 이를 통해 준비 단계와 실증 근거의 사용을 분리하면서도 수동 Actions UI 없이 세션 재개 자동화를 이어갈 수 있습니다.

### Freeze infrastructure merged — #316

PR #316 was squash-merged as `fad004cdfce8e40c2119d3758ab47332d52e6253`.

현재 `main`에는 다음이 포함됩니다.
- 기계 판독형 목표 85/97/100/1 + 250 ms를 정의한 `benchmarks/operation-routing-production-targets.json`;
- `benchmarks/operation-routing-freeze-manifest.template.json`;
- `scripts/validate_operation_routing_freeze_manifest.py`;
- 목표·권한·출처·지표 범위·제공자 리비전 ID·GitHub 산출물 다이제스트 변경을 검증하는 테스트;
- `docs/research/operation-routing-freeze-protocol.md`.

Canonical ownership boundary는 이제 documentation과 machine-readable governance에서 강제됩니다:
- #197 owns DEV qualification → exact freeze → NEW zero-overlap fresh confirmation;
- #198 begins only after a validated `fresh-confirmed` manifest and owns calibration → one-shot blind-final.


### Runtime parity infrastructure merged — #320

PR #320 was merged as `acaca1e14b2f387094100dde3e1186aa4520d01d`.

`main`에는 동결된 참조 분석과 런타임 변형을 비교하는 `scripts/validate_routing_runtime_parity.py`도 포함됩니다. 이 도구는 다음 변경을 거부합니다.
- 사례 집합 변경;
- 선택된 경로 변경;
- 실행·선택 포기 임계값 경계의 교차;
- 실행 오류;
- 권한 위반.

이 도구는 확률 차이의 최대·평균·p50·p95와 동결 참조의 경계 여유를 기록합니다. 이는 #318 런타임 전용 최적화의 필수 게이트입니다. 동등성 검사에 실패한 런타임 변형은 별도 사전등록 실험이 필요한 새로운 의미적 후보가 됩니다.

### Kev CPU runtime terminated without quality evidence

#299 / PR #300 attempted pinned Kev-0.8B native `choice+noul` on GitHub-hosted CPU/fp32.

이 실행은 인프라 설정까지 마쳤지만 1,800행 진단은 완료하지 못했습니다.
- 워크플로: `36366508183`;
- 종료 상태: `cancelled`;
- 산출물: `10951921452`;
- 산출물 다이제스트: `sha256:58d3c1b4aec1bb70eb2aa1747e3acd86278a16da45582930bb80dbca92f54ee0`;
- `analysis.json`: 없음.

The server log shows correct-but-slow reference PyTorch fallbacks for causal convolution and gated-delta kernels. 이 CPU/fp32 runtime은 impractical execution path로서 terminal이지만 negative model-quality evidence는 아닙니다.

후속 조치:
- #317의 6시간 제한 재시도는 실행하지 않은 채 종료;
- #314/#315의 동결된 BGE+Kev 합성은 필수 행별 분석 자료가 없으므로 종료;
- #313의 AnyJev CPU 실행은 추론 전에 종료;
- 향후 타입 기반 결정 연구는 250 ms 이하의 신뢰할 만한 운영 경로가 포함된 사전등록 런타임이 필요.

The research frontier returns to lightweight BGE-native/open-set evidence where latency is an architectural constraint from the start.

### Runtime parity infrastructure merged — #320

PR #320 was merged as `acaca1e14b2f387094100dde3e1186aa4520d01d`.

`scripts/validate_routing_runtime_parity.py`는 이후 품질 통과·지연시간 실패 후보를 최적화할 때 필수 게이트입니다. 사례 집합이나 경로의 변경, 실행·선택 포기 임계값 교차, 실행 오류, 권한 위반을 거부하며 확률 차이와 참조 경계의 여유를 기록합니다.

## 47. Lightweight BGE composition becomes active frontier

The expensive autoregressive typed-decision path was retired for the CPU product target. The next
candidate reuses only previously measured lightweight evidence.

### #322 / PR #323 — offline composition PASS

변경할 수 없는 출처 산출물:
- #262 GTE 전용 복구: 워크플로 `36326745694`, 산출물 `10934337695`,
  다이제스트 `sha256:7881a3594ecdab6a242a946a60cfde14d64e3c452ec9d0956c9cfa75a1e0c748`;
- #275 부정 기능 진단: 워크플로 `36352558325`, 산출물 `10942243493`,
  다이제스트 `sha256:a831a35098b546c8003435ea04927fb8767aab1435320823ba4763e0b6608ae1`.

동결된 합성 규칙:
- #259의 엄격한 BGE 기준;
- 원래 기준이 승인한 사례 중 최대 음성 점수 >=0.55, 우위 >=0.05인 경우에만 음성 거부권 적용;
- 거부된 기준 승인 사례는 복구 대상으로 넘기지 않음;
- 복구 시 잘못된 경로 예산 4를 가진 정확한 #262 GTE 전용 경로 규칙 사용;
- 원래 기준이 선택을 포기한 경우에만, 동일한 원시 BGE 승자를 복구.

Workflow `36379888054`, artifact `10951119927`,
digest `sha256:1e86c0ebd881ff98f73d30d65ea618ff4525ead164f7f8a0b04c4ccf98190303`.

Result:
- exact: 980/1152 = 85.0694%;
- near rejection: 572/576 = 99.3056%;
- OOD rejection: 100%;
- false-route: 4/648 = 0.6173%;
- authority/errors: 0/0.

이는 tuning-DEV offline artifact composition이며 executable 또는 generalization evidence가 아닙니다.

### #324 / PR #325 — executable candidate

#324 freezes the exact #322 semantics and recomputes them from the models:
- BGE query embedding is shared between route scoring and negative prototypes;
- GTE is invoked only on original #259 base abstentions;
- the executable output must have exact row-level parity with #322;
- directly measured total p95 must be <=250 ms.

If #324 passes, the next step is no longer architecture search: create the #316 freeze manifest and
run a new zero-overlap fresh confirmation distinct from #270/#287.

### Lightweight executable candidate passes DEV — #324/#325

The offline #322 composition was executed directly in workflow `36380771103` at semantic source
`caca039aff1c7b2960d167196f883e3bcbc5d431`.

Artifact `10952711288`, digest
`sha256:4ad9d0cc76500dd8705e0db0f677a21e44dbebb74cc3a9ca097723eb453abdc3`.

결과:
- 정확도 85.0694%;
- 유사 도메인 거부율 99.3056%;
- OOD 100%;
- 잘못된 경로 0.6173%;
- 권한 위반·오류 0/0;
- 오프라인 행별 동등성 불일치 0건;
- BGE p95 134.05 ms;
- 조건부 GTE p95 54.39 ms;
- 종단 간 p95 176.94 ms;
- GTE 호출 비율 42.61%.

이는 당시 cycle에서 quality, authority/parity, standing 250 ms runtime gate를 동시에 통과한 최초의 executable candidate입니다.

### Exact freeze and new fresh confirmation — #326/#327

The candidate was frozen with a machine-readable `frozen-dev` manifest. Representation digests and
the canonical production target validated successfully.

새로운 확인 실행 전에 다음 데이터 표면을 사전등록했습니다.
- 시드 `operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a`;
- 표면 `lightweight-bge-gte-operational-envelope-v1`;
- 확인 전용이며 튜닝에 사용할 수 없음;
- 정식 DEV 및 결정적으로 다시 생성한 #270/#287 새 표면과 정규화된 정확 중복이 0이어야 함;
- 동결된 평가기·매니페스트는 의미론적 소스 `caca039…`와 바이트 단위 차이가 없어야 함.

Active fresh workflow: `36382202178`.

### Lightweight candidate fresh confirmation — valid run 36382647406

The executable lightweight candidate from #324/#325 is frozen under #326/#327.

Frozen DEV:
- exact 85.0694%;
- near-domain rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- authority/errors 0/0;
- row parity 0;
- p95 176.9436 ms.

Fresh seed/surface were preregistered before scoring:
- seed `operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a`;
- surface `lightweight-bge-gte-operational-envelope-v1`.

초기 두 실행은 인프라 오류에 관한 증거로만 취급되어 무효입니다.
- `36382202178`: 과거 #270/#287 페이로드 재생성 시 현재 버전 전용 분할 메타데이터가 추가돼 계약 위반;
- `36382467222`: 분할 표식 테스트에서 구현 누락을 발견해 계약 위반.

Neither run generated a fresh corpus artifact or model score.

당시 유효했던 실행:
- 워크플로 `36382647406`;
- 헤드 `b19d7b0255ee9717464b6fa65ce1ebdeaf58a1bd`;
- 계약 검사 통과;
- 과거 #270/#287 코퍼스 SHA 재현 통과;
- 동결된 의미론적 차이 검사 통과;
- 동결 DEV 매니페스트 통과;
- 새로운 데이터 생성기·게이트 테스트 통과;
- 평가 작업 대기.

Technical fix 과정에서 frozen candidate의 semantic parameter는 변경되지 않았습니다.

## 47. #326 / PR #327 — lightweight BGE+GTE fresh confirmation failed

The executable lightweight candidate from #324/#325 passed canonical DEV at:
- exact 85.0694%;
- near rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- p95 176.9436 ms.

의미론적 재튜닝 없이 동결한 뒤 새로운 확인 표면에서 단 한 번 평가했습니다.
- 시드 `operation-routing-quality-v4-lightweight-bge-gte-confirmation-2026-09-28-a`;
- 표면 `lightweight-bge-gte-operational-envelope-v1`;
- 코퍼스 SHA256 `7d960bb43924569eede34748acc95f5bcd2cc04f2b9f8e396ec59c495dd3e1ec`;
- 정식 DEV 및 재생성한 #270/#287 표면과 정규화된 정확 중복: 0건.

Terminal fresh result:
- exact 977/1152 = 84.8090%;
- near-domain rejection 521/576 = 90.4514%;
- OOD 72/72 = 100%;
- false-route 55/648 = 8.4877%;
- authority/errors 0/0;
- end-to-end p95 278.3748 ms.

이는 technical failure가 아니라 valid negative evidence입니다.

해당 candidate는 종료했습니다. Fresh corpus는 영구적으로 confirmation-only이며 threshold, route/language/family repair, prototype change, rescue-rule change, model selection, calibration 또는 다른 tuning에 사용할 수 없습니다.

#270과 #287에 이어 세 번째로, 정식 DEV에서 유망해 보이는 후보도 요청 표면이 바뀌면 개방 집합 승인 경계가 약화될 수 있다는 사실을 독립적으로 보여줬습니다. 다음 아키텍처는 DEV에 맞춘 점수 분포의 추가 수정이 아니라 튜닝 가능한 DEV와 레지스트리 수준의 운영 불변 조건에서 근거를 찾아야 합니다.

## 48. #328 / PR #329 — BGE-M3 multi-representation operation gate

After the valid #326 fresh failure, the next cycle stops refining DEV-fitted dense
acceptance geometry.

저장소에는 이미 다음 접근들의 부정적 결과가 기록돼 있습니다.
- 경로별 스칼라 작업 적합성 임계값;
- 작업 이름만 이용한 MiniLM 게이트;
- 승자 전용 BGE 교차 인코더 거부;
- 교차 인코더 복구;
- 부호 있는·음성 밀집 프로토타입;
- DEV 분포를 학습한 검증기;
- 외부 사전학습 Qwen/Laya 타입 게이트.

새 hypothesis는 또 다른 threshold repair를 추가하는 대신 representation 자체를 변경합니다.

BGE-M3 natively exposes three retrieval representations:
- dense CLS embedding;
- sparse lexical weights;
- ColBERT-style token-level multi-vector interaction.

#328 이전 SchemaRouter 0.11 BGE-M3 작업은 dense representation만 사용했습니다.

#328 preregisters:
- the same pinned BGE-M3 model/revision;
- dense schema/action fusion as the sole route authority;
- token-level ColBERT evidence against only the trusted endpoint action name +
  `operation_aliases`;
- sparse lexical evidence as diagnostic-only;
- no route-local acceptance threshold;
- no margin-threshold search;
- no second threshold dimension;
- exact row-level raw-winner parity against the frozen #259 artifact.

허용된 ColBERT 규칙군은 네 가지입니다.
1. 전역 경로 일치만 사용;
2. 동일 도구의 엔드포인트 일치만 사용;
3. 전역 일치와 하나의 전역 승자 점수 임계값;
4. 동일 도구 일치와 하나의 전역 승자 점수 임계값.

Threshold families report only false-route budgets 0/6/12 on canonical tuning DEV.

Fresh #270/#287/#326 surfaces remain excluded from design and model selection.

Initial workflow runs `36384727564` and `36384796110` failed contract checks before model
evaluation and are invalid for quality conclusions. The first model-quality execution is
`36384892825`.



## 49. #328 / PR #329 — BGE-M3 ColBERT operation-contract gate rejected

Canonical workflow `36385740263` completed successfully at source
`4c72f2dd1939edb6ecf8415d620dbb5d58683fa0`.

산출물:
- ID `10955036349`;
- 다이제스트 `sha256:6e6bfbd2cb352aba03e2d98683ae6967a64115f90a04cf49f74e7cd1ab76dde7`;
- 정식 DEV SHA는 `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`로 유지;
- 밀집 벡터 원시 승자 동등성 불일치: 0건;
- 권한 위반 / 실행 오류: 0 / 0.

Dense BGE-M3 raw supported top-1 remained 88.4549%, confirming that route-ranking capacity was unchanged.
The preregistered ColBERT operation-contract families did not produce a promotable open-set boundary:

- 전역 일치만 사용: 정확도 82.5521% / 유사 도메인 거부율 32.8125% / 잘못된 경로 64.5062%;
- 동일 도구 일치만 사용: 정확도 83.7674% / 유사 도메인 거부율 7.4653% / 잘못된 경로 91.2037%;
- 전역 일치 + 잘못된 경로 1% 이하 예산의 전역 점수 임계값: 정확도 38.6285% / 유사 도메인 거부율 98.9583% / OOD 100% / 잘못된 경로 0.9259%;
- 동일 도구 일치 + 같은 예산의 전역 점수 임계값: 정확도 38.7153% / 유사 도메인 거부율 98.9583% / OOD 100% / 잘못된 경로 0.9259%.

Preregistered rule 중 standing 85 / 97 / 100 / 1 quality gate를 통과한 것은 없었습니다.

측정된 전체 경로 p95는 398.6848 ms였습니다. 희소 점수 계산은 진단 전용이었으므로 PR #331은 결과를 확인하기 전에 열렸습니다. 이미 저장된 행별 구성 요소(`encode + dense scoring + ColBERT scoring`)로 실제 실행 지연시간을 다시 계산해도 **398.6149 ms p95**여서 희소 진단 부분을 제외해도 최종 판단이 바뀌지 않았습니다. 따라서 재실행은 필요하지 않습니다.

사후적인 희소 벡터 전용 진단도 승격 근거가 아니라는 조건으로 검토했습니다. 잘못된 경로 1% 이하 예산에서 지원 사례의 정확한 경로는 12.6736%만 유지됐습니다. 동일한 BGE-M3 희소 표현을 새로운 승격 시도로 반복하지 않도록 이 결과를 보존합니다.

Decision: 이 cycle의 BGE-M3 native ColBERT/sparse operation-contract representation을 reject하고 종료합니다. Do not add a post-hoc second threshold, route-local exception, margin search, rank-2 fallback, or pseudo-route to repair it.

#198 remains blocked. The next behavior-changing architecture, if any, must be separately preregistered using only tuning-eligible DEV plus registry-defined operational semantics; failed fresh-confirmation surfaces #270/#287/#326 remain permanently non-tuning.

## 50. #332 / PR #333 — registry-self-calibrated alias envelope rejected

After ColBERT failed, #332 tested whether trusted registry metadata itself could define a
surface-independent operation boundary without another query model or a labeled-DEV threshold.

동결된 설계:
- BGE-M3 원시 등록 Top-1만 경로 선택 권한을 보유;
- 동일하게 정규화한 질의 임베딩을 경로 순위 결정과 게이트에 재사용;
- 별칭 뱅크에는 정규화된 엔드포인트 이름과 신뢰할 수 있는 `operation_aliases`만 포함;
- 경로 마진·응집도 하한은 별칭의 leave-one-out 자체 응집도와 동일 도구 형제 엔드포인트 간 거리만으로 도출;
- 고정 규칙군 A/B/C/D 네 가지를 정확히 평가;
- #270/#287/#326의 새로운 표면은 제외.

정식 근거:
- 워크플로 `36388641609`;
- 소스 `fa091f43296eb1ca680f39921010482275bb4cda`;
- 산출물 `10955736650`;
- 다이제스트 `sha256:21166d8c10009401b34380e6e24ddbcdcf4ec06c760d86b4d19eaf99930a1e1e`;
- 정식 DEV SHA `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`;
- 밀집 벡터 원시 지원 사례 Top-1 88.4549%;
- 밀집 동등성 / 권한 / 실행 오류 0 / 0 / 0;
- 라우팅 경로 p95 198.0714 ms.

결과:
- A 형제 작업 대조: 정확도 84.8958% / 유사 도메인 거부율 11.9792% / OOD 18.0556% / 잘못된 경로 87.3457%;
- B 레지스트리 마진: 정확도 72.3090% / 유사 도메인 거부율 24.1319% / OOD 68.0556% / 잘못된 경로 70.9877%;
- C 레지스트리 응집도: 정확도 24.3056% / 유사 도메인 거부율 98.4375% / OOD 100% / 잘못된 경로 1.3889%;
- D 결합 범위: 정확도 23.5243% / 유사 도메인 거부율 98.4375% / OOD 100% / 잘못된 경로 1.3889%.

No fixed family passed the standing 85/97/100/1 target.

이 결과는 structure 관점에서 유의미합니다. Same-tool alias contrast is useful for operation preference but
does not establish capability membership: unsupported requests usually still prefer one registered
sibling. Conversely, the alias self-cohesion floor becomes a strong rejection mechanism only by
demanding supported natural-language requests look nearly as internally coherent as curated registry
aliases, which collapses supported recall.

이 representation은 terminal입니다. Per preregistration, it is not repaired with a
DEV-fitted score threshold, a second threshold dimension, route/language/family exceptions, or failed
fresh-confirmation rows.

0.11 cycle에는 이제 active candidate가 없으며 #198은 blocked 상태를 유지합니다. A subsequent behavior-changing
hypothesis must provide a materially different source of open-set capability evidence rather than
another transformation of the same dense score/alias geometry.


## 51. #336 / PR #337 — threshold-free BGE/GTE consensus rejected

마지막 lightweight 0.11 hypothesis는 추가 score threshold 없이 cross-backbone route agreement만 분리해 검증했습니다.

동결된 규칙:
- BGE-M3 #259 원시 등록 Top-1만 실행 권한을 보유;
- GTE 다국어 기본 모델은 이전에 동결한 스키마/작업 표현 0.25/0.75를 사용;
- GTE 원시 Top-1이 BGE 원시 Top-1과 정확히 일치할 때만 BGE 승자 실행;
- 그렇지 않으면 선택 포기;
- 점수·마진·경로별·언어별·집단별 임계값 없음;
- 두 번째 순위 폴백, 가상 경로, 보정·블라인드 데이터 또는 실패한 새로운 근거 없음.

정식 근거:
- 워크플로 `36390328100`;
- 소스 `d25f427569fc4419a72963c6f31994fa170805f6`;
- 산출물 `10956013271`;
- 다이제스트 `sha256:56fad4070ef97782f398a259192bc5ad0e4ec3ac7d6c0fd4d531f17bfc89ccf9`;
- 정식 DEV SHA `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`;
- 권한 위반 / 실행 오류 0 / 0.

Raw ranking capacity remained high:
- BGE-M3 supported top-1 88.4549%;
- GTE supported top-1 89.1493%.

하지만 경로 일치는 개방 집합 기능 판단 신호가 아니었습니다.
- 전체 행에서 BGE/GTE 경로 일치율 72.7222%;
- 지원 사례 정확도 937/1152 = 81.3368%;
- 유사 도메인 거부율 251/576 = 43.5764%;
- OOD 거부율 59/72 = 81.9444%;
- 잘못된 경로 338/648 = 52.1605%;
- 잘못 수락된 지원 사례 34건.

GTE query+scoring p95 was 83.3360 ms and the frozen #259 BGE direct p95 was
132.1553 ms, but no combined executable latency claim was made because quality failed first.

Interpretation:

> 두 strong closed-set ranker의 agreement는 capability membership보다 selection confidence를 더 강하게 측정합니다. When an unsupported request is topically close to a registered operation,
> both rankers can confidently choose the same wrong executable destination.

The exact consensus rule is terminal. No post-result score/margin threshold is added.

## 52. 0.11 operation-routing-quality-v4 — terminal cycle decision

0.11 cycle은 promoted production-target candidate 없이 종료됩니다.

The standing target was:
- supported exact >=85%;
- near-domain unsupported rejection >=97%;
- OOD rejection =100%;
- false-route <=1%;
- authority/execution errors =0;
- executable p95 <=250 ms.

One executable DEV candidate (#324/#325) met the complete target:
- exact 85.0694%;
- near rejection 99.3056%;
- OOD 100%;
- false-route 0.6173%;
- p95 176.9436 ms.

The exact frozen candidate then failed its new zero-overlap fresh confirmation (#326/#327):
- exact 84.8090%;
- near rejection 90.4514%;
- OOD 100%;
- false-route 8.4877%;
- p95 278.3748 ms.

이 failure가 promotion을 결정하는 결과이며 calibration과 blind-final은 실행하지 않습니다.

새 표면에서 실패한 뒤에는 확인 데이터의 개별 행을 수정하지 않고, 실질적으로 다른 표현을 시험했습니다.
- BGE-M3 ColBERT·희소 작업 근거(#328/#329): 최종 거부;
- 레지스트리 자체 보정 별칭 경계(#332/#333): 최종 거부;
- 임계값 없는 BGE/GTE 합의(#336/#337): 최종 거부.

기존 부정적 결과(긍정 밀집 임계값, NLI, 부호 있는·음성 프로토타입, 순위 휴리스틱, 학습된 DEV 검증기 분포, Qwen/Laya/Kev/AnyJev 타입 결정 경로, 교차 인코더 변형)와 함께 보면 정식 DEV는 이미 충분히 탐색됐습니다. 임계값이나 사람이 직접 작성한 예외를 계속 추가하면 독립적 근거 없이 선택 편향만 키울 수 있습니다.

0.11 research conclusion은 다음과 같습니다:

1. 등록 경로의 순위 결정 능력은 충분함. BGE-M3 원시 Top-1은 약 88.45%;
2. 해결되지 않은 문제는 개방 집합에서의 기능 소속 여부;
3. DEV 통과만으로는 충분한 근거가 아님. 세 가지 독립된 접근이 새로운 요청 표면에서 악화됐고, 현재 가장 강력한 실행 가능 후보도 정식 새 표면 게이트에서 실패;
4. 근거를 이미 사용한 데이터에 맞춰 튜닝하는 대신 아키텍처 탐색 주기를 종료하는 것이 안전한 조치;
5. 진입 조건을 충족하지 못했으므로 #198 보정·블라인드 최종 평가는 실행하지 않음.

The robust #259 profile remains a useful conservative reference:
- exact 83.7674%;
- near rejection 98.9583%;
- false-route 0.9259%;
- planner p95 ~134.95 ms.

85% exact requirement를 충족하지 못하므로 production-target pass로 다시 labeling하지 않습니다.

후속 연구 주기는 실질적으로 새로운 기능 근거와 새로운 사전등록 프로토콜을 도입해야 합니다. #270/#287/#326에 맞춰 튜닝하거나, 사후 임계값으로 종료된 0.11 계열을 되살리거나, 호환성 근거를 품질 근거로 바꿔 해석해서는 안 됩니다.


## 53. #338 / PR #341 — arbitrary-tool registry-compiled verifier rejected

After the 0.11 architecture-search cycle closed, #338 tested a product-level generalization
constraint that earlier benchmark-specific work did not fully exercise:

> can the same capability compiler and verifier work when a user registers previously unseen native
> ToolSpec, OpenAPI, or MCP tools, without route-specific retraining?

The experiment was preregistered before execution.

설계 제약:
- 네이티브 ToolSpec, OpenAPI, MCP는 동일한 제공자 중립 기능 중간 표현으로 컴파일;
- 엔드포인트 이름은 불투명할 수 있고 `operation_aliases`는 비어 있을 수 있음;
- 경로 ID, 고정 엔드포인트 개수, 벤치마크 도메인 키워드 표를 학습 특징으로 사용 금지;
- JSON 데이터형·구조, 의미 식별자, 원본 단위, 명시적인 단위 정규화, 한정자는 등록된 결정적 메타데이터로 보존;
- BGE-M3 원시 Top-1만 경로 선택 권한을 보유;
- 학습 구성 요소는 거부권만 가지며 두 번째 경로 폴백이나 가상 경로를 허용하지 않음;
- 새로 등록된 경로마다 별도 재학습을 요구하지 않음.

Canonical execution:
- workflow `36393153612`;
- source `ef75100abc1bb03a80ef2d7cfbd9d463accfb623`;
- artifact `10957952613`;
- digest `sha256:2a24d50c563ee872fdad8d498e30ab7a55e6c82e0650bf27ac4bfbadc4fc4269`.

Results:

| Surface | Exact | Near reject | OOD | False-route | Correct raw-winner retention | p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Canonical DEV (1,800) | 5.0347% | 100% | 100% | 0% | 5.6919% | 196.93 ms |
| Registration holdout (228) | 2.0833% | 100% | 100% | 0% | 2.4590% | 192.85 ms |

Authority violations and execution errors were zero, and canonical raw BGE parity had zero
mismatches.

Interpretation:

Provider-neutral typed capability/data-contract compiler는 arbitrary native/OpenAPI/MCP registration과 datatype/unit/qualifier metadata 보존을 포함해 infrastructure로서는 정상 동작했습니다.
The generic synthetic learned veto did not. It achieved perfect rejection by rejecting nearly every
valid supported request.

Decision: preregistration대로 label-driven repair 없이 terminal reject합니다.

PR #341 was closed without merge. The infrastructure lesson is retained; the learned-veto quality
claim is not promoted into the library default.


## 54. #347 / PR #348 — query-first typed frame preserves supported routes but under-rejects unsupported

The first 0.12 successor experiment stopped comparing query/endpoint similarity for
capability membership.

Preregistered architecture:

```text
query
  -> registry-independent explicit request frame
  -> frozen BGE-M3 raw top tool/domain anchor
  -> deterministic within-tool contract compatibility
  -> unchanged BGE-M3 ranking inside the compatible endpoint set
  -> route or NO_ROUTE
```

Unlike #338, there was no learned binary veto, probability threshold, route-local threshold,
pseudo-route, or post-ranking rank-2 fallback.

새로운 0.12 데이터 프로토콜은 채점 전에 동결했습니다.
- 개발: 936건, SHA `79a7cb9672e6633739e0acd08882019f5cfeff479df103f8199aabacb8501a9f`;
- 등록 확인: 1,008건, SHA `15587c646d64b4f3462127742c05d59092938f68a4c047b731e9a8c78c0eb673`;
- 두 카탈로그 모두 새로운 도구 식별자와 네이티브/OpenAPI/MCP 등록을 사용;
- 확인 코퍼스는 DEV 채점 전에 생성하고 동결.

DEV evidence:
- workflow `36404647843`;
- source `ef0e0a567f12129bf9f4b003d13f9f6e9679a216`;
- artifact `10962450383`;
- digest
  `sha256:74df3e068421bb2c551a30c2b5c5cdb9547e17066bf3f4ce7f8154c11690849c`.

결과:
- 지원 사례 정확도 97.2222%;
- 원시 지원 사례 정확도 96.7593%;
- 원시 지원 도구 정확도 99.5370%;
- 유사 도메인 미지원 거부율 70.3704%;
- OOD 거부율 95.8333%;
- 잘못된 경로 25.9921%;
- p95 179.526 ms;
- 권한 위반 / 실행 오류 0 / 0.

이는 #338과 거의 정반대의 결과입니다. The query-first structural filter preserves valid
supported requests extremely well and can correct some endpoint choices, but the high-precision
lexical request frame leaves too many unsupported requests as structurally unknown. So those requests
fall back to the raw BGE domain anchor and still receive an executable destination.

Decision: terminal reject on DEV. No row-driven lexicon expansion, per-language patching, or
route-specific exception is allowed. The frozen 1,008-case confirmation corpus remains completely
unscored.

Architectural lesson은 명확합니다. 다음 materially new signal은 endpoint-similarity membership threshold로 돌아가지 않으면서 여기서 입증한 높은 supported-route retention을 희생하지 않고 **query-side operation-frame coverage**를 개선해야 합니다.


## 55. #349 / PR #352 — flat semantic action ontology rejected

#347에서 명시적인 어휘 기반 요청 형식이 지원 요청의 라우팅은 보존하지만 미지원 작업을 너무 많이 놓친다는 사실이 드러나자, #349는 표면상의 어휘집을 레지스트리와 독립적인 다국어 의미 기반 작업 온톨로지로 교체했습니다.

요청은 동결된 BGE-M3 프로토타입 유사도를 통해 일반적인 작업 분류 하나에 투영되고, 해당 작업은 도구 내부의 결정적 기능 제약으로 사용됐습니다. 학습된 거부권, 확률 임계값, 경로별 임계값, 가상 경로 또는 도구 간 폴백을 허용하지 않았습니다.

새 코퍼스 두 개는 채점 전에 생성하고 동결했습니다.
- DEV: 504건, SHA `1a497bcd36192913840d7ecd4c6bed714c908468baed6f2b0b9f4367bf57ffc6`;
- 확인: 552건, SHA `548fe42da09e7c8dc89530c43d409db05618f57a39c277fca27aebe79b6802b9`;
- 확인 데이터는 채점하지 않았습니다.

DEV evidence:
- workflow `36406845612`;
- source `38ee7557565983746e33741897e6168bf4f35643`;
- artifact `10962178834`;
- digest
  `sha256:de687d850e619cb1ce143648ef6fe21950f6a395a33bc6835a7564b24f9a03a1`.

결과:
- 지원 사례 정확도 44.9074%;
- 원시 BGE 지원 사례 정확도 77.3148%;
- 원시 BGE 지원 도구 정확도 94.4444%;
- 유사 도메인 미지원 거부율 56.4815%;
- OOD 거부율 100%;
- 잘못된 경로 32.6389%;
- p95 197.549 ms;
- 권한 위반 / 실행 오류 0 / 0.

Flat semantic ontology는 terminal reject했습니다. 핵심 lesson은 ontology가 쓸모없다는 것이 아니라 noisy semantic label에 hard endpoint-removal authority를 부여해서는 안 된다는 점입니다.

## 56. #354 / PR #357 — hierarchical executable-capability ontology rejected as a hard filter

#354 made the ontology explicit and hierarchical rather than flat.

일반 온톨로지는 다음을 구분했습니다.
- 읽기: 검색 / 조회 / 목록 확인;
- 변경: 생성 / 수정 / 삭제 / 취소 / 환불;
- 전송: 보내기 / 공유;
- 변환: 내보내기 / 번역 / 요약 / 비교 / 병합;
- 제어: 재시작 / 실행;
- 예측: 예보;
- 비도구 작업: 작성 / 설명 / 계산 / 대화.

요청 측 상위·하위 기능 근거는 고정된 다국어 대조 프로토타입에서 얻었습니다. 엔드포인트 측 상위·하위 기능 사실은 신뢰할 수 있는 레지스트리 메타데이터에서 얻었으며, HTTP·읽기 전용·파괴적 작업 메타데이터를 의미 추론보다 우선했습니다.

동결 작업은 채점 전에 끝났습니다.
- 동결 워크플로 `36408654108`;
- 동결된 온톨로지·코퍼스 소스 `9777e1c76df27bff38cb3060d672d4f8baf65334`;
- 동결 산출물 `10963536169`;
- 동결 다이제스트 `sha256:ac8bb723e8def4dca002c21662504ccbc169d02d2bdcc72905d621710f128bd2`;
- DEV: 564건, SHA `3731ade0c1cfc69fbf234c00e9090a35b8fca5340af98077e1a18f98782d2a4a`;
- 확인: 576건, SHA `1e965111a7835af002b397d0be6b4776ea2a9295f417991f5b7733f79f23a24e`;
- 확인 데이터는 열지 않았습니다.

DEV 평가:
- 워크플로 `36408861468`;
- 평가 소스 `250845bba058a704ab50cdde43326cc1e5c26d62`;
- 워크플로는 먼저 모든 동결 온톨로지·코퍼스 파일이 동결 소스와 바이트 단위로 동일한지 검증;
- 산출물 `10964025921`;
- 다이제스트 `sha256:40eb58bc091380257409d93b662bbfbfa9b966e8c752b9a63df04b68237f7e2b`.

결과:
- 지원 사례 정확도 30.4167%;
- 원시 BGE 지원 사례 정확도 85.4167%;
- 원시 BGE 지원 도구 정확도 100%;
- 유사 도메인 거부율 68.6508%;
- OOD 거부율 88.8889%;
- 잘못된 경로 26.8519%;
- p95 164.328 ms;
- 권한 위반 / 실행 오류 0 / 0.

이는 강한 architectural negative result였습니다. On this new DEV, the raw BGE ranker already met the
supported exact target and identified the correct tool for every supported case. The hierarchical
ontology hard filter then destroyed that good signal.

Decision: row-driven repair 없이 terminal reject합니다.

그 결과 다음 candidate의 design rule이 더 명확해졌습니다:

> keep ontology as structured capability metadata and negative evidence, but do not let noisy
> semantic ontology projection select, rerank, or remove supported endpoints.


## 57. #358 / PR #360 — asymmetric ontology veto preserves supported winners but lacks recall

After #347, #349 and #354, the ontology was removed from positive route-selection authority.

#358 preregistered a stricter authority separation:
- frozen BGE-M3 raw top-1 is the sole positive route selector;
- the anchored tool's registered capability leaves define the finite authority set;
- the explicit parser, BGE ontology projection and an independent pinned multilingual MiniLM
  projection may only provide negative evidence;
- ontology can return `NO_ROUTE`, but can never switch, rerank or select another endpoint;
- the veto requires exact unsupported-leaf agreement under a fixed rule;
- no similarity, margin, confidence, route-local or learned threshold is used.

동결 코퍼스 근거:
- 동결 실행 `36411756496`;
- 동결 소스 `e29b6e0006dd64bab31c613b97ea68de8c2931f6`;
- 동결 산출물 `10965015475`;
- 다이제스트 `sha256:1d93e8441224051ce63aacc050eb6cd99979f613945e5a21419abc5aa65b0a39`;
- DEV: 552건, SHA256 `e2f3ab0f93584d896f401c94200200d7a39c8f00a4983addd4ebc8889757ee07`;
- 확인: 552건, SHA256 `bbe4984681472ad5ffe1ed881fd2b92937668fed453a45d6afbba587ffa376e8`.

DEV workflow `36412029437` at source
`759359882c3deb1be310fc540bbb1780b1543885` produced artifact `10964703106`,
digest `sha256:6b25f94698650175475a4c7339526298e7582b1be43366a8c695cfeecdcf9aaa`.

결과:
- 지원 사례 정확도 96.0526%;
- 원시 지원 사례 정확도 96.0526%;
- 원시 도구 정확도 99.5614%;
- 원시 정답 승자 거부율 0%;
- 유사 도메인 거부율 26.5873%;
- OOD 거부율 84.7222%;
- 잘못된 경로 60.4938%;
- 거부 정밀도 99.2248%;
- 거부 재현율 39.5062%;
- 긍정 경로 변경 0;
- p95 236.0203 ms;
- 권한·실행 오류 0/0.

Interpretation:

Authority design 자체는 동작했습니다. Ontology evidence를 negative-only signal로 안전하게 제한할 수 있었고 이 exact rule은 raw-correct supported winner를 하나도 veto하지 않았습니다. 실패 원인은 precision이 아니라 recall입니다. Requiring
independent evidence to agree on the exact same unsupported leaf is too strict for open-set
membership.

Decision: exact agreement rule을 terminal reject합니다. No failed row is used to add phrases,
rewrite prototypes, tune thresholds or create route-specific exceptions. The already-generated
confirmation corpus remains unopened.


## 58. #363 / PR #364 — capability-set membership consensus improves recall but remains insufficient

#363 kept the authority rule established by #358: frozen BGE-M3 raw top-1 was the sole positive
route selector, and ontology evidence could only veto to `NO_ROUTE`.

변경된 동작은 의미 기반 합의의 단위뿐이었습니다. BGE와 MiniLM이 정확히 같은 미지원 하위 기능의 이름을 제시하도록 요구하는 대신, 각 신호를 기준 도구에 등록된 유한한 기능 집합에 대응시키고 `SUPPORTED`, `OUTSIDE_SET`, `UNKNOWN`으로 분류했습니다.

규칙은 새로운 평가 표면을 만들기 전에 사전등록했습니다.
- 명시적인 `OUTSIDE_SET`와 하나 이상의 의미 기반 `OUTSIDE_SET` → 거부;
- 명시적인 `UNKNOWN`와 두 의미 인코더 모두의 `OUTSIDE_SET` → 거부;
- 명시적인 `SUPPORTED` → 원시 BGE 경로 유지;
- 그 외에는 유지;
- 임계값, 학습 헤드, 엔드포인트 필터, 두 번째 순위 폴백, 가상 경로, 긍정 재순위화 없음.

새로운 네이티브/OpenAPI/MCP 코퍼스 쌍을 채점 전에 동결했습니다.
- 동결 실행 `36415762115`;
- 동결 소스 `a1a9eb20622dd8a47082ca8fa5cd02c52d27e653`;
- 동결 산출물 `10966724823`;
- 다이제스트 `sha256:d957f82e29bdec0723fb0dda0622098563354a8ecdb45e8108b4633bc3bc6915`;
- DEV: 552건, SHA `1d3d18975b33156d97f3b4fd518158cba418c449fae01e864977f8bdf77b5e62`;
- 확인: 552건, SHA `ba92c3c25da3601bd50f580dcfaf7b512ec2e26971e10ec9e501bb59cbf35d37`;
- 타입 기반 숫자·단위 예제(`W/m2`, `L/s`) 포함;
- 확인 데이터는 열지 않았습니다.

DEV evaluation:
- run `36415951667`;
- source `f198f896c44860c27ce14b4c88200096ef0b754f`;
- artifact `10967871097`;
- digest `sha256:799006f7d69b94a29bfa0cfc62384ca2a8640cba668ac69e04ab2702a08f3f93`.

결과:
- 지원 사례 정확도 86.4035%;
- 원시 BGE 지원 사례 정확도 94.2982%;
- 원시 BGE 도구 정확도 99.5614%;
- 유사 도메인 거부율 54.7619%;
- OOD 거부율 97.2222%;
- 잘못된 경로 35.8025%;
- 거부 정밀도 91.2281%;
- 거부 재현율 64.1975%;
- 원시 정답 승자 거부 18건 / 8.3721%;
- 긍정 경로 변경 0;
- p95 249.7303 ms;
- 권한·실행 오류 0 / 0.

#358과 비교하면 set membership이 veto recall을 크게 높였지만 같은 projection family는 충분한 open-set coverage를 제공하지 못했고 correct supported winner를 해치기 시작했습니다.

Decision: terminal reject합니다. No membership-combination diagnostic or failed row is used to tune
another rule on this DEV, and the frozen confirmation is not opened. The next candidate must use a
materially different semantic membership evidence source.


## 59. #371 / PR #372 — external multilingual zero-shot OUTSIDE-label membership rejected

#371 introduced a materially different semantic evidence source after the BGE/MiniLM ontology-vote
family was closed. Frozen BGE-M3 remained the sole positive route selector, while an independently
pretrained multilingual zero-shot classifier could only preserve that winner or veto to
`NO_ROUTE`.

기준 도구마다 후보 레이블 집합은 다음으로 구성됐습니다.
- 등록된 각 작업 세부 기능에 대한 고정 설명 레이블 하나;
- 일반적인 `request an operation outside the registered capabilities of this tool` 레이블 하나.

No classifier output could select, rerank, filter to, or fall through to another endpoint. No
probability/margin threshold or SchemaRouter fine-tuning was used.

V5F 코퍼스 두 개는 채점 전에 동결했습니다.
- 동결 실행 `36419226642`;
- 동결된 동작·코퍼스 소스 `6c02c313a022740100377ead5890fd1f0d782978`;
- 동결 산출물 `10968721554`;
- 다이제스트 `sha256:1820bafd0e5c745e7175e75cca32e6e27f20a7b3bafd53b7138a138d11429a62`;
- DEV: 552건, SHA `64a89e96a2beaf90e9b44febdef033a2ec9a17c60459c909a0718b759dd9baae`;
- 확인: 552건, SHA `9beebb5957f1bfd264a14349582c74ad9b15627c6530324f792d3e1d249ecbe9`;
- `degC -> K`, `kPa -> Pa`를 포함한 단위 필드 보존;
- 확인 데이터는 열지 않았습니다.

The external model was pinned at runtime from tag `v1.1` to immutable revision
`d8c48cf2e7c7640ad5bbb379bdb2f72f5ebde7c4`.

DEV evaluation:
- workflow `36419512215`;
- evaluated source `5e6dde0c3860ff46f0961c74233d7196e6c86f59`;
- artifact `10968782843`;
- digest
  `sha256:fe53e28362d9d9d78573e68f41bcb1cce6eab0c26294f1b73a599d36fafbb6d5`.

결과:
- 지원 사례 정확도 93.4211%;
- 원시 BGE 정확도 93.8596%;
- 원시 BGE 도구 정확도 99.1228%;
- 유사 도메인 거부율 1.5873%;
- OOD 거부율 2.7778%;
- 잘못된 경로 98.1481%;
- 거부 정밀도 85.7143%;
- 거부 재현율 1.8519%;
- 원시 정답 지원 승자 거부 1건(0.4673%);
- 긍정 경로 변경 / 권한 위반 / 실행 오류 모두 0;
- 외부 분류기 p95 93.1540 ms;
- 종단 간 p95 274.5241 ms.

External model은 bounded semantic verifier로서 operationally 관심을 가질 만큼 빨랐지만 generic OUTSIDE catch-all은 native single-label normalization에서 concrete supported label을 거의 이기지 못했습니다. 실패 원인은 runtime뿐 아니라 semantic formulation입니다.

Decision: terminal reject. No label wording, hypothesis-template, threshold, language rule, or
route-local repair may use this DEV. The frozen confirmation surface remains unopened.

The next materially distinct hypothesis is to condition the actual anchored tool capability set
directly in a binary entailment/not-entailment question.


## 60. #374 / PR #375 — set-conditioned binary entailment collapses to universal rejection

#374 tested the direct set-conditioned NLI formulation suggested by #371's failure.

아키텍처는 실행 권한 측면에서 안전한 상태를 유지했습니다.
- 동결된 BGE-M3 원시 Top-1만 긍정적 경로 선택 권한을 가짐;
- 기준 도구에 등록된 하위 기능은 신뢰할 수 있는 스키마 메타데이터에서 컴파일;
- 하나의 NLI 문장 쌍에서 원시 질의를 전제로, 유한한 등록 기능 집합을 가설로 제공;
- 함의 판단은 원시 경로를 유지하고 비함의 판단은 `NO_ROUTE`로 거부;
- 임계값, 보정, 언어 규칙, 두 번째 순위 폴백, 가상 경로 또는 긍정 재순위화 없음.

새 V5G 코퍼스는 채점 전에 동결했습니다.
- 동결 워크플로 `36421851941`;
- 동결된 동작·코퍼스 소스 `c456214daba7d98d6822f99bd74aa50fb887a8f4`;
- 동결 산출물 `10969746736`;
- 다이제스트 `sha256:d52241d155c043ae4398a471a25b9ce35700229d46377da5f86a41e02b851d8d`;
- DEV: 552건, SHA `f24d874afb5c248ff0ece71da27f89fd4d442e745e6e610269a9300c1851c034`;
- 확인: 552건, SHA `214d59f25e755c73d15d9d6814363604ff88d5f7f6e66a93e1c0f133b0633332`;
- 확인 데이터는 열지 않았습니다.

DEV evaluation:
- workflow `36422168708`;
- evaluated source `e61058d0aa31819bf99b182f4bd5947dd0d11fab`;
- artifact `10970342078`;
- digest
  `sha256:4584f55a67b6744ba8ba3454290a2acb5e7cee1ce58695a0362618ab07f7faf8`.

결과:
- 지원 사례 정확도 0.0000%;
- 원시 BGE 지원 사례 정확도 92.5439%;
- 원시 BGE 도구 정확도 99.5614%;
- 유사 도메인 거부율 100%;
- OOD 거부율 100%;
- 잘못된 경로 0%;
- 함의 / 비함의 판단 0 / 552;
- 원시 정답 승자 거부 211건 / 100%;
- 거부 정밀도 58.6957%;
- 거부 재현율 100%;
- NLI p95 56.1598 ms;
- 종단 간 p95 254.5495 ms;
- 긍정 경로 변경 / 권한 위반 / 실행 오류 0 / 0 / 0.

이는 #371의 semantic mirror image입니다. The multiclass OUTSIDE formulation almost never rejected;
the aggregate set-entailment formulation rejected everything. The external model itself is fast
enough to remain technically interesting, but neither extreme formulation provides a useful
open-set capability-membership boundary.

Decision: terminal reject. No hypothesis rewrite, threshold, language-specific rule or
failed-row-driven repair is permitted. The frozen confirmation surface remains unopened.

Successor는 post-hoc threshold로 두 결과 사이를 interpolate하는 대신 semantic decomposition 자체를 바꿔야 합니다.


## 61. #377 / PR #379 — independent registered-leaf entailment improves recall but over-vetoes support

#377 replaced the failed aggregate set-entailment sentence with one independent NLI pair per
registered capability leaf under the BGE-anchored tool.

동결된 권한 규칙은 변경하지 않았습니다.
- BGE-M3 원시 Top-1만 긍정 경로 선택 가능;
- 각 등록 세부 기능마다 하나의 고정 일반 가설을 제공;
- 질의 하나에 대한 모든 가설을 단일 배치에서 평가;
- 함의 판정이 하나라도 있으면 원시 BGE 승자를 유지;
- 함의 판정이 0개라면 `NO_ROUTE`로 거부;
- NLI는 다른 엔드포인트를 선택·재순위화·대체·필터링할 수 없음;
- 신뢰도·확률·마진·언어·경로·학습 임계값을 사용하지 않음.

동결 근거:
- 워크플로 `36424007584`;
- 동결된 동작·코퍼스 소스 `b545999528b17a2782c76e6b6e546703b7b11da5`;
- 산출물 `10970381458`;
- 다이제스트 `sha256:48afeead8687eb7d28aa2fce30485a017a368b2b5119b1278a162f7badad45af`;
- DEV: 552건, SHA `c68bf11e52f960a7c8600d9d36b7fe13ab0b7b6e215a87f5b2bcffb783a67310`;
- 확인: 552건, SHA `ac4be0d6febda04fea60ae351691dfeebb932c1ec1161f14cf7754c44f49eefd`;
- 확인 데이터는 열지 않았습니다.

DEV evaluation:
- workflow `36424336147`;
- source `a872c9602dcad959ea1bf10f16a052592754d4ae`;
- artifact `10971456253`;
- digest `sha256:153781b690336a863de5a4ad2f2a7cb0793a01718d5d6c053bcd99a3dd66a937`.

결과:
- 지원 사례 정확도 45.6140%;
- 원시 BGE 정확도 96.4912%;
- 원시 BGE 도구 정확도 100%;
- 유사 도메인 거부율 71.0317%;
- OOD 거부율 95.8333%;
- 잘못된 경로 23.4568%;
- 거부 정밀도 66.8464%;
- 거부 재현율 76.5432%;
- 원시 정답 승자 거부 116건 / 52.7273%;
- NLI 배치 p95 79.5343 ms;
- 종단 간 p95 278.0917 ms;
- 긍정 경로 변경 / 권한 위반 / 실행 오류 0 / 0 / 0.

이 experiment는 finite capability set을 independent leaf judgment로 분해하는 것이 하나의 aggregate set-membership sentence보다 유의미하게 낫지만 independent binary argmax는 hard membership veto로 쓰기에는 여전히 너무 brittle하다는 점을 보여줍니다. Supported queries frequently receive zero entailment,
causing more than half of raw-correct winners to be rejected.

판정: 최종 거부. 실패한 행의 문구, 언어별 부분집합, 혼동 쌍, 점수 분포, 가설 문구 수정, 임계값, 마진 또는 투표 규칙을 #377 수리에 사용해서는 안 됩니다. 확인 코퍼스는 계속 열지 않은 상태로 유지합니다.

이미 사전등록된 #378은 다음으로 허용된 단계입니다. BGE를 유일한 긍정 경로 선택자로 유지하면서 등록된 세부 기능들에서 얻은 최대 함의 근거와 가상의 반사실적 세부 기능들에서 얻은 최대 함의 근거를 비교합니다.


## 62. #378 / PR #380 — pairwise registered-vs-counterfactual NLI remains below target

#378 was preregistered before #377 DEV was opened. It evaluated all 22 fixed generic operation
hypotheses independently in one batch, then compared the maximum entailment score among the
BGE-anchored tool's registered leaves with the maximum score among counterfactual tool/non-tool
leaves.

The authority rule remained asymmetric: counterfactual evidence could only veto to `NO_ROUTE`;
frozen BGE-M3 raw top-1 remained the sole positive route selector.

동결:
- 워크플로 `36424651535`;
- 소스 `7fccdb1eccb5f08d31ca87c798fc5f9f52a119f3`;
- 산출물 `10971625459`;
- 다이제스트 `sha256:9a0f4cfa2f5fe3a47f81374a9867dd618ebe84fa17cbb0a09c2c8a2cd2503577`;
- DEV SHA `75c7bab67de9c533df08ab5a76f7ce5e49acd92d3737f70b8dcfa50222c6abbd`;
- 확인 SHA `caee6eb89b07e948b42130e4bb1ea3f6c1b4088fc76137f0d8e7cb394f8c6007`;
- 확인 데이터는 열지 않았습니다.

DEV:
- 워크플로 `36424971822`;
- 소스 `02aeefd4656f5b61a948142dfba74f51207bd979`;
- 산출물 `10970443611`;
- 다이제스트 `sha256:8f24db27938f6924723d2088fd5ddc6811db433d0ceaf5b5e23c2412422dfd06`;
- 지원 사례 정확도 67.5439%;
- 원시 BGE 정확도 95.1754%;
- 원시 BGE 도구 정확도 98.2456%;
- 유사 도메인 거부율 55.9524%;
- OOD 거부율 95.8333%;
- 잘못된 경로 35.1852%;
- 거부 정밀도 75.5396%;
- 거부 재현율 64.8148%;
- 원시 정답 승자 거부 63건 / 29.0323%;
- NLI 배치 p95 387.8679 ms;
- 종단 간 p95 539.9184 ms;
- 긍정 경로 변경 / 권한 위반 / 실행 오류 0 / 0 / 0.

Decision: terminal reject. The exact pairwise comparison neither met open-set quality nor runtime
targets. No threshold, epsilon, tie rule, hypothesis wording, language rule or failed-row repair is
permitted.

이로써 Horizon zero-shot/NLI decomposition family(#371/#374/#377/#378)를 종료합니다. The next research
cycle (#382) moves to a materially different family grounded in open-intent/OOS literature:
schema-derived adaptive decision boundaries, then schema-derived hard negatives and energy-based
open-set evidence.


## 2026-09-28/29 — 0.13 post-V6E semantic-evidence sequence

V6A~V6E에서 합성 스키마에 기반한 구형·타원체·가우시안 혼합·로컬 kNN 분포가 실제 자연어 요청에 제대로 일반화되지 않는다는 사실이 드러나자, 연구는 분포를 다시 튜닝하는 대신 근거의 출처를 바꿨습니다.

Five preregistered controls were consumed:

1. #404 자연스러운 일반 작업 탐침은 동결된 다국어 발화 뱅크에서 MiniLM 선형 탐침을 학습했습니다. 넓은 OOD 성능은 향상됐지만 지원 사례 정확도는 75.44%, 유사 도메인 거부율은 59.52%, p95는 297.36 ms였습니다.
2. #406 Tool-Embed 긍정 검색은 도구에 특화된 외부 임베딩 모델을 경로 선택자로 시험했습니다. 같은 표면의 BGE-M3 86.84%에 비해 정확도 78.07%에 그쳤고 지연시간 목표도 실패했습니다.
3. #408 상대 다국어 교차 인코딩은 요청과 등록 문서, 동일 리소스의 반사실적 문서, 배경 문서의 점수를 함께 계산했습니다. 지원 사례 정확도 79.39%, 유사 도메인 거부율 19.84%, OOD 거부율 59.72%, 잘못된 경로 71.30%, p95 약 2.99초였습니다.
4. #409 동결된 GTE 다국어 긍정 검색은 V6F 이전에 강했던 표현을 새로운 지원 사례 전용 레지스트리에서 재검토했습니다. p95 100.14 ms로 런타임은 가능했지만, GTE 정확도는 71.49%로 동일 표면 BGE의 88.16%보다 낮았습니다.
5. #412 다국어 E5 분할 컨포멀 소속 판단은 경로 선택과 선택 포기를 분리하고 고정 alpha=0.01에서 단측 미지원 귀무가설을 보정했습니다. 유사 도메인 거부율 99.21%, OOD 거부율 100%, 잘못된 경로 0.62%, p95 244.24 ms였지만 정답인 원시 BGE 승자의 87.29%를 거부하면서 지원 사례 정확도는 10.09%까지 하락했습니다.

Every associated confirmation surface remained unopened because DEV failed at least one
preregistered gate.

이 결과는 이전보다 강한 아키텍처 제약을 제시합니다. 후속 후보는 지원 요청과 같은 도메인의 미지원 기능 요청을 의미적으로 분리하는 능력을 개선해야 합니다. 긍정 검색기의 교체, 일반 작업 분류, 상대 관련성 순위 결정 또는 약한 스칼라 점수를 컨포멀 보정하는 방법만으로는 충분하지 않습니다.



## 2026-09-29 — V6H closes the authoritative parser line and 0.14 reframes the product question

### #415 / PR #416 — V6H end-to-end multilingual operation/OOS parser

V6H는 학습된 의미 파서가 동결된 BGE 승자의 거부권으로 작동하게 하는 0.13의 마지막 시도였습니다. #404와 달리 다국어 MiniLM 인코더 자체를 TOOL_OPERATION/BACKGROUND 범위 판단과 18종 일반 작업 분류에 맞춰 종단 간 미세조정했습니다.

모델 채점 전에 실험을 동결했습니다.
- 동결 워크플로 `36501993390`;
- 소스 `5135a29f39633421136a0c13c39675947fd92f3b`;
- 학습 뱅크 SHA `c9bf9d378f8f9ef7388fde833e9a04c941871514319961b4a0666d97983caa68`;
- DEV SHA `4da38c34929fcbd7ef828a5ccee9afa89b048c960b852cf315dd68b97370f09e`;
- 확인 SHA `26140a4a77ef07fbda0d875cbcba421b0f7a7465990c775fe656bfa4115c7565`.

DEV 결과:
- 게이트 통과 후 지원 사례 정확도 70.18%;
- 원시 BGE 정확도 81.58%;
- 원시 BGE 도구 정확도 92.98%;
- 유사 도메인 거부율 65.08%;
- OOD 거부율 98.61%;
- 잘못된 경로 27.47%;
- 원시 정답 승자 거부율 13.98%;
- 범위 분류 정확도 90.58%;
- 지원 사례 작업 정확도 70.61%;
- 유사 도메인 미지원 작업 정확도 51.98%;
- 결합 p95 181.44 ms;
- 권한 / 경로 변경 / 실행 오류 0 / 0 / 0.

이 결과는 표현 학습이 일반적인 범위 판단을 개선하고 런타임 목표도 충족했지만, 동일 도메인의 작업을 구별하는 능력은 충분히 일반화되지 않았다는 점에서 중요합니다. 확인 데이터는 열지 않았고, 정확한 V6H 학습·결정 방식은 최종 종료됐습니다.

### The conceptual correction

At this point the research question itself was re-examined.

SchemaRouter의 안정된 제품 아키텍처는 이미 등록된 실행 가능 기능을 타입 기반 메타데이터와 함께 컴파일하고 색인합니다. LLM 에이전트 시스템에서 이 계층은 최종적인 자율 도구 선택 권한이라기보다 타입이 지정된 실행 가능 검색기·색인에 가깝습니다.

0.11~0.13 연구는 검색 계층에 점차 다음 세 책임을 동시에 부여했습니다.
1. 정확한 경로 검색;
2. 요청이 등록된 기능 집합에 속하는지 판단;
3. 실행 또는 비실행에 대한 최종 결정.

종료된 연구 계보는 이런 책임 결합이 안전성과 포괄 범위 간의 트레이드오프를 강요할 수 있음을 보여줬습니다. 가장 명확한 사례인 #412에서는 유사 도메인 거부율 99.21%, OOD 100%, 잘못된 경로 0.62%, p95 244 ms를 달성했지만 지원 사례 정확도는 10.09%까지 무너졌습니다.

0.14 separates concerns:

```text
query
  -> SchemaRouter typed Top-K capability retrieval
  -> downstream LLM agent
  -> execution validation / permission / destructive policy
  -> tool
  -> deterministic result evaluation
  -> optional candidate expansion / retry
```

이는 검색 정확도가 중요하지 않다는 뜻은 아닙니다. 중요한 정확도의 질문이 "검색기가 최종 엔드포인트 하나를 직접 골랐는가?"에서 "압축된 후보 집합이 후속 에이전트에 필요한 모든 기능을 보존했는가?"로 바뀐다는 뜻입니다.

### #417 / #418 / PR #419 — Phase A establishes the retrieval premise

첫 번째 0.14 벤치마크는 20·50·100·250개 엔드포인트 카탈로그에서 단일·다중 도구 작업 23개를 동결했습니다. 에이전트 추론 전에 다중 도구의 데이터 의존성 계약 두 개와 빠져 있던 명시적 작업 인수를 수정해 벤치마크가 실제로 실행 가능하도록 했습니다. 이후 수정된 코퍼스를 다시 동결하고 기존 해시를 대체했습니다.

수정된 정식 동결:
- 워크플로 `36507439562`;
- 산출물 `11006614997`;
- 다이제스트 `sha256:5cec1c650bd2a98fc78f7fbb911c0b15d95a39c96a43848b939ba56302658022`;
- 작업 SHA `9663145d1e331007a45901a6426f62df4e67179ca44dc1b7e0e5bfa6390d1fd1`.

Phase A:
- Recall@1 68.97%;
- Recall@3 96.55%;
- Recall@5 100%;
- Recall@10 100%;
- all-required task coverage@5 100%;
- MRR 0.82471.

Mean Top-5 serialized schema context versus FULL:
- 20 endpoints: 26.76%;
- 50: 11.47%;
- 100: 5.87%;
- 250: 2.38%.

This is the first direct evidence for the revised product thesis: a low Top-1 number can coexist with
complete Top-K capability preservation, and candidate reduction becomes more valuable as the catalog
grows.

PR #419 was merged to main as `1c0dc93e843f6f9bf8a628c80ca95e02efcf5088`.

### #420 / PR #421 — B1 end-to-end downstream-agent A/B

B1 adds a real tool-calling model but keeps SchemaRouter retrieval and the agent role strictly
separate.

Conditions:
- FULL;
- SR-3;
- SR-5;
- SR-10;
- SR-PROGRESSIVE;
- ORACLE.

동일한 결정적 실행기는 타입이 지정된 인수, 여러 단계의 데이터 의존성, 파괴적 작업 정책을 강제합니다. SchemaRouter의 경로 순위 점수와 위치는 숨기고, Top-K 집합을 결정한 다음 도구들을 어휘 순으로 정렬해서 에이전트에게 보여줍니다.

The local model is `Qwen/Qwen3-0.6B` at immutable revision
`c1899de289a04d12100db370d81485cdf75e47ca`. It is a reproducible sanity baseline, not
the final product model.

이것이 #289 연구를 되살리는 것은 아닙니다. #289는 `Qwen3-Reranker-0.6B`를 라우팅 경계 내부의 yes/no 기능 검증기로 시험한 종료된 연구입니다. B1에서는 서로 다른 인과적 모델을 후속 도구 사용 에이전트로만 이용하므로 Qwen 점수가 검색에 영향을 주지 않습니다.

The canonical B1 evaluation contains 552 episodes:
23 tasks × 4 catalog sizes × 6 conditions.

도구 호출 스모크 테스트는 벤치마크 전에 통과했습니다. CPU에서 전체 카탈로그를 사용하는 긴 실행은 런타임 전용 마이크로 샤딩이 필요했지만 작업·카탈로그·모델·프롬프트·K·실행기 의미는 동결 상태를 유지했습니다. 정식 집계는 552개 에피소드가 모두 복원된 경우에만 인정합니다.

### #423 and #424 — required replication layers

B1 alone cannot establish general agent utility.

- #423은 작은 로컬 기준선을 넘어서 일반화하려면 같은 동결 벤치마크를 실질적으로 더 강한 도구 호출 에이전트에서 복제하도록 요구합니다.
- #424는 최종 답변의 사실적 품질을 도구 호출 성공률에서 분리해 FULL과 압축 기능 문맥에서 필수 사실의 재현율, 환각, 숫자·단위 정확도 및 출처를 측정합니다.

연구의 최종 목표는 더 나은 개방 집합 임계값을 찾는 것이 아닙니다. 타입 기반 기능 검색 기반 계층이 통제된 환경과 이후 현실적인 조건에서 후속 에이전트의 효용, 효율성, 안전성을 개선하는지 확인하는 것입니다.


## 2026-09-29 — B1 integrity hardening before canonical aggregate

552개 에피소드의 B1 집계를 인정하기 전에 산출물을 조사하면서 샤드 ID의 기계적 오류를 발견했습니다. 동결된 작업 ID `multi-create-send`가 s06 실행 워크플로와 실행기별 검증 분기에서 `multi-inventory-create-send`로 잘못 참조됐습니다. 수정 전 실행에서는 승인 가능한 전체 집계가 생성되지 않았습니다.

이 수정에서는 작업 문구, 카탈로그 내용, 모델 식별자, K 값, 프롬프트, 후보 순서, 실행기의 성공 판정 의미 또는 임계값을 변경하지 않았습니다. 이제 평가기는 알 수 없는 작업 ID를 안전하게 거부하고, 워크플로 테스트는 모든 동결된 작업이 샤드 전체에 정확히 한 번씩 나타나는지 검증합니다. 집계기는 `(catalog_size, task_id, condition)` 식별자의 유일성과 정확한 동결 23작업 집합을 확인합니다.

두 번째 설계 수준 수정도 승인된 집계 전에 동결했습니다. 동일한 23개 의미 작업을 네 가지 카탈로그 크기로 반복하므로, 대응 쌍의 불확실성을 92개 작업×카탈로그 행이 각각 독립적이라고 가정하지 않고 `task_id` 클러스터 단위로 부트스트랩합니다. 이는 의사 반복을 방지합니다. 따라서 B1의 비열등성 허용치 -2%p는 기술적인 상태 점검용 설명 지표로만 해석하고, 모집단 수준 추론에 필요한 더 큰 독립 홀드아웃 작업 모집단은 #432에서 준비합니다.

The staged 0.14 successors are:
- #428 public typed Top-K retrieval API;
- #430 adaptive shortlist depth;
- #431 execution-state-aware corrective re-retrieval;
- #432 independent held-out generalization surface.

None may use B1 row-level failures to rewrite the frozen B1 task surface.


### B1 v2 canonical protocol

승인된 B1 전체 집계 전에 추가 정적 벤치마크 감사를 수행한 결과, 실행기는 요구하지만 원래 작업 문구에 명시되지 않았던 사용자 인수 두 개가 발견됐습니다. `single-message-send`에는 정확한 메시지 내용이 없었고 `multi-create-share`에는 숫자 형태의 크레딧 금액이 없었습니다. 에이전트가 숨겨진 사용자 의도를 추측하게 두지 않고 작업 계약을 수정했습니다.

이로 인해 동결 작업 SHA는 `9663145d1e331007a45901a6426f62df4e67179ca44dc1b7e0e5bfa6390d1fd1`에서 `bc0b78ff2be11b89e6ac54ea0ee336f944f04b3c203fc61da70a46ff48b4e03c`로 변경됐습니다. 작업 ID, 필요한 경로 집합, 작업 유형, 카탈로그, K 값 및 검색 알고리즘은 변경하지 않았습니다.

별도의 인과성 감사에서도 하나의 어시스턴트 턴에서 여러 도구 호출이 발생하면 모델이 첫 번째 도구 결과를 관찰하기 전에 호출들이 순차적으로 실행될 수 있었던 문제가 발견됐습니다. B1 v2는 이제 다음을 강제합니다.
- 어시스턴트 턴마다 실행되는 도구 호출은 최대 하나;
- 같은 턴에서 뒤따르는 호출은 기록하되 작업 상태를 진전시킬 수 없음;
- 의존성이 있는 호출은 선행 도구의 관찰 결과가 필요;
- `multi-create-send`는 실제 관찰한 `INV-NEW-1` 식별자를 전파해야 함.

The exact B1 runtime is frozen to:
- Ubuntu 24.04;
- Python 3.12.14;
- torch 2.14.0+cpu;
- transformers 4.57.6;
- tokenizers 0.22.2;
- safetensors 0.8.0.

같은 워크플로에서 추론 전에 2턴 결정적 스모크 테스트를 통과해야 합니다. 정식 실행 `36529108855`에서는 사전 검증과 스모크가 모두 통과했습니다. 스모크는 먼저 `lookup__value(key="alpha")`를 실행하고 관찰 후 `calculator__add(a=41,b=1)`를 실행했으며 반복 결과도 결정적으로 동일했습니다.

B1 v2의 Phase A도 다시 통과했습니다.
- 모든 카탈로그 크기에서 Recall@3 96.55%;
- Recall@5 / Recall@10 100% / 100%;
- Top-1은 20/50/100개 엔드포인트에서 68.97%, 250개에서 65.52%;
- 250개 엔드포인트에서 직렬화한 Top-5 문맥의 평균 길이는 FULL의 2.383%.

정식 v2 실행은 커밋 `b9eadefd3cd076f026a54bbc55a949f0424f5dab`의 `36529108855`입니다. 실제 경과 시간을 제어하기 위해 250개 엔드포인트의 작업을 더 작은 묶음으로 나누어 총 30개 실행 작업을 사용합니다. 스케줄링은 실험 처치가 아니므로 모든 작업을 동결된 샤딩 계획에 대조하여 `(catalog_size, task_id, condition)`의 서로 다른 에피소드 정확히 552개로 집계합니다.

해당 집계가 성공하기 전까지 어떤 B1 결과도 승인하지 않습니다. 23개 의미 작업은 통제된 메커니즘 실험 표면이므로 -2%p 기준은 설명적인 기술 게이트일 뿐입니다. 모집단 수준 일반화나 비열등성 주장을 하려면 #432가 필요합니다.
