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
