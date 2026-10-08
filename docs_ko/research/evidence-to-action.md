# Evidence-to-Action 경계

SchemaRouter는 evidence sufficiency를 workflow orchestration이 아니라 실행 전제조건으로 취급합니다.

## Evidence Contract

`EvidenceContract`는 trusted local authority입니다. 등록된 capability가 이미 선언한 global evidence와 field별 evidence를 요구할 수 있습니다. Model output이나 remote description은 누락된 evidence를 보강하거나 권한을 높일 수 없습니다.

초기 contract는 provenance, license, unit, 정확한 source type, field별 requirement, 명시적인 corroboration count를 지원합니다. Corroboration count가 1보다 크면 independent observation을 확립하는 explicit aggregation boundary가 구현되기 전까지 single-route boundary에서 fail-closed합니다.

## Evidence Ledger

`EvidenceLedgerEntry`는 result payload를 저장하지 않고 실행 경계에서 확인된 evidence를 기록합니다. Tool/endpoint identity, selected logical field, 정확한 tool/endpoint fingerprint, declared available evidence, field별 validation context, validation state를 보존합니다.

`build_evidence_ledger_entry()`는 현재 trusted `ToolSpec`과 `EndpointSpec`을 기준으로 contract를 다시 평가하며 evidence가 부족하면 fail-closed합니다.

이 기능은 DAG, memory system, autonomous replanner, evidence inference engine이 아닙니다.

## Benchmark 계획

Issue 1203의 고정 비교 조건은 다음 세 가지입니다.

1. vanilla tool-using agent
2. evidence gate가 없는 SchemaRouter routing/execution
3. typed evidence gate를 적용한 SchemaRouter

Primary metric은 premature action rate, evidence-complete action rate, unsupported action rate, exact action success, provenance correctness, schema validity, route/field exactness, false refusal rate, latency/token overhead입니다.

Benchmark에서는 locally declared evidence와 model assertion을 구분해야 하며 model assertion을 established evidence로 계산하지 않습니다.

## 재현과 현재 결과

Deterministic seed corpus, runner, baseline, ablation/error analysis는 `benchmarks/evidence-to-action-v1/`에 있습니다. 고정된 8개 seed case에서 routing-only의 premature/unsupported action rate는 0.375이고 evidence-gated 조건에서는 둘 다 0이며 false refusal은 없습니다. 이는 contract regression 결과이며 외부 agent benchmark 성능 주장으로 사용하지 않습니다.

## SafeActBench와의 관계

이 작업의 직접적인 동기는 Lin et al., *From Evidence to Action: How Tool-Using Agents Fail* (arXiv:2610.07753)입니다. SafeActBench는 6개 operational domain의 656개 case를 5개 protocol로 평가합니다. Protocol은 static action judgement, 조사 후 non-action, single consequential action, linear multi-action workflow, dependency-constrained DAG workflow를 구분합니다. Provenance-bound Evidence Ledger와 deterministic trajectory evaluator는 action 전에 필요한 evidence가 실제로 확립됐는지, downstream prerequisite가 충족됐는지를 검사합니다.

SchemaRouter의 현재 8-case seed는 이 656개 case를 재현했다고 주장하지 않습니다. 현재 harness는 execution boundary의 mechanism-level regression test입니다. 외부 비교를 하려면 공개 SafeActBench corpus/evaluator를 실제로 실행하고 model, harness, protocol version, repetition, cost/latency를 별도로 보고해야 합니다.

### 대응 관계

| SafeActBench 관점 | SchemaRouter 경계 |
| --- | --- |
| action 전 evidence 확립 | 실행 전 trusted-local `EvidenceContract` 검사 |
| provenance-bound evidence | payload-free `EvidenceLedgerEntry`와 등록된 evidence metadata |
| premature action | fail-closed evidence sufficiency gate |
| 정확한 action/tool argument | 기존 schema/fingerprint/argument/policy validation |
| multi-action prerequisite | 현재 evidence gate 범위 밖이며 SchemaRouter를 DAG orchestrator로 확장하지 않음 |
| deterministic evaluation | 현재 frozen local regression scorer; 외부 비교에는 공개 SafeActBench evaluator 필요 |

### 후속 검증

PR #1204가 merge된 뒤 2026-10-08에 교신저자들에게 연락했습니다. Externally declared typed evidence requirement가 SafeActBench 평가 모델과 부합하는지, 그리고 single-action protocol부터 검증한 뒤 multi-action으로 확장하는 것이 적절한지 질문했습니다. 향후 결과는 위 deterministic seed와 분리해서 보고합니다.
