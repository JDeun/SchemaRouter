# Operation routing v4 terminal report

Cycle: `0.11-operation-routing-quality-v4`  
Decision date: **2026-09-28**  
Status: **promoted production-target candidate 없이 종료**

## 결정

0.11 architecture-search cycle은 완료됐습니다. SchemaRouter가 independent request-surface shift에서 standing 85/97/100/1 + 250 ms production target을 검증했다는 주장을 하지 않습니다.

가장 강한 executable development candidate는 모든 canonical DEV gate를 통과했지만, exact frozen candidate가 새로운 zero-overlap fresh confirmation에 실패했습니다. 따라서 calibration과 blind-final은 소비하지 않았습니다.

## Standing target

| Metric | Target |
| --- | ---: |
| Supported exact route | >= 85% |
| Near-domain unsupported rejection | >= 97% |
| OOD rejection | 100% |
| False-route rate | <= 1% |
| Authority / execution errors | 0 |
| Executable p95 | <= 250 ms |

Canonical DEV: 1,800 rows, SHA `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

## Strongest DEV candidate와 결정적 fresh result

| Evidence | Exact | Near reject | OOD | False-route | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| #324/#325 executable DEV | 85.07% | 99.31% | 100% | 0.62% | 176.94 ms |
| #326/#327 frozen fresh | 84.81% | 90.45% | 100% | 8.49% | 278.37 ms |

Fresh run이 promotion decision입니다. Supported-exact floor, near-domain rejection floor, false-route ceiling, p95 target을 모두 실패했습니다. Fresh corpus는 영구적으로 confirmation-only이며 tuning data가 될 수 없습니다.

## 배제된 접근

한 threshold를 반복 tuning한 것이 아니라 여러 구조적으로 다른 family를 시험했습니다.

- positive dense score/margin boundary와 winner-first gating
- operation-fit selector와 hierarchical ranking variant
- multilingual NLI
- 명시적 미지원 기능 프로토타입·부호가 있는 근거 뱅크·부정/배경 이중 뱅크·순위 기반 프로토타입 규칙
- grouped-OOF learned verifier geometry 후 fit-once fresh confirmation
- BGE reranker / cross-encoder veto 및 rescue variant
- Qwen·Laya·Kev·AnyJev의 타입 기반 의사결정 경로
- 경량 BGE 부정 판단에 따른 거부와 조건부 GTE 복구
- BGE-M3의 기본 ColBERT 및 희소 벡터 기반 작업 근거
- 레지스트리에서 자체 보정한 엔드포인트 별칭 허용 범위
- 임계값을 사용하지 않는 BGE·GTE Top-1 합의 판정

마지막 세 post-fresh experiment는 canonical tuning DEV와 trusted registry/model invariant에서만 파생됐습니다. #270/#287/#326 row를 repair에 사용하지 않았습니다.

## 최종 기술적 발견

BGE-M3 raw registered-route top-1은 약 88.45%에 도달하므로 closed-set route ranking은 후기 단계의 주된 blocker가 아닙니다.

해결되지 않은 문제는 **open-set surface shift에서의 capability membership**입니다.

> 요청이 registered domain과 주제상 가깝지만 등록되지 않은 operation을 요구할 때 semantic ranker는 높은 confidence로 그럴듯한 registered endpoint를 선택할 수 있습니다.

이 때문에 더 강한 ranking, model agreement, alias contrast, 여러 learned/prototype gate가 development data에서는 좋아 보여도 independent request surface에서 unsupported rejection을 보존하지 못할 수 있습니다.

## Safe reference profile

#259 robust BGE-M3 profile은 가장 유용한 conservative reference로 남습니다.

- supported exact: 83.77%
- near-domain rejection: 98.96%
- false-route: 0.93%
- planner p95: ~134.95 ms

85% supported exact requirement를 놓치므로 production-target profile로 rename/promote하지 않습니다.

## Calibration과 blind-final을 실행하지 않은 이유

Issue #198은 다음 candidate를 요구합니다.

1. canonical DEV 통과
2. 정확히 freeze
3. 새로운 zero-overlap fresh confirmation 통과
4. `fresh-confirmed`로 validation

0.11 candidate 중 이 entry requirement를 만족한 것은 없습니다. 그럼에도 calibration/blind-final을 실행하면 valid promoted candidate 없이 evidence만 소비하고 research protocol을 약화시킵니다.

## Successor-cycle boundary

후속 cycle은 같은 score geometry에 또 다른 post-hoc threshold를 추가하는 것이 아니라 **materially new source of capability evidence**로 시작해야 합니다.

금지:

- #270, #287, #326에서 train/tune
- route/language/family exception으로 terminal 0.11 family 부활
- rejected winner를 rescue하기 위한 rank-2 fallback 또는 pseudo-route 추가
- provider compatibility를 routing-quality evidence로 취급

후속 연구는 behavior-changing evaluation 전에 architecture, data role, model/runtime identity, authority semantics, stopping rule, fresh-confirmation protocol을 preregister해야 합니다.

## Reproducibility

기계 판독형 최종 판정: `benchmarks/operation-routing-v4-terminal-decision.json`

정식 근거 원장: `benchmarks/research-experiment-ledger.json`

전체 설계 및 실험 이력: `docs/research/design-and-experiment-history.md`

논문용 근거 내보내기 명령어: `python scripts/export_research_evidence.py`
