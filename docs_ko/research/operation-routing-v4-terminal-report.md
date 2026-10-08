# Operation routing v4 최종 보고서

Cycle: `0.11-operation-routing-quality-v4`  
결정일: **2026-09-28**  
상태: **production-target candidate를 promotion하지 않고 종료**

## 결정

0.11 architecture-search cycle은 완료됐습니다. SchemaRouter가 independent request-surface shift 조건에서 기존 85/97/100/1 + 250 ms production target을 검증했다는 주장은 **하지 않습니다**.

가장 강력한 executable development candidate는 canonical DEV gate를 모두 통과했지만, 정확히 고정한 candidate가 새로운 zero-overlap fresh confirmation에서 실패했습니다. 따라서 calibration과 blind-final은 사용하지 않았습니다.

## 기존 목표

| Metric | Target |
| --- | ---: |
| Supported exact route | >= 85% |
| Near-domain unsupported rejection | >= 97% |
| OOD rejection | 100% |
| False-route rate | <= 1% |
| Authority / execution errors | 0 |
| Executable p95 | <= 250 ms |

Canonical DEV: 1,800 rows, SHA `fc085c58ed7c667d71024e60cf9e213e66da8f7b43f6e79551ed810a9e328216`.

## 최강 DEV candidate와 결정적인 fresh 결과

| Evidence | Exact | Near reject | OOD | False-route | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| #324/#325 executable DEV | 85.07% | 99.31% | 100% | 0.62% | 176.94 ms |
| #326/#327 frozen fresh | 84.81% | 90.45% | 100% | 8.49% | 278.37 ms |

Fresh run이 promotion 결정의 근거입니다. Supported-exact floor, near-domain rejection floor, false-route ceiling, p95 target을 모두 충족하지 못했습니다. Fresh corpus는 영구적으로 confirmation-only이며 tuning data로 전환할 수 없습니다.

## 배제된 접근

Cycle에서는 하나의 threshold를 반복 tuning한 것이 아니라 구조적으로 서로 다른 여러 family를 시험했습니다.

- positive dense score/margin boundary 및 winner-first gating
- operation-fit selector 및 hierarchical ranking variant
- multilingual NLI
- explicit negative capability prototype, signed bank, dual negative/background bank, rank-based prototype rule
- grouped-OOF learned verifier geometry와 이어지는 fit-once fresh confirmation
- BGE reranker / cross-encoder veto 및 rescue variant
- Qwen, Laya, Kev, AnyJev typed-decision path
- lightweight BGE negative veto + conditional GTE rescue
- BGE-M3 native ColBERT/sparse operation evidence
- registry-self-calibrated endpoint alias envelope
- threshold-free BGE/GTE top-1 consensus

Fresh 이후 마지막 세 실험은 canonical tuning DEV와 trusted registry/model invariant만으로 도출했습니다. #270/#287/#326 row를 repair에 사용하지 않았습니다.

## 최종 기술적 발견

BGE-M3 raw registered-route top-1은 약 88.45%이므로 closed-set route ranking은 후기 단계의 주된 blocker가 아닙니다.

해결되지 않은 문제는 **open-set surface shift에서의 capability membership**입니다.

> Request가 registered domain과 주제상 가깝지만 등록되지 않은 operation을 요구할 때 semantic ranker는 여전히 높은 confidence로 그럴듯한 registered endpoint를 선택할 수 있습니다.

이 때문에 stronger ranking, model agreement, alias contrast 및 여러 learned/prototype-based gate가 development data에서는 좋아 보이면서도 independent request surface에서는 unsupported rejection을 유지하지 못할 수 있습니다.

## 안전한 reference profile

#259 robust BGE-M3 profile은 가장 유용한 conservative reference로 유지합니다.

- supported exact: 83.77%
- near-domain rejection: 98.96%
- false-route: 0.93%
- planner p95: ~134.95 ms

85% supported exact requirement를 충족하지 못하므로 production-target profile로 이름을 바꾸거나 promotion하지 않습니다.

## Calibration과 blind-final을 실행하지 않은 이유

Issue #198은 candidate가 다음을 만족하도록 요구합니다.

1. canonical DEV 통과
2. 정확히 freeze
3. 새로운 zero-overlap fresh confirmation 통과
4. `fresh-confirmed`로 검증

어떤 0.11 candidate도 이 entry requirement를 충족하지 못했습니다. 그럼에도 calibration이나 blind-final을 실행하면 유효한 promoted candidate 없이 evidence만 소모하여 research protocol을 약화시킵니다.

## 후속 cycle 경계

후속 cycle은 동일한 score geometry에 post-hoc threshold를 추가하는 것이 아니라 **실질적으로 새로운 capability evidence source**가 있을 때만 시작해야 합니다.

다음을 해서는 안 됩니다.

- #270, #287, #326으로 train/tune
- terminal 0.11 family를 route/language/family exception과 함께 부활
- rejected winner를 구제하기 위한 rank-2 fallback 또는 pseudo-route 추가
- provider compatibility를 routing-quality evidence로 취급

후속 연구는 behavior-changing evaluation 전에 architecture, data role, model/runtime identity, authority semantics, stopping rule, fresh-confirmation protocol을 preregister해야 합니다.

## 재현성

Machine-readable closure: `benchmarks/operation-routing-v4-terminal-decision.json`

Canonical evidence ledger: `benchmarks/research-experiment-ledger.json`

전체 design/experiment history: `docs/research/design-and-experiment-history.md`

Paper-ready export: `python scripts/export_research_evidence.py`
