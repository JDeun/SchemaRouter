# Capability graph drift

SchemaRouter는 이전에 컴파일한 capability-contract snapshot과 갱신된 snapshot을 비교해 어떤 capability graph node를 다시 컴파일해야 하는지 식별할 수 있습니다.

```python
from schemarouter import compare_capability_graph_snapshot

report = compare_capability_graph_snapshot(graph, previous_contracts, refreshed_contracts)
if report.changed:
    print(report.compatibility)
    print(report.invalidated_capability_ids)
```

비교는 deterministic합니다. capability contract fingerprint는 canonical JSON의 SHA-256 digest이므로 mapping insertion order가 fingerprint를 바꾸지 않습니다.

## Invalidation 경계

변경되거나 제거된 contract는 breaking change이며 해당 capability와 기존 immediate graph predecessor/successor를 invalidate합니다. 이 incident edge들이 stale해졌을 수 있는 compatibility decision입니다. 새 capability 추가는 compatible additive drift로 취급하며 새 edge를 계산할 수 있도록 새 node만 invalidate합니다.

이 API는 **invalidation metadata만** 생성합니다. capability 실행, invocation migration, authorization 확대, host execution policy 대체는 하지 않습니다. provider schema 갱신, 영향받은 graph node 재빌드, 갱신 graph 배포 시점은 host가 결정합니다.

provider 수준의 OpenAPI, MCP, scientific-provider schema 변경은 먼저 기존 ToolSpec/schema-diff layer로 normalize해야 합니다. 그 다음 capability graph drift가 갱신 schema에서 생성된 provider-neutral capability contract를 비교합니다. runtime health는 별도 overlay이며 deterministic contract fingerprint에 포함되지 않습니다.
