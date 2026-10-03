# 확장 가능한 capability dependency graph

SchemaRouter는 한 capability의 선언된 output이 다른 capability의 모든 requirement를 만족할 수 있을 때만 dependency edge를 만듭니다. 이 graph는 contract inspection primitive이며 workflow를 계획하거나 실행하지 않습니다.

## Indexed construction

Graph 생성은 full compatibility comparator를 호출하기 전에 semantic producer index를 사용합니다.

```text
producer.produces semantic ID
        |
        v
semantic producer index
        |
        v
consumer.requires semantic ID
        |
        v
candidate producer intersection
        |
        v
full type/unit/qualifier compatibility check
```

이 index는 보수적으로 동작합니다. exact semantic ID와 명시적인 `CompatibilityContext.semantic_equivalences` 를 포함합니다. type, unit, dimension, qualifier, conversion 의미는 계속 `compare_capability_composition(...)` 이 최종 판정합니다.

출력은 입력 capability 순서와 무관하게 deterministic합니다.

## Incremental update

Contract가 추가, 삭제 또는 변경되면 다음 API를 사용합니다.

```python
updated = update_capability_dependency_graph(
    old_graph,
    previous_contracts,
    current_contracts,
    context=context,
)
```

추가·삭제·변경된 capability에 incident한 edge만 다시 계산합니다. 결과는 clean full rebuild와 동일해야 합니다.

`CompatibilityContext` 자체가 바뀐 경우에는 full rebuild를 수행해야 합니다. semantic equivalence나 unit conversion policy 변경은 contract 자체가 바뀌지 않은 capability 사이의 edge에도 영향을 줄 수 있습니다.

## Cycle 분석

`dependency_strongly_connected_components(...)` 는 Tarjan 알고리즘을 사용합니다.

`dependency_cycles(...)` 는 cyclic SCC마다 최대 하나의 deterministic simple-cycle witness를 반환하고, `max_witnesses` 로 상한을 둡니다. dense graph에서 모든 simple cycle을 열거하지 않습니다.

## Benchmark

저장소에는 다음 benchmark가 포함됩니다.

```bash
python scripts/benchmark_capability_graph.py
```

기본 sparse benchmark는 1,000 / 10,000 / 50,000 capability에서 build latency, incremental-update latency, edge 수, peak traced memory를 기록합니다. Dense case는 결과 edge 집합 자체가 O(N²)이므로 기본적으로 제한하며, 의도적인 stress run에서만 `--dense-limit` 을 높이는 것을 권장합니다.
