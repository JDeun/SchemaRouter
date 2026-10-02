# Candidate indexing

SchemaRouter는 deterministic endpoint scoring 전에 exact-recall lexical candidate index를 사용합니다. index는 성능 최적화일 뿐 기존 `_score_endpoint()` ranking 규칙을 바꾸지 않습니다.

## Index 대상

현재 deterministic score를 양수로 만들 수 있는 tool key/name, preferred endpoint identity, tool/endpoint name/description token, output field name/alias/dotted projection path, exact/substring concept matching 문자열, supplied request argument에 사용되는 parameter name을 index합니다.

따라서 현재 scorer에서 양수 점수를 받을 수 있는 endpoint의 superset을 반환하고 최종 score/sort는 기존 scorer가 수행합니다.

## Cache invalidation

index는 `ToolRegistry.version`을 기준으로 cache합니다. 성공한 registry mutation이 version을 증가시키면 다음 request에서 planner cache가 무효화됩니다. index 생성 중 registry가 반복 변경되면 mixed-version view를 cache하지 않고 planning을 실패시킵니다.

## 비교/디버깅 시 비활성화

`SchemaPlanner(registry, candidate_index=False)`를 사용하면 모든 endpoint를 scoring하는 exhaustive mode가 됩니다.

## Benchmark와 범위

`python scripts/benchmark_candidate_index.py --tools 1000 --iterations 50`으로 synthetic benchmark를 실행할 수 있습니다. wall-clock은 hardware/registry shape에 따라 달라지지만 repository test는 indexed/exhaustive planning이 동일한 plan을 만들면서 selective case의 scorer call 수가 정확한 candidate subset으로 감소하는지를 검증합니다.

현재 index는 in-process이며 registry snapshot에서 재구축됩니다. vector DB, remote search, ANN layer가 아닙니다. 향후 별도 explicit contract 뒤에 추가할 수 있지만 deterministic planner recall을 조용히 바꾸어서는 안 됩니다.
