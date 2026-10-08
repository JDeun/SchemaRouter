# Candidate indexing

SchemaRouter는 deterministic endpoint scoring 전에 exact-recall lexical candidate index를 사용합니다.

index는 성능 최적화일 뿐이며 기존 `_score_endpoint()` ranking rule을 대체하거나 변경하지 않습니다.

## Index 대상

등록된 각 endpoint에 대해 planner는 현재 positive deterministic score를 만들 수 있는 input을 index합니다:

- tool key와 tool name
- preferred endpoint identity
- tool/endpoint name과 description의 token
- output field name, alias, explicit dotted projection path
- exact/substring concept matching에 사용하는 normalized output-field string
- 제공된 request argument에서 사용하는 declared parameter name

따라서 index는 현재 deterministic scorer에서 positive score를 받을 수 있는 모든 endpoint의 superset을 반환합니다. 최종 score와 sorting은 기존 scorer가 그대로 계산합니다.

## Cache invalidation

index는 `ToolRegistry.version`을 기준으로 cache됩니다.

registry mutation이 성공하면 version이 증가해 다음 request에서 planner cache를 invalidate합니다. index 구축은 stable registry snapshot을 읽으며 구축 중 registry가 반복 변경되면 mixed-version view를 cache하지 않고 planning을 실패시킵니다.

## 비교 또는 debugging을 위한 비활성화

```python
planner = SchemaPlanner(
    registry,
    candidate_index=False,
)
```

exhaustive mode는 모든 endpoint를 scoring하며 benchmark 비교와 semantic parity 검증에 유용합니다.

## Benchmark

synthetic benchmark harness가 포함되어 있습니다:

```bash
python scripts/benchmark_candidate_index.py --tools 1000 --iterations 50
```

indexed/exhaustive mode의 elapsed time과 endpoint scorer call 수를 보고합니다.

wall-clock 결과는 hardware와 registry shape에 따라 달라집니다. repository test는 더 강한 deterministic property도 검증합니다. indexed/exhaustive planning은 동일 plan을 생성해야 하며 selective synthetic case에서는 scorer call이 전체 registry가 아니라 정확한 candidate subset으로 줄어야 합니다.

## 범위

현재 index는 in-process이며 registry snapshot에서 재구축됩니다. vector database, remote search service, approximate-nearest-neighbor layer가 아닙니다. 규모상 필요하면 별도의 명시적 contract 뒤에 그런 system을 추가할 수 있지만 deterministic planner recall을 조용히 변경해서는 안 됩니다.
